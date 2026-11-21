"""Qualify background execution and bounded GUI event delivery on the Mac."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from application_lock import ROOT,MANIFEST,check_lock
from moe_fixtures import KINDS,generate,oracle,compare,parse_txt
from m2_text import extended_cedict,load_oracle,oracle_convert

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise AssertionError(message)
def protected_sources():
    report=json.loads((ROOT/'docs/evidence/m2-application-user-run/m2-application-report.json').read_text())
    expected={**report['protected_source_sha256'],**report['source_sha256']}
    # One intentional public module export; the qualified facade body is exact.
    name='m2/application/src/lib.rs';archived=ROOT/'docs/evidence/m2-application-user-run/qualified'/name
    require((ROOT/name).read_bytes()==archived.read_bytes()+b'\npub mod runner;\n','Qualified application changed beyond the explicit runner export')
    expected[name]=sha(ROOT/name)
    for name,digest in expected.items():require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return expected
def fingerprints():
    paths=[p for p in (ROOT/'m2/application').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/application').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_jobs.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}

def compare_events(events,results):
    finals={r['job_id']:r for r in results};last={};terminal=set()
    require(len(finals)==len(results),'Duplicate job IDs')
    for event in events:
        name=event['job_id'];require(name in finals,'Event leaked another job identity')
        require(type(event['revision']) is int and event['revision']>last.get(name,0),'Event revision did not advance')
        require(name not in terminal,'Event after terminal result');last[name]=event['revision']
        if event['state'] in ['succeeded','failed','cancelled']:
            require(event==finals[name],'Terminal event differs from retained status');terminal.add(name)
        p=event['latest_progress']
        if p is not None:require(p['job_id']==name,'Progress leaked another job identity')
    require(terminal==set(finals),'Polling lost a terminal event')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_jobs_failed','M1':'complete_unchanged','M2_complete':False,'background_runtime_qualified':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'one serial worker, bounded pending/retained jobs, coalesced polling, cancellation and shutdown; bounded native TXT conversion jobs','native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True)
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict');combined=r.stdout+'\nSTDERR:\n'+r.stderr
        log.write_text(combined,encoding='utf-8');step={'name':label,'returncode':r.returncode,'log':log.name};report['steps'].append(step)
        if r.returncode!=0:step['failure_log_tail']=combined[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded output or {log.name}')
        return json.loads(r.stdout) if parse else None
    try:
        require(importlib.metadata.version('openpyxl')=='3.1.5','Use existing .venv with openpyxl==3.1.5')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on the Rust-enabled Mac')
        run('background-and-application-tests',[cargo,'test','--locked','--manifest-path',MANIFEST,'--workspace'])
        fixtures=generate(out/'inputs');cases=[];requests=[];input_hashes={}
        for c in fixtures[:2]:
            for kind in KINDS:cases.append({'label':c['name']+'-'+kind,'kind':kind,'source':c['file']})
        for label,data in [('baseline',json.loads((ROOT/'baseline/cases.json').read_text())['cedict'].encode()),('extended',extended_cedict())]:
            source=out/'inputs'/('cedict-'+label+'.u8');source.write_bytes(data);cases.append({'label':label+'-cc_cedict','kind':'cc_cedict','source':source})
        for c in fixtures[2:]:cases.append({'label':c['name'],'kind':c['kind'],'source':c['file'],'refusal':c['refusal']})
        existing=out/'existing.txt';existing.write_bytes(b'KEEP EXISTING OUTPUT\n')
        cases.append({'label':'existing-output','kind':'moe_mini','source':fixtures[0]['file'],'refusal':'destination_exists','destination':existing})
        for c in cases:
            target=c.get('destination',out/(c['label']+'-rust.txt'));c['target']=target;input_hashes[str(c['source'])]=sha(c['source'])
            requests.append({'conversion':{'converter':c['kind'],'input':str(c['source']),'worksheet':None},'destination':str(target)})
        batch=out/'batch.json';batch.write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n')
        actual=run('background-batch',[cargo,'run','--locked','--manifest-path',MANIFEST,'--bin','studio-jobs-probe','--',str(batch)],True)
        (out/'background-actual.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n')
        require(actual['worker_joined'] is True and len(actual['jobs'])==len(cases),'Worker batch did not finish and join')
        compare_events(actual['events'],actual['jobs']);report['events_delivered']=len(actual['events'])
        for c,job in zip(cases,actual['jobs']):
            require(job['cancel_requested'] is False,'Batch unexpectedly requested cancellation')
            if c.get('refusal'):
                require(job['state']=='failed' and job['error']['code']==c['refusal'] and job['error']['publication_uncertain'] is False and job['output'] is None,'Incorrect background failure state')
                if c['label']=='existing-output':require(existing.read_bytes()==b'KEEP EXISTING OUTPUT\n','Existing output replaced')
                else:require(not c['target'].exists(),'Failed job published output')
                report['checks'].append({'case':c['label'],'status':'expected_failed_job','code':c['refusal'],'job_id':job['job_id']});continue
            require(job['state']=='succeeded' and job['error'] is None,'Background conversion did not succeed')
            output=job['output'];require(output['destination']==str(c['target']) and output['converter']==c['kind'],'Background output associated with wrong request')
            require(job['latest_progress']['stage']=='publishing' and job['latest_progress']['phase']=='published','Missing committed progress state')
            expected_file=out/(c['label']+'-python.txt')
            if c['kind']=='cc_cedict':
                metrics=oracle_convert(load_oracle(),c['source'],expected_file);expected=parse_txt(expected_file.read_bytes())
                require(output['primary_entries']==metrics['primary_entries'] and output['traditional_entries']==metrics['traditional_entries'] and output['skipped_rows_or_lines']==metrics['skipped_lines'] and output['alias_redirects']==0,'Background CEDICT metrics changed')
            else:
                expected=oracle(c['source'],c['kind'],expected_file);primary=sum(not e['text'].startswith('@@@LINK=') for e in expected)
                require(output['primary_entries']==primary and output['alias_redirects']==len(expected)-primary and output['traditional_entries']==0 and output['skipped_rows_or_lines']==1,'Background MOE metrics changed')
            data=c['target'].read_bytes();compare(parse_txt(data),expected,c['kind'])
            require(output['entries']==len(expected) and output['file_bytes']==len(data),'Background output summary changed')
            report['checks'].append({'case':c['label'],'status':'background_content_metrics_and_publication_passed','job_id':job['job_id'],'entries':len(expected),'output_sha256':sha(c['target']),'raw_python_bytes_equal':data==expected_file.read_bytes()})
        require(all(sha(Path(p))==digest for p,digest in input_hashes.items()),'Source workbook/text changed')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during job batch');check_lock()
        report['background_runtime_qualified']=True;report['status']='m2_background_jobs_passed_remaining_M2_work_pending'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}'
    dest=out/'m2-jobs-report.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {dest}",flush=True)
    return 0 if report['background_runtime_qualified'] else 1
if __name__=='__main__':raise SystemExit(main())
