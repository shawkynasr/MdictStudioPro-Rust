"""Qualify sequential database edits and prepare UTF-8/UTF-16 reader fixtures."""
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
from verify_database_metadata import check as check_metadata
from verify_database_entry import check as check_entry
from verify_database_add import check as check_add
from verify_database_delete import check as check_delete
from verify_database_mdx import check as check_rebuild, groups
from verify_mdx_database import read_mdx, check as check_import

DESCRIPTION='Edit, rename, add and delete into database copies.'
EDITED='`1`EDITED_DUPLICATE_BOLD'
ADDED='`2`ADDED_DUPLICATE_BLUE'
READER_CHECKS='''Open native/utf8/rebuilt.mdx in MDict and GoldenDict, then repeat with
native/utf16/rebuilt.mdx. Disable other test dictionaries with overlapping keys.
Each rebuilt dictionary has SEVEN records. Its title is
Combined database workflow · UTF-8 (or UTF-16) and its description is:
Edit, rename, add and delete into database copies.

Headword       Expected result
combined       inline-blue and marker-blue are blue; marker-bold is bold.
duplicate      THREE definitions in order: DUPLICATE_ONE_BLUE (blue),
               EDITED_DUPLICATE_BOLD (bold), ADDED_DUPLICATE_BLUE (blue).
renamed 字      INLINE_BLUE_OK is blue. This was the old inline entry.
multilingual   English, Chinese and Arabic; MULTILINGUAL_BLUE_OK is blue.
empty          Valid entry with an empty definition.
inline         Absent from this dictionary (renamed).
marker         Absent from this dictionary (deleted).

No literal numeric markers should be visible. No MDD is needed.
The automated runner checks raw definitions, duplicate order and exact metadata;
these manual checks qualify actual rendering and lookup in each reader.
Do not compare the original and rebuilt dictionaries as if they were identical:
the original intentionally has the pre-edit entries and original metadata.
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_case(directory,fixture,label,receipts):
    files={n:directory/n for n in ['original.mdx','dictionary.db','metadata.db','definition.db',
                                  'renamed.db','added.db','final.db','rebuilt.mdx','roundtrip.db']}
    assert all(p.is_file() and p.stat().st_size<=128*1024*1024 for p in files.values())
    before={n:sha(p) for n,p in files.items()}
    original_hash,rows,attrs=read_mdx(files['original.mdx'])
    expected=[(r['key'],r['text']) for r in fixture['entries']]
    assert rows==expected, 'Original MDX differs from declarative fixture'
    assert attrs['Encoding']==label and attrs['StyleSheet']==fixture['stylesheet']
    assert attrs['Title']==f'Combined workflow source · {label}' and attrs['Description']==fixture['description']
    assert receipts['encoding']==label.lower().replace('-','')
    imported=check_import(files['dictionary.db'],rows,attrs,original_hash)
    edits={'title':f'Combined database workflow · {label}','description':DESCRIPTION}
    metadata=check_metadata(files['dictionary.db'],files['metadata.db'],edits)
    edited=check_entry(files['metadata.db'],files['definition.db'],'3',EDITED)
    renamed=check_entry(files['definition.db'],files['renamed.db'],'5',expected[4][1],'renamed 字')
    added=check_add(files['renamed.db'],files['added.db'],'duplicate',ADDED)
    deleted=check_delete(files['added.db'],files['final.db'],'6')
    final=expected.copy();final[2]=('duplicate',EDITED);final[4]=('renamed 字',expected[4][1]);final.append(('duplicate',ADDED));del final[5]
    rebuilt_hash,rebuilt_rows,rebuilt_attrs=read_mdx(files['rebuilt.mdx'])
    assert rebuilt_attrs=={**attrs,'Title':edits['title'],'Description':DESCRIPTION}
    assert groups(rebuilt_rows)==groups(final) and len(rebuilt_rows)==7
    # Fixture keys have no Unicode-version-dependent lowercase mappings.
    assert [k for k,_ in rebuilt_rows]==sorted([k for k,_ in final],key=str.lower), 'Rebuilt fixture key order differs'
    rebuilt=check_rebuild(files['final.db'],rebuilt_rows,rebuilt_attrs)
    back=check_import(files['roundtrip.db'],rebuilt_rows,rebuilt_attrs,rebuilt_hash)
    assert groups(rebuilt_rows)['duplicate']==[expected[1][1],EDITED,ADDED]
    assert 'inline' not in groups(rebuilt_rows) and 'marker' not in groups(rebuilt_rows)
    checks=[('import','mdx_to_db',imported),('metadata','db_edit_metadata',metadata),
            ('edit','db_edit_entry',edited),('rename','db_edit_entry',renamed),
            ('add','db_add_entry',added),('delete','db_delete_entry',deleted),
            ('rebuild','db_to_mdx',{'records':7,'source_sha256':before['final.db']}),
            ('back','mdx_to_db',back)]
    for name,operation,oracle in checks:
        receipt=receipts[name]['receipt'];assert receipt['operation']==operation
        for field in ['records','source_sha256','rows_sha256','source_rowid','output_rowid']:
            if field in oracle:assert receipt['value'][field]==oracle[field], (name,field)
    assert receipts['add']['receipt']['value']['output_rowid']=='8'
    assert 'output_rowid' not in receipts['delete']['receipt']['value']
    assert before=={n:sha(p) for n,p in files.items()}, 'Verification changed an artifact'
    return {'status':'passed','encoding':label,'records':7,'initial_import':imported,
            'metadata_oracle':metadata,'edit_oracle':edited,'rename_oracle':renamed,
            'add_oracle':added,'delete_oracle':deleted,'rebuild_oracle':rebuilt,
            'roundtrip_import_oracle':back,'file_sha256':before,'three_duplicate_definitions_preserved':True,
            'renamed_and_deleted_keys_absent':True,'reader_visual_checks':'pending'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('m4-database-out-workflow'))
    a=p.parse_args();out=a.output.resolve()
    if not out.name.startswith('m4-database-out'):p.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-m4-database-workflow-v1','status':'failed','native_tests_executed':False,
            'native_jobs_executed':False,'reader_visual_checks':'pending','steps':[],'checks':[]}
    protected=current=lock_before=None;lock=ROOT/'m4/database/Cargo.lock'
    def source_hashes():
        return {n:h for n,h in sources().items() if '__pycache__' not in Path(n).parts and Path(n).name!='.DS_Store'}
    def run(name,command):
        report['stage']=name;print(name,flush=True)
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=3600)
        (out/(name+'.log')).write_text(done.stdout+'\nSTDERR:\n'+done.stderr,encoding='utf-8')
        report['steps'].append({'name':name,'command':command,'returncode':done.returncode})
        assert done.returncode==0,f'{name} failed; see {out/(name+".log")}'
    try:
        protected,current,lock_before=inventory(),source_hashes(),lock.read_bytes()
        report.update(protected_source_sha256=protected,source_sha256=current,lock_sha256=sha(lock))
        from mdict_utils.base.readmdict import MDX  # Fail early if the independent reader is absent.
        cargo=shutil.which('cargo')
        if not cargo:raise RuntimeError('Run on the Rust-enabled Mac; no native jobs ran here')
        shell_out=out/'m3-shell-out'
        run('desktop-gate',[sys.executable,'scripts/m3_shell.py','--output',str(shell_out)])
        shell=json.loads((shell_out/'m3-shell-report.json').read_text())
        assert shell['status']=='adapter_tests_and_shell_compile_passed_native_launch_pending'
        assert shell['native_tests_executed'] and all(s['returncode']==0 for s in shell['steps'])
        logs='\n'.join(s.get('log_tail','') for s in shell['steps'])
        for name in ['entry_copy_route_cancels_retries_and_rebuilds_selected_definition',
                     'entry_rename_route_cancels_retries_and_resorts_mdx',
                     'entry_delete_route_cancels_retries_and_rebuilds_surviving_duplicate',
                     'entry_add_route_cancels_retries_and_rebuilds_duplicate_order']:
            assert f'{name} ... ok' in logs,f'Required native test did not run: {name}'
        report.update(native_tests_executed=True,shell_report=str(shell_out/'m3-shell-report.json'))
        native=out/'native'
        run('combined-workflow',[cargo,'run','--offline','--locked','--manifest-path',ADAPTER,
                                  '--example','sqlite_workflow','--',str(native)])
        report['native_jobs_executed']=True
        fixture=json.loads((ROOT/'m3/fixtures/database-stylesheet.json').read_text())
        receipts=json.loads((native/'receipts.json').read_text());assert len(receipts)==2
        for label,receipt in zip(['UTF-8','UTF-16'],receipts):
            report['checks'].append(verify_case(native/label.lower().replace('-',''),fixture,label,receipt))
        (out/'reader-checks.txt').write_text(READER_CHECKS,encoding='utf-8')
        report.update(status='database_workflow_native_and_oracle_passed_readers_pending',stage='complete')
    except (Exception,KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        try:
            if protected is not None:assert inventory()==protected,'Protected M2 source changed'
            if current is not None:assert source_hashes()==current,'Qualification sources changed'
            if lock_before is not None:assert lock.read_bytes()==lock_before,'M4 lock changed'
        except Exception as error:report.update(status='failed',error=str(error))
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    return 0 if report['status']=='database_workflow_native_and_oracle_passed_readers_pending' else 1


if __name__=='__main__':raise SystemExit(main())
