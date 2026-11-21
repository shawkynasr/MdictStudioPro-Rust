"""Qualify synchronous application composition and serial background imports."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import importlib.metadata
import locale
from m2_v2_import import ROOT,require,compare_header,compare_query
from v2_import_lock import MANIFEST,LOCK,check_lock
from v2_import_fixtures import generate,QUERIES,REDIRECTS,lookup,resolve

LIB='m2/v2-import/src/lib.rs'
EXTENSION=b'\npub mod application;\n'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def protected_sources():
    directory=ROOT/'docs/evidence/m2-v2-import-user-run';report=json.loads((directory/'m2-v2-import-report.json').read_text())
    expected={**report['protected_source_sha256'],**report['source_sha256']}
    for name,digest in expected.items():
        if name==LIB:
            previous=(directory/'qualified'/name).read_bytes()
            require(hashlib.sha256(previous).hexdigest()==digest,'Accepted reader snapshot changed')
            require((ROOT/name).read_bytes()==previous+EXTENSION,'Reader lib changed beyond application module export')
        else:require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return {name:sha(ROOT/name) for name in expected}
def fingerprints():
    paths=[p for p in (ROOT/'m2/v2-import').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/v2-import').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_import_jobs.py',ROOT/'scripts/test_m2_import_jobs.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def request_for(case):
    actions=([{'action':'lookup','query':q} for q in QUERIES]+[{'action':'resolve','query':q} for q in REDIRECTS]) if case['kind']=='mdx' else [{'action':'resource','query':q} for q in ['\\data\\dup.bin','empty.bin','../raw.bin','missing']]
    return {'path':str(case['path']),'source':{'kind':'mdx','policy':case['policy']} if case['kind']=='mdx' else {'kind':'mdd'},'actions':actions,'max_hops':case.get('max_hops'),'max_results':case.get('max_results'),'max_entries':case.get('max_entries')}
def compare_response(response,case,request):
    compare_header(response['header'],case['path'])
    rows=case['rows'] if case['kind']=='mdx' else case['resources']
    require(response['records']==len(rows),'Wrong imported record count')
    require(response['policy']==('raw-exact-v1' if case.get('policy')=='raw_exact' else 'header-ascii-strip-unicode16-v1') if case['kind']=='mdx' else response['policy']=='resource-raw-exact-v1','Wrong policy identity')
    require([item['request'] for item in response['results']]==request['actions'],'Missing/reordered application actions')
    counts={'exact_query_result':0,'expected_query_error':0,'resource_queries':0}
    for item in response['results']:
        action=item['request'];outcome=item['outcome'];query=action['query']
        if action['action']=='resource':
            require(outcome['status']=='resources' and outcome['resources']==[r for r in rows if r['key']==query],'MDD resource reply changed bytes/order');counts['resource_queries']+=1
        else:
            operation=lookup if action['action']=='lookup' else resolve
            expected_kind='entries' if action['action']=='lookup' else 'resolutions'
            require(outcome['status'] in {expected_kind,'error'},'Unexpected typed query outcome')
            options={'max_results':case.get('max_results',256)}
            if action['action']=='resolve':options['max_hops']=case.get('max_hops',16)
            result=compare_query(outcome,lambda:operation(rows,query,case['policy'],case['case_sensitive'],case['strip'],**options));counts[result]+=1
    return counts
def validate_background(actual):
    terminal=actual['terminal'];collected=actual['collected'];success=actual['state']=='succeeded'
    require(terminal['state']==actual['state'] and terminal['operation'] in {'import_mdx','import_mdd'},'Background terminal identity differs')
    require(terminal['result_available']==success and not collected['result_available'],'Reply retention/transfer differs')
    require(actual['taken_once'] and actual['forgotten'] and actual['late_cancel']=='already_finished','Reply ownership or terminal lifecycle differs')
    require(len(actual['events'])==1 and actual['events'][0]['job_id']==terminal['job_id'],'Mailbox failed to coalesce to one retained job')
    require(all(p is None or p['job_id']==terminal['job_id'] for p in [terminal['latest_progress'],collected['latest_progress']]),'Progress belongs to wrong job')
    require((actual['response'] is not None)==success,'Failed job exposed partial reply')
    if success:
        size=len(json.dumps(actual['response'],ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        require(terminal['result_bytes']==size and size<=2*1024*1024,'Serialized reply accounting differs')
    else:require(terminal['error']==actual['error'],'Typed background failure changed')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_import_jobs_failed','M1':'complete_unchanged','M2_complete':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded one-shot synchronous and serial background ordinary v2 import/query composition; separate import worker, unchanged conversion/packing runner','native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False):
        print(f'Running {label}',flush=True);r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8');text=r.stdout+'\nSTDERR:\n'+r.stderr
        (out/(label+'.log')).write_text(text);step={'name':label,'returncode':r.returncode};report['steps'].append(step)
        if r.returncode:step['failure_log_tail']=text[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded log tail');return json.loads(r.stdout) if parse else None
    try:
        report['stage']='preflight';require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing .venv mdict-utils==1.3.14');locale.setlocale(locale.LC_COLLATE,'C')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_contents']=(ROOT/LOCK).read_text()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        report['stage']='rust_tests';run('refresh-import-artifacts',[cargo,'clean','--locked','--offline','--manifest-path',MANIFEST,'--package','studio-v2-import'])
        run('import-application-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace'])
        report['stage']='fixture_generation';cases=generate(out/'inputs')
        extra={**cases[0],'name':'aggregate-reply-budget','max_reply_bytes':1,'refusal':'limit_exceeded'};cases.append(extra)
        command=[cargo,'run','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-import-jobs','--']
        for case in cases:
            report['stage']=case['name'];request=request_for(case)
            if 'max_reply_bytes' in case:request['max_reply_bytes']=case['max_reply_bytes']
            path=out/(case['name']+'-request.json');path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n');before=sha(case['path'])
            sync=run(case['name']+'-sync',command+['sync',str(path)],True);background=run(case['name']+'-background',command+['background',str(path)],True)
            (out/(case['name']+'-actual.json')).write_text(json.dumps({'sync':sync,'background':background},ensure_ascii=False,indent=2)+'\n');validate_background(background)
            require(sync['state']==background['state'],'Sync/background terminal states differ')
            if case.get('refusal'):
                require(sync['state']=='failed' and sync['error']['code']==background['error']['code']==case['refusal'],'Wrong typed import refusal')
                require(sync['error']['detail']==background['error']['detail'],'Sync/background failure detail differs');counts={};status='expected_job_failure'
            else:
                require(sync['state']=='succeeded' and sync['response']==background['response'],'Sync/background payload differs')
                counts=compare_response(sync['response'],case,request);status='sync_background_oracle_passed'
            require(sha(case['path'])==before,'Source dictionary changed');report['checks'].append({'case':case['name'],'status':status,'query_checks':counts,'input_sha256':before})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Source identities changed during qualification');check_lock()
        report['status']='m2_import_application_background_jobs_passed_remaining_M2_work_pending';report['stage']='complete'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
    path=out/'m2-import-jobs-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_import_jobs_failed')
if __name__=='__main__':raise SystemExit(main())
