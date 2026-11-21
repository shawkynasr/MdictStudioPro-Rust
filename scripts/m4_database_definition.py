"""Run the desktop gate and independently check stored-definition substring search."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from m2_closeout import inventory
from m3_shell import ROOT, sources
from m4_database import MANIFEST, graph
from verify_database_jsonl import check, read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-definition'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-definition-v1', 'status': 'failed',
              'native_tests_executed': False, 'GUI_checks_executed': False, 'steps': [], 'checks': []}
    protected = current = lock_bytes = None
    lock = ROOT / 'm4/database/Cargo.lock'

    def source_hashes():
        return {n: h for n, h in sources().items()
                if '__pycache__' not in Path(n).parts and Path(n).name != '.DS_Store'}

    def run(name, command, expected=0):
        report['stage'] = name
        print(name, flush=True)
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        log = done.stdout + '\nSTDERR:\n' + done.stderr
        (out / (name + '.log')).write_text(log, encoding='utf-8')
        report['steps'].append({'name': name, 'command': command, 'returncode': done.returncode})
        if done.returncode != expected:
            raise RuntimeError(f'{name} failed; see {out / (name + ".log")}')
        return done.stdout

    try:
        protected, current = inventory(), source_hashes()
        report.update(protected_source_sha256=protected, source_sha256=current)
        lock_bytes = lock.read_bytes()
        report['lock_sha256'] = hashlib.sha256(lock_bytes).hexdigest()
        report['registry_graph'] = graph(lock)
        cargo = shutil.which('cargo')
        if not cargo:
            raise RuntimeError('Run on the Rust-enabled Mac; no native tests ran here')
        shell_out = out / 'm3-shell-out'
        run('desktop-gate', [sys.executable, 'scripts/m3_shell.py', '--output', str(shell_out)])
        shell = json.loads((shell_out / 'm3-shell-report.json').read_text())
        assert shell['status'] == 'adapter_tests_and_shell_compile_passed_native_launch_pending'
        assert shell['native_tests_executed'] and all(s['returncode'] == 0 for s in shell['steps'])
        logs = '\n'.join(s.get('log_tail', '') for s in shell['steps'])
        for name in ['definition_search_matches_stored_text_literals_unicode_and_duplicate_rows',
                     'definition_scan_cancellation_snapshot_and_page_overflow_allow_retry',
                     'definition_requests_validate_cancel_and_retry_with_matching_policy',
                     'definition_search_commands_preserve_pages_and_reader_identity']:
            assert f'{name} ... ok' in logs, f'Required native test did not run: {name}'
        report.update(native_tests_executed=True, shell_report=str(shell_out / 'm3-shell-report.json'))
        metadata = json.loads(run('backend-metadata', [cargo, 'metadata', '--offline', '--locked', '--format-version', '1', '--manifest-path', MANIFEST]))
        run('backend-build', [cargo, 'build', '--offline', '--locked', '--manifest-path', MANIFEST])
        binary = Path(metadata['target_directory']) / 'debug' / ('studio-database.exe' if sys.platform == 'win32' else 'studio-database')

        def execute(name, request, error=None):
            path = out / (name + '.request.json')
            path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
            result = json.loads(run(name, [str(binary), 'execute', str(path)], 1 if error else 0))
            if error:
                assert result['status'] == 'failed' and result['error']['code'] == error
                return None
            assert result['status'] == 'passed'
            return result['result']['value']

        fixture = ROOT / 'm3/fixtures/database-definition.jsonl'
        rows = read_jsonl(fixture)
        assert len(rows) == 10
        database = out / 'definitions.db'
        execute('import-fixture', {'operation': 'jsonl_to_db', 'source': str(fixture), 'destination': str(database)})
        report['fixture_oracle'] = check(database, fixture)
        before = database.read_bytes()
        source_hash = hashlib.sha256(before).hexdigest()
        cases = [('needle', False, [3]), ('Needle', False, [1]), ('NEEDLE', False, [2]),
                 ('nEeDlE', True, [1, 2, 3]), ('中文', False, [5, 6]), ('أهلاً', False, [7]),
                 ('<div', False, [1, 7]), ('`2`', False, [4]), ('? * % _', False, [4]),
                 ('\\', False, [4]), ('</div>\nNeedle', False, [1]), ('missing', False, []),
                 ('école', True, [9]), ('ΟΣ', True, [9]), ('οσ', True, []), ('İ', True, [9]),
                 ('straße', True, [9]), ('STRASSE', True, []), ('𐐨', True, [9])]
        for index, (query, lower, ids) in enumerate(cases):
            expected = [{'rowid': str(i), 'key': rows[i-1][0], 'text': rows[i-1][1]} for i in ids]
            for offset in range(0, max(len(ids), 1), 2):
                page = execute(f'case-{index}-offset-{offset}', {
                    'operation': 'definition_lookup', 'source': str(database), 'query': query,
                    'lower': lower, 'offset': offset, 'limit': 2})
                assert page['source_sha256'] == source_hash and page['total'] == len(ids)
                assert page['offset'] == offset and page['rows'] == expected[offset:offset+2]
                assert page['next_offset'] == (offset+2 if offset+2 < len(ids) else None)
            report['checks'].append({'query': query, 'lower': lower, 'rowids': ids, 'status': 'passed'})
        execute('empty-query', {'operation': 'definition_lookup', 'source': str(database), 'query': '', 'offset': 0, 'limit': 2}, 'invalid_input')
        execute('query-cap', {'operation': 'definition_lookup', 'source': str(database), 'query': 'a'*4097, 'offset': 0, 'limit': 2}, 'invalid_input')
        assert database.read_bytes() == before
        report.update(source_unchanged=True, status='database_definition_native_and_oracle_passed_GUI_pending', stage='complete')
    except (Exception, KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
    finally:
        try:
            if protected is not None:
                assert inventory() == protected, 'Protected M2 source changed'
            if current is not None:
                assert source_hashes() == current, 'Qualification sources changed during run'
            if lock_bytes is not None:
                assert lock.read_bytes() == lock_bytes, 'M4 lock changed'
        except Exception as error:
            report.update(status='failed', error=str(error))
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(report['status'], flush=True)
    print(out / 'report.json', flush=True)
    return 0 if report['status'] == 'database_definition_native_and_oracle_passed_GUI_pending' else 1


if __name__ == '__main__':
    sys.exit(main())
