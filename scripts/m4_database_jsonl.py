"""Run the desktop gate, then independently qualify native SQLite to JSONL export."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import traceback
from m2_closeout import inventory
from m3_shell import ROOT, sources
from m4_database import APP_ID, MDX_SQL, META_SQL, MANIFEST, framed, graph
from verify_database_jsonl import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-jsonl'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-jsonl-v1', 'status': 'failed',
              'native_tests_executed': False, 'GUI_checks_executed': False, 'steps': [], 'checks': []}
    protected = current = lock_bytes = None
    lock = ROOT / 'm4/database/Cargo.lock'

    def source_hashes():
        return {name: digest for name, digest in sources().items()
                if '__pycache__' not in Path(name).parts and Path(name).name != '.DS_Store'}

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
        backend_log = next(s['log_tail'] for s in shell['steps'] if s['name'] == 'database-backend-tests')
        for name in ['jsonl_preserves_order_duplicates_empty_bodies_and_text_controls',
                     'cancellation_output_limits_and_destination_races_leave_no_partial_export',
                     'staged_verifier_rejects_changed_missing_reordered_and_duplicate_rows']:
            assert f'test jsonl::tests::{name} ... ok' in backend_log, 'Required JSONL test did not run'
        report['native_tests_executed'] = True
        report['shell_report'] = str(shell_out / 'm3-shell-report.json')
        metadata = json.loads(run('backend-metadata', [cargo, 'metadata', '--offline', '--locked', '--format-version', '1', '--manifest-path', MANIFEST]))
        run('backend-build', [cargo, 'build', '--offline', '--locked', '--manifest-path', MANIFEST])
        binary = Path(metadata['target_directory']) / 'debug' / ('studio-database.exe' if sys.platform == 'win32' else 'studio-database')
        rows = [('apple', '<div>A fruit.</div>'), ('字', 'first\r\n\n</>\n"quoted"\\tail\0'),
                ('字', 'second'), ('مرحبا', 'أهلاً وسهلاً'), ('empty', ''), ('literal', '`2`marker\n\n')]
        attributes = {'GeneratedByEngineVersion': '2.0', 'RequiredEngineVersion': '2.0',
                      'KeyCaseSensitive': 'No', 'StripKey': 'No', 'Title': 'JSONL · 字', 'Description': 'row-only export', 'Encoding': 'UTF-8',
                      'Format': 'Html', 'StyleSheet': '2\n<b>\n</b>\n', 'Compact': 'Yes'}

        def execute(name, database, destination, error=None):
            request = out / (name + '.request.json')
            request.write_text(json.dumps({'operation': 'db_to_jsonl', 'source': str(database), 'destination': str(destination)}))
            reply = json.loads(run(name, [str(binary), 'execute', str(request)], expected=1 if error else 0))
            if error:
                assert reply['status'] == 'failed' and reply['error']['code'] == error
            else:
                assert reply['status'] == 'passed' and reply['result']['operation'] == 'db_to_jsonl'
            return reply

        for studio in [False, True]:
            name = 'studio-mdx' if studio else 'legacy'
            database, destination = out / (name + '.db'), out / (name + '.jsonl')
            with sqlite3.connect(database) as connection:
                connection.execute(MDX_SQL)
                connection.executemany('INSERT INTO mdx VALUES (?,?)', rows)
                if studio:
                    raw = json.dumps(attributes, ensure_ascii=False, separators=(',', ':'))
                    connection.execute(f'PRAGMA application_id={APP_ID}')
                    connection.execute('PRAGMA user_version=2')
                    connection.execute(META_SQL)
                    connection.executemany('INSERT INTO studio_meta VALUES (?,?)', [
                        ('profile', 'studio-sqlite-mdx-v1'), ('records', str(len(rows))),
                        ('source_sha256', 'a' * 64), ('rows_sha256', framed(rows)), ('text_profile', 'canonical_v1'),
                        ('mdx_header_json', raw), ('mdx_header_sha256', hashlib.sha256(raw.encode()).hexdigest())])
            connection.close()
            receipt = execute(name, database, destination)['result']['value']
            verified = check(database, destination)
            for field in ['records', 'source_sha256', 'rows_sha256', 'bytes']:
                assert receipt[field] == verified[field], field
            assert receipt.get('dictionary_metadata') == (attributes if studio else None)
            before = destination.read_bytes()
            execute(name + '-no-clobber', database, destination, 'destination_exists')
            assert destination.read_bytes() == before
            report['checks'].append({'fixture': name, 'oracle': verified,
                                     'duplicate_order_and_controls': 'passed', 'existing_output_unchanged': True})
        report.update(status='database_jsonl_native_and_oracle_passed_GUI_pending', stage='complete')
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
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['status'], flush=True)
    print(out / 'report.json', flush=True)
    return 0 if report['status'] == 'database_jsonl_native_and_oracle_passed_GUI_pending' else 1


if __name__ == '__main__':
    sys.exit(main())
