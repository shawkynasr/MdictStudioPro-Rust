"""Qualify the persistent native SQLite reader; desktop integration is pending."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import traceback

from m2_closeout import inventory
from m3_shell import ROOT, sources
from m4_database import MANIFEST, check_database, framed, graph
from verify_gui_extraction import txt_rows


def check_page(page, expected, source_hash, offset, limit=2):
    assert page['profile'] == 'studio-sqlite-text-v1'
    assert page['source_sha256'] == source_hash
    assert page['total'] == len(expected) and page['offset'] == offset
    assert page['rows'] == expected[offset:offset + limit], 'Row contents, IDs, order or duplicates changed'
    end = min(offset, len(expected)) + len(page['rows'])
    assert page['next_offset'] == (end if end < len(expected) else None)
    assert page.get('dictionary_metadata') is None


def check_receipt(receipt, expected, source_hash):
    info = receipt['info']
    assert info['profile'] == 'sqlite-persistent-reader-v1'
    assert info['database_profile'] == 'studio-sqlite-text-v1'
    assert info['source_sha256'] == source_hash
    assert info['records'] == len(expected) and info['rows_sha256'] == framed(expected)
    assert info.get('dictionary_metadata') is None
    rows = [{'rowid': str(i + 1), 'key': key, 'text': body} for i, (key, body) in enumerate(expected)]
    assert len(receipt['browse']) == (len(rows) + 1) // 2
    for i, page in enumerate(receipt['browse']):
        check_page(page, rows, source_hash, 2 * i)
    cases = [('prefix', 'app', 0), ('prefix', 'app', 2), ('exact', 'apple', 0),
             ('prefix', 'App', 0), ('prefix', 'a%', 0), ('prefix', 'a_', 0),
             ('prefix', '字', 0), ('prefix', 'مر', 0), ('exact', 'app', 0)]
    assert len(receipt['lookups']) == len(cases)
    for result, (kind, query, offset) in zip(receipt['lookups'], cases):
        assert (result['kind'], result['query']) == (kind, query)
        filtered = [r for r in rows if (r['key'].startswith(query) if kind == 'prefix' else r['key'] == query)]
        check_page(result['page'], filtered, source_hash, offset)
    assert receipt['source_removed'] is True
    assert receipt['closed_info'] == receipt['closed_page'] == 'closed'
    opening = [p['phase'] for p in receipt['opening_phases']]
    assert opening.count('database_snapshot') == 1 and opening[-1] == 'database_reader_ready'
    phases = [p['phase'] for p in receipt['page_phases']]
    assert phases == ['database_page'] * (len(receipt['browse']) + len(cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-reader'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a new m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-reader-v1', 'status': 'failed',
              'native_tests_executed': False, 'GUI_integration_enabled': False, 'steps': []}
    protected = current = lock_bytes = None
    lock = ROOT / 'm4/database/Cargo.lock'

    def current_sources():
        result = sources()
        for name in ['scripts/m4_database_reader.py', 'scripts/test_m4_database_reader.py', 'docs/M4-DATABASE-READER.md']:
            result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        return result

    def run(name, command):
        report['stage'] = name
        print(name, flush=True)
        done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=1200)
        log = done.stdout + '\nSTDERR:\n' + done.stderr
        (out / (name + '.log')).write_text(log, encoding='utf-8')
        report['steps'].append({'name': name, 'command': command, 'returncode': done.returncode})
        if done.returncode:
            raise RuntimeError(f'{name} failed; see {out / (name + ".log")}')
        return done.stdout

    try:
        protected, current = inventory(), current_sources()
        report.update(protected_source_sha256=protected, source_sha256=current)
        lock_bytes = lock.read_bytes()
        report['lock_sha256'] = hashlib.sha256(lock_bytes).hexdigest()
        report['registry_graph'] = graph(lock)
        cargo = shutil.which('cargo')
        if not cargo:
            raise RuntimeError('Run on the Rust-enabled Mac; no native checks ran here')
        run('metadata', [cargo, 'metadata', '--offline', '--locked', '--format-version', '1', '--manifest-path', MANIFEST])
        test_log = run('reader-tests', [cargo, 'test', '--offline', '--locked', '--manifest-path', MANIFEST, '--lib'])
        if not re.search(r'test result: ok\. (?:[1-9][0-9]*) passed; 0 failed;', test_log):
            raise RuntimeError('Refuse a zero-test or failed native run')
        # Require every newly added lifecycle regression to have actually run.
        reader_tests = re.findall(r'^test reader::tests::\S+ \.\.\. ok$', test_log, re.M)
        assert len(reader_tests) >= 11, 'Expected at least eleven passing persistent reader tests'
        report['native_tests_executed'] = True
        run('reader-example', [cargo, 'run', '--offline', '--locked', '--manifest-path', MANIFEST,
                               '--example', 'persistent_reader', '--', str(out / 'native')])
        native = out / 'native'
        expected = txt_rows(ROOT / 'm3/fixtures/database-prefix.txt')
        assert len(expected) == 8
        original = native / 'original.db'
        source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        report['oracle'] = check_database(original, expected, hashlib.sha256((native / 'source.txt').read_bytes()).hexdigest())
        receipt = json.loads((native / 'reader.json').read_text())
        check_receipt(receipt, expected, source_hash)
        assert not (native / 'reader-source.db').exists()
        report['checks'] = ['independent SQLite rows and metadata', 'pinned snapshot after source removal',
                            'all/exact/prefix pages with duplicate row identities', 'one validation across all pages',
                            'close/drop cleanup and cancellation recovery in native tests']
        report.update(status='persistent_reader_backend_passed_GUI_integration_pending', stage='complete')
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        try:
            if protected is not None:
                assert inventory() == protected, 'Protected M2 sources changed'
            if current is not None:
                assert current_sources() == current, 'Qualification sources changed during run'
            if lock_bytes is not None:
                assert lock.read_bytes() == lock_bytes, 'M4 dependency lock changed'
        except Exception as error:
            report.update(status='failed', error=str(error))
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['status'], flush=True)
    print(out / 'report.json', flush=True)
    return 0 if report['status'].startswith('persistent_reader_backend_passed') else 1


if __name__ == '__main__':
    sys.exit(main())
