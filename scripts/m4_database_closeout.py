"""Audit retained Database evidence and run the final scoped Mac regression."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
from m2_closeout import inventory
from m3_shell import ROOT,sources

MANIFEST='docs/evidence/m4-database-closeout-review/manifest.json'
# A nested archive extraction was present in Mac receipts; it is not a build input.
IGNORED_NON_BUILD_PREFIXES=('m3/desktop/mdict-studio-m0-m1/',)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def production_sources():
    return {n:h for n,h in sources().items() if n.startswith(('m3/','m4/')) and not n.startswith(IGNORED_NON_BUILD_PREFIXES) and '__pycache__' not in Path(n).parts and Path(n).name!='.DS_Store'}


def audit(manifest,root=ROOT,production=None,protected=None):
    def path(name):
        relative=Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts,'Evidence path must stay inside the project'
        p=root/relative
        assert p.resolve().is_relative_to(root.resolve()),'Evidence symlink escapes project'
        return p
    for group in ['evidence_sha256','locks_sha256']:
        assert manifest[group],f'Missing {group}'
        variants={}
        if group=='locks_sha256' and manifest.get('reviewed_lock_normalizations'):
            reviewed=manifest['reviewed_lock_normalizations']
            assert reviewed in manifest['evidence_sha256'],'Lock variants must be evidence-bound'
            variants=json.loads(path(reviewed).read_text())['accepted_sha256']
            assert variants.keys()<=manifest[group].keys(),'Unknown lock variant path'
            for name,values in variants.items():
                assert len(values)==2 and len(set(values))==2 and manifest[group][name] in values,'Invalid seed/resolved lock pair'
        for name,expected in manifest[group].items():
            assert digest(path(name)) in variants.get(name,[expected]),f'{group} changed: {name}' 
    actual=dict(production_sources() if production is None else production)
    optional_present=[]
    if manifest.get('optional_platform_bindings'):
        bindings=json.loads(path(manifest['optional_platform_bindings']).read_text())
        assert bindings['qualified_native_status']=='database_sizing_native_and_oracle_passed'
        for name,item in bindings['files'].items():
            if name in actual:
                assert actual[name]==item['sha256'],f'Qualified platform file changed: {name}'
                optional_present.append(name);del actual[name]
    expected=manifest['qualified_production_sha256']
    missing=sorted(expected.keys()-actual.keys());extra=sorted(actual.keys()-expected.keys())
    changed=sorted(n for n in expected.keys()&actual.keys() if expected[n]!=actual[n])
    assert not (missing or extra or changed),f'Production source mismatch: missing={missing}, extra={extra}, changed={changed}'
    accepted=inventory() if protected is None else protected
    assert accepted==manifest['protected_source_sha256'],'Protected M2 source identities differ'
    report=json.loads(path(manifest['qualified_source_report']).read_text())
    assert report['status']=='database_sizing_native_and_oracle_passed' and report['native_tests_executed'] and report['native_jobs_executed']
    assert all(s['returncode']==0 for s in report['steps'])
    near=next(c for c in report['checks'] if c['case']=='near-limit')
    real=next(c for c in report['checks'] if c['case']=='real')
    assert near['status']=='passed' and near['records']==100000 and near['all_lookup_samples_verified']
    assert real['status']=='passed' and real['records']>0 and real['all_lookup_samples_verified'] and real['source_unchanged']
    assert real['records']==report['preflight']['records_observed'] and real['decoded_bytes']==report['preflight']['decoded_bytes_observed']
    assert report['preflight']['status']=='fits_size_profile' and report['preflight']['scan_complete']
    for name in ['over-count','over-decoded']:
        c=next(c for c in report['checks'] if c['case']==name)
        assert c['status']=='controlled_refusal_verified' and c['code']=='limit_exceeded' and c['no_partial_output'] and c['source_unchanged']
    return {'status':'passed','production_identities':len(actual),'protected_identities':len(accepted),
            'evidence_files':len(manifest['evidence_sha256']),'locks':len(manifest['locks_sha256']),'optional_platform_files_verified':optional_present,
            'real_dictionary_records':real['records'],'real_dictionary_decoded_bytes':real['decoded_bytes'],
            'scope':'Retained evidence integrity and unchanged qualified production; no new native execution implied by this audit alone.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('m4-database-out-closeout'))
    a=p.parse_args();out=a.output.resolve()
    if not out.name.startswith('m4-database-out'):p.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-m4-database-closeout-v1','status':'failed','native_tests_executed':False,
            'native_jobs_executed':False,'production_release_ready':False,'steps':[]}
    before=None;manifest=json.loads((ROOT/MANIFEST).read_text())
    def source_hashes():
        result={n:h for n,h in sources().items() if '__pycache__' not in Path(n).parts and Path(n).name!='.DS_Store'}
        for name in ['README.md','docs/STATUS.json',MANIFEST]:result[name]=digest(ROOT/name)
        return result
    def run(name,command):
        report['stage']=name;print(name,flush=True)
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=3600)
        (out/(name+'.log')).write_text(done.stdout+'\nSTDERR:\n'+done.stderr,encoding='utf-8')
        report['steps'].append({'name':name,'command':command,'returncode':done.returncode})
        if done.returncode:
            report['steps'][-1]['failure_log_tail']=(done.stdout+'\nSTDERR:\n'+done.stderr)[-24000:]
        assert done.returncode==0,f'{name} failed; see {out/(name+".log")}'
    try:
        before=source_hashes();report.update(source_sha256=before,protected_source_sha256=inventory(),
            manifest_sha256=digest(ROOT/MANIFEST),lock_sha256=digest(ROOT/'m4/database/Cargo.lock'))
        report['evidence_audit']=audit(manifest)
        run('baseline',[sys.executable,'-m','unittest','discover','-s','baseline','-v'])
        run('contracts',[sys.executable,'scripts/run_contracts.py'])
        run('historical-evidence',[sys.executable,'scripts/validate_evidence.py'])
        run('reference-sources',[sys.executable,'scripts/check_safari_sources.py'])
        workflow=out/'m4-database-out-workflow'
        run('workflow-and-desktop-regression',[sys.executable,'scripts/m4_database_workflow.py','--output',str(workflow)])
        child=json.loads((workflow/'report.json').read_text())
        assert child['status']=='database_workflow_native_and_oracle_passed_readers_pending'
        assert child['native_tests_executed'] and child['native_jobs_executed'] and len(child['checks'])==2
        assert all(c['status']=='passed' and c['records']==7 and c['three_duplicate_definitions_preserved'] for c in child['checks'])
        assert all(s['returncode']==0 for s in child['steps'])
        report.update(native_tests_executed=True,native_jobs_executed=True,workflow_report=str(workflow/'report.json'),
                      workflow_checks=child['checks'],reader_evidence='Retained prior user confirmation; newly generated artifacts have automated verification only.')
        report['final_evidence_audit']=audit(manifest)
        assert source_hashes()==before,'Qualification sources changed during final regression'
        report.update(status='database_closeout_final_regression_passed_review_pending',stage='complete',
                      scope=manifest['scope'],accepted_prior_checkpoints=manifest['accepted_checkpoints'],
                      limitations=manifest['limitations'])
    except (Exception,KeyboardInterrupt) as error:report.update(status='failed',error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        try:
            if before is not None:assert source_hashes()==before,'Qualification source identities changed'
        except Exception as error:report.update(status='failed',error=str(error))
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    return 0 if report['status']=='database_closeout_final_regression_passed_review_pending' else 1


if __name__=='__main__':raise SystemExit(main())
