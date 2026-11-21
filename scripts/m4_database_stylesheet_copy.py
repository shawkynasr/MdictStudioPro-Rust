"""Qualify database stylesheet editing and MDX rebuilds without changing accepted M2 code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from m2_closeout import inventory
from m3_shell import ROOT, sources, ADAPTER
from verify_database_metadata import check as check_copy
from verify_database_mdx import check as check_rebuild
from verify_mdx_database import read_mdx, check as check_import


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, default=Path('m4-database-out-stylesheet-copy'))
    a = p.parse_args()
    out = a.output.resolve()
    if not out.name.startswith('m4-database-out'):
        p.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-stylesheet-copy-v1', 'status': 'failed',
              'native_tests_executed': False, 'GUI_checks_executed': False, 'steps': [], 'checks': []}
    protected = current = lock_before = None
    lock = ROOT/'m4/database/Cargo.lock'

    def source_hashes():
        return {n: h for n, h in sources().items() if '__pycache__' not in Path(n).parts and Path(n).name != '.DS_Store'}

    def run(name, command):
        report['stage'] = name
        print(name, flush=True)
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600)
        (out/(name+'.log')).write_text(done.stdout+'\nSTDERR:\n'+done.stderr, encoding='utf-8')
        report['steps'].append({'name': name, 'command': command, 'returncode': done.returncode})
        assert done.returncode == 0, f'{name} failed; see {out/(name+".log")}'

    try:
        protected, current, lock_before = inventory(), source_hashes(), lock.read_bytes()
        report.update(protected_source_sha256=protected, source_sha256=current,
                      lock_sha256=hashlib.sha256(lock_before).hexdigest())
        cargo = shutil.which('cargo')
        if not cargo:
            raise RuntimeError('Run on the Rust-enabled Mac; native tests did not run here')
        # This child gate includes the full desktop build and existing copy checks.
        run('metadata-and-desktop-gate', [sys.executable, 'scripts/m4_database_metadata.py', '--output', str(out/'m4-database-out-metadata-gate')])
        gate = out/'m4-database-out-metadata-gate'
        parent = json.loads((gate/'report.json').read_text())
        assert parent['status'] == 'database_metadata_native_and_oracle_passed_GUI_pending'
        shell = json.loads((gate/'m3-shell-out/m3-shell-report.json').read_text())
        assert shell['native_tests_executed'] and all(s['returncode'] == 0 for s in shell['steps'])
        logs = '\n'.join(s.get('log_tail', '') for s in shell['steps'])
        for name in ['stylesheet_copy_preserves_rows_and_unselected_metadata_and_rejects_missing_markers',
                     'stylesheet_shape_bounds_flags_and_clearing_unmarked_bodies_are_checked']:
            assert f'{name} ... ok' in logs, f'Required native test did not run: {name}'
        report.update(native_tests_executed=True, metadata_report=str(gate/'report.json'),
                      shell_report=str(gate/'m3-shell-out/m3-shell-report.json'))
        native = out/'native'
        run('native-style-roundtrip', [cargo, 'run', '--offline', '--locked', '--manifest-path', ADAPTER,
                                      '--example', 'sqlite_stylesheet_copy', '--', str(native)])
        fixture = json.loads((ROOT/'m3/fixtures/database-stylesheet.json').read_text())
        expected = [(r['key'], r['text']) for r in fixture['entries']]
        style = (ROOT/'m3/fixtures/database-stylesheet-green.txt').read_bytes().decode()
        receipts = json.loads((native/'receipts.json').read_text())
        assert len(receipts) == 2
        for label, receipt in zip(['utf8', 'utf16'], receipts):
            directory = native/label
            source, copy, rebuilt, back = [directory/name for name in ['dictionary.db', 'edited.db', 'rebuilt.mdx', 'roundtrip.db']]
            original_hash, rows, attrs = read_mdx(directory/'original.mdx')
            assert rows == expected and attrs['StyleSheet'] == fixture['stylesheet']
            check_import(source, rows, attrs, original_hash)
            oracle = check_copy(source, copy, {'stylesheet': style})
            rebuilt_hash, actual, edited_attrs = read_mdx(rebuilt)
            rebuilt_oracle = check_rebuild(copy, actual, edited_attrs)
            assert edited_attrs == {**attrs, 'StyleSheet': style}
            imported_oracle = check_import(back, actual, edited_attrs, rebuilt_hash)
            assert receipt['copy']['receipt']['operation'] == 'db_edit_metadata'
            assert receipt['copy']['receipt']['value']['dictionary_metadata'] == edited_attrs
            assert receipt['copy']['receipt']['value']['rows_sha256'] == oracle['rows_sha256']
            report['checks'].append({'encoding': label, 'copy_oracle': oracle,
                                     'rebuild_oracle': rebuilt_oracle, 'roundtrip_import_oracle': imported_oracle,
                                     'definitions_and_raw_markers_unchanged': True})
        report.update(status='database_stylesheet_copy_native_and_oracle_passed_GUI_pending', stage='complete')
    except (Exception, KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
    finally:
        try:
            if protected is not None:
                assert inventory() == protected, 'Protected M2 source changed'
            if current is not None:
                assert source_hashes() == current, 'Qualification sources changed'
            if lock_before is not None:
                assert lock.read_bytes() == lock_before, 'M4 dependency lock changed'
        except Exception as error:
            report.update(status='failed', error=str(error))
        (out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(report['status'], flush=True)
    print(out/'report.json', flush=True)
    return 0 if report['status'] == 'database_stylesheet_copy_native_and_oracle_passed_GUI_pending' else 1


if __name__ == '__main__':
    raise SystemExit(main())
