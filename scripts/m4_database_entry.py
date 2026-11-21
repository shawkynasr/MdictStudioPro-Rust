"""Run the desktop gate and independently check selected-definition database copies."""
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
from verify_database_entry import check as check_copy
from verify_database_jsonl import check, read_jsonl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-database-out-entry'))
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-database-out'):
        parser.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-database-entry-v1', 'status': 'failed',
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
        for name in ['entry_copy_changes_only_selected_duplicate_even_with_sparse_rowids',
                     'entry_copy_preserves_stored_header_and_checks_numeric_markers',
                     'entry_copy_stale_bounds_cancellation_and_destination_races_are_atomic',
                     'entry_copy_route_cancels_retries_and_rebuilds_selected_definition',
                     'entry_copy_jobs_target_the_selected_duplicate_and_release_admission']:
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
        for encoding in ['UTF-8','UTF-16','legacy']:
            label=encoding.lower().replace('-','')
            source=out/(label+'-source.db');destination=out/(label+'-edited.db')
            physical=[-2,7,99] if encoding=='legacy' else list(range(1,len(rows)+1))
            values=[('字','first'),('字','second'),('empty','')] if encoding=='legacy' else rows
            with sqlite3.connect(source) as connection:
                connection.execute(MDX_SQL)
                connection.executemany('INSERT INTO mdx(rowid,entry,paraphrase) VALUES (?,?,?)',[(rid,k,t) for rid,(k,t) in zip(physical,values)])
                if encoding!='legacy':
                    attrs={'GeneratedByEngineVersion':'2.0','RequiredEngineVersion':'2.0',
                           'Title':'Entry copy · '+encoding,'Description':'before','Encoding':encoding,
                           'KeyCaseSensitive':'No','StripKey':'No','Format':'Html','Compact':'Yes',
                           'StyleSheet':fixture['stylesheet']}
                    raw=json.dumps(attrs,ensure_ascii=False,separators=(',',':'))
                    connection.execute(f'PRAGMA application_id={APP_ID}')
                    connection.execute('PRAGMA user_version=2')
                    connection.execute(META_SQL)
                    connection.executemany('INSERT INTO studio_meta VALUES (?,?)',[
                        ('profile','studio-sqlite-mdx-v1'),('records',str(len(values))),
                        ('rows_sha256',framed(values)),('source_sha256','a'*64),('text_profile','canonical_v1'),
                        ('mdx_header_json',raw),('mdx_header_sha256',hashlib.sha256(raw.encode()).hexdigest())])
            connection.close()
            before=source.read_bytes();expected_hash=hashlib.sha256(before).hexdigest()
            rowid='7' if encoding=='legacy' else '3'
            body='<p>Edited second duplicate.</p>' if encoding=='legacy' else '`1`Edited second duplicate.'
            request={'operation':'db_edit_entry','source':str(source),'destination':str(destination),
                     'expected_source_sha256':expected_hash,'rowid':rowid,'text':body}
            receipt=execute(label+'-edit',request)
            oracle=check_copy(source,destination,rowid,body)
            for name in ['records','source_sha256','rows_sha256','source_rowid','output_rowid']:
                assert receipt[name]==oracle[name],name
            dest_before=destination.read_bytes()
            execute(label+'-no-clobber',request,'destination_exists')
            assert destination.read_bytes()==dest_before
            empty=out/(label+'-empty.db')
            execute(label+'-empty',{**request,'destination':str(empty),'text':''})
            empty_oracle=check_copy(source,empty,rowid,'')
            for name,changes,error in [
                ('stale',{'expected_source_sha256':'0'*64},'integrity'),
                ('missing-row',{'rowid':'500'},'invalid_input'),
                ('bad-row',{'rowid':'03'},'invalid_input'),
                ('body-cap',{'text':'x'*8193},'limit_exceeded')]:
                dest=out/(label+'-'+name+'.db')
                execute(label+'-'+name,{**request,**changes,'destination':str(dest)},error)
                assert not dest.exists()
            if encoding!='legacy':
                dest=out/(label+'-missing-rule.db')
                execute(label+'-missing-rule',{**request,'destination':str(dest),'text':'`9`missing rule'},'invalid_input')
                assert not dest.exists()
            assert source.read_bytes()==before
            report['checks'].append({'encoding':encoding,'oracle':oracle,'empty_definition_oracle':empty_oracle,
                                     'existing_output_unchanged':True,'no_partial_failure_outputs':True})
        report.update(source_unchanged=True, status='database_entry_native_and_oracle_passed_GUI_pending', stage='complete')
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
    return 0 if report['status'] == 'database_entry_native_and_oracle_passed_GUI_pending' else 1


if __name__ == '__main__':
    sys.exit(main())
