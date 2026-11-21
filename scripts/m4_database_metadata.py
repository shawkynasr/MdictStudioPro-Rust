"""Run the desktop gate and independently check SQLite metadata copies."""
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
from m4_database import MANIFEST, graph, APP_ID, MDX_SQL, META_SQL, framed
import sqlite3
from verify_database_metadata import check as check_copy
from verify_database_jsonl import check, read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-metadata'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-metadata-v1', 'status': 'failed',
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
        for name in ['metadata_copy_preserves_every_row_styles_encoding_and_other_attributes',
                     'stale_sources_cancel_and_destination_races_leave_no_partial_copy',
                     'invalid_metadata_and_databases_without_headers_are_refused',
                     'database_metadata_copy_route_cancels_retries_and_rebuilds_edited_header',
                     'metadata_copy_jobs_release_reader_and_preserve_selected_header_edits']:
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

        fixture = json.loads((ROOT / 'm3/fixtures/database-stylesheet.json').read_text())
        rows = [(r['key'], r['text']) for r in fixture['entries']]
        for encoding in ['UTF-8', 'UTF-16']:
            label = encoding.lower().replace('-', '')
            source = out / (label+'-source.db')
            destination = out / (label+'-edited.db')
            attrs = {'GeneratedByEngineVersion': '2.0', 'RequiredEngineVersion': '2.0',
                     'Title': 'Metadata copy · '+encoding, 'Description': 'before', 'Encoding': encoding,
                     'KeyCaseSensitive': 'No', 'StripKey': 'No', 'Format': 'Html', 'Compact': 'Yes',
                     'StyleSheet': fixture['stylesheet']}
            raw = json.dumps(attrs, ensure_ascii=False, separators=(',', ':'))
            with sqlite3.connect(source) as connection:
                connection.execute(MDX_SQL)
                connection.executemany('INSERT INTO mdx VALUES (?,?)', rows)
                connection.execute(f'PRAGMA application_id={APP_ID}')
                connection.execute('PRAGMA user_version=2')
                connection.execute(META_SQL)
                connection.executemany('INSERT INTO studio_meta VALUES (?,?)', [
                    ('profile', 'studio-sqlite-mdx-v1'), ('records', str(len(rows))),
                    ('rows_sha256', framed(rows)), ('source_sha256', 'a'*64), ('text_profile', 'canonical_v1'),
                    ('mdx_header_json', raw), ('mdx_header_sha256', hashlib.sha256(raw.encode()).hexdigest())])
            connection.close()
            before = source.read_bytes()
            expected_hash = hashlib.sha256(before).hexdigest()
            edits = {'title': 'edited 字 / مرحبا & <title>', 'description': 'hi new world\nsecond line'}
            request = {'operation': 'db_edit_metadata', 'source': str(source), 'destination': str(destination),
                       'expected_source_sha256': expected_hash, 'edits': edits}
            receipt = execute(label+'-copy', request)
            oracle = check_copy(source, destination, edits)
            assert receipt['records'] == len(rows) and receipt['rows_sha256'] == framed(rows)
            assert receipt['source_sha256'] == expected_hash
            assert receipt['dictionary_metadata'] == {**attrs, 'Title': edits['title'], 'Description': edits['description']}
            assert receipt['bytes'] == destination.stat().st_size
            dest_before = destination.read_bytes()
            execute(label+'-no-clobber', request, 'destination_exists')
            assert destination.read_bytes() == dest_before
            empty = out / (label+'-empty-title.db')
            execute(label+'-empty-title', {**request, 'destination': str(empty), 'edits': {'title': ''}})
            empty_oracle = check_copy(source, empty, {'title': ''})
            for name, changes, error in [
                ('stale', {'expected_source_sha256': '0'*64}, 'integrity'),
                ('empty-edits', {'edits': {}}, 'invalid_input'),
                ('invalid-xml', {'edits': {'title': 'bad\0'}}, 'invalid_input'),
                ('title-cap', {'edits': {'title': 'x'*4097}}, 'limit_exceeded'),
                ('description-cap', {'edits': {'description': 'x'*8193}}, 'limit_exceeded')]:
                dest = out / (label+'-'+name+'.db')
                execute(label+'-'+name, {**request, **changes, 'destination': str(dest)}, error)
                assert not dest.exists()
            assert source.read_bytes() == before
            report['checks'].append({'encoding': encoding, 'oracle': oracle, 'empty_title_oracle': empty_oracle,
                                     'no_partial_failure_outputs': True, 'existing_output_unchanged': True,
                                     'fixture_scope': 'synthetic stored MDX metadata; not an MDX decoding claim'})
        report.update(source_unchanged=True, status='database_metadata_native_and_oracle_passed_GUI_pending', stage='complete')
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
    return 0 if report['status'] == 'database_metadata_native_and_oracle_passed_GUI_pending' else 1


if __name__ == '__main__':
    sys.exit(main())
