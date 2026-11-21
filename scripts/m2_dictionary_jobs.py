"""Qualify native MDX/MDD operations through the background runner."""
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
from m2_jobs import compare_events
from m2_text import boundary_source,reference_rows
from m2_foundation import compare_rows
from m2_resources import compare_resources,verify_extracted
from patched_interop import read_python
from v2_audit import audit

RUNNER_SHA='b2a4d68c6c189fd08802cf11535ba6307a2078be5d69409ef79a497f9336e934'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise AssertionError(message)
def protected_sources():
    report=json.loads((ROOT/'docs/evidence/m2-jobs-user-run/m2-jobs-report.json').read_text())
    expected={**report['protected_source_sha256'],**report['source_sha256']};name='m2/application/src/runner.rs'
    require(sha(ROOT/name)==RUNNER_SHA,'Dictionary dispatch differs from reviewed runner extension')
    expected[name]=RUNNER_SHA
    for name,digest in expected.items():require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return expected
def fingerprints():
    paths=[p for p in (ROOT/'m2/application').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/application').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_dictionary_jobs.py',ROOT/'scripts/m2_resources.py',ROOT/'scripts/v2_audit.py',ROOT/'scripts/patched_interop.py',ROOT/'scripts/m2_foundation.py',ROOT/'baseline/resource-probe/studio-probe.ttf']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def make_cases(out):
    inputs=out/'inputs';inputs.mkdir();source=inputs/'source.txt';source.write_bytes(boundary_source());cases=[]
    for profile in ['canonical_v1','legacy_body_span_v1']:
        for encoding in ['utf8','utf16']:
            label=profile+'-'+encoding;mdx=out/(label+'.mdx');export=out/(label+'-export.txt')
            pack={'operation':'pack_mdx','source':str(source),'destination':str(mdx),'title':'Dictionary jobs 字 العربية','description':'Scoped Studio output','encoding':encoding,'profile':profile}
            cases.append({'label':label+'-pack','request':pack,'profile':profile})
            cases.append({'label':label+'-export','request':{'operation':'export_mdx','source':str(mdx),'destination':str(export),'profile':profile},'profile':profile})
    payloads=[('\\css\\style.css',b'body{color:teal}'),('\\fonts\\probe.ttf',(ROOT/'baseline/resource-probe/studio-probe.ttf').read_bytes()),('\\data\\all.bin',bytes(range(256))),('\\empty.bin',b''),('\\字\\text.txt','字典'.encode()),('\\العربية\\نص.txt','أهلاً'.encode())]
    resources=[];expected=[]
    for i,(key,data) in enumerate(payloads):
        path=inputs/f'resource-{i}.bin';path.write_bytes(data);resources.append({'key':key,'source':path.name});expected.append({'key':key,'bytes':list(data)})
    def manifest(name,rows):
        path=inputs/(name+'.json');path.write_text(json.dumps({'title':'Resource jobs','description':'Synthetic resources','resources':rows},ensure_ascii=False)+'\n');return path
    m=manifest('resources',resources);mdd=out/'resources.mdd';extracted=out/'extracted'
    cases += [{'label':'resources-pack','request':{'operation':'pack_mdd','manifest':str(m),'destination':str(mdd)}},
              {'label':'resources-extract','request':{'operation':'extract_mdd','source':str(mdd),'destination':str(extracted)}}]
    first=cases[0]['request'];export=cases[1]['request'];extract=cases[-1]['request']
    cases += [{'label':'existing-mdx','request':dict(first),'refusal':'destination_exists'},
              {'label':'existing-export','request':dict(export),'refusal':'destination_exists'},
              {'label':'existing-extract','request':dict(extract),'refusal':'destination_exists'}]
    for label,rows,code in [('unsafe',[{'key':'../escape.bin','source':'resource-0.bin'}],'unsafe_path'),
        ('aliases',[{'key':'A/file.bin','source':'resource-0.bin'},{'key':'a/other.bin','source':'resource-0.bin'}],'path_collision'),
        ('missing-resource',[{'key':'data.bin','source':'not-present.bin'}],'io')]:
        path=manifest(label,rows);cases.append({'label':label,'request':{'operation':'pack_mdd','manifest':str(path),'destination':str(out/(label+'.mdd'))},'refusal':code})
    bad=inputs/'bad.txt';bad.write_bytes(b'word\nunterminated\n');req={**first,'source':str(bad),'destination':str(out/'bad.mdx')};cases.append({'label':'malformed-txt','request':req,'refusal':'malformed_source'})
    recovery=out/'recovery.mdx';cases += [{'label':'recovery-pack','request':{**first,'destination':str(recovery)},'profile':'canonical_v1'},
        {'label':'recovery-export','request':{'operation':'export_mdx','source':str(recovery),'destination':str(out/'recovery.txt'),'profile':'canonical_v1'},'profile':'canonical_v1'}]
    return cases,expected,source
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_dictionary_jobs_failed','M1':'complete_unchanged','M2_complete':False,'dictionary_jobs_runtime_qualified':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded Studio MDX TXT pack/export and MDD file-manifest pack/extract through serial background worker','native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True);r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict');combined=r.stdout+'\nSTDERR:\n'+r.stderr
        log.write_text(combined,encoding='utf-8');step={'name':label,'returncode':r.returncode,'log':log.name};report['steps'].append(step)
        if r.returncode!=0:step['failure_log_tail']=combined[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded output or {log.name}');return json.loads(r.stdout) if parse else None
    try:
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing venv mdict-utils==1.3.14')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on the Rust-enabled Mac')
        run('dictionary-background-tests',[cargo,'test','--locked','--manifest-path',MANIFEST,'--workspace'])
        cases,expected_resources,source=make_cases(out);hashes={str(p):sha(p) for p in (out/'inputs').iterdir() if p.is_file()}
        batch=out/'batch.json';batch.write_text(json.dumps([c['request'] for c in cases],ensure_ascii=False,indent=2)+'\n')
        actual=run('dictionary-background-batch',[cargo,'run','--locked','--manifest-path',MANIFEST,'--bin','studio-dictionary-jobs-probe','--',str(batch)],True)
        (out/'background-actual.json').write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n');require(actual['worker_joined'] and len(actual['jobs'])==len(cases),'Dictionary batch did not finish and join')
        compare_events(actual['events'],actual['jobs']);report['events_delivered']=len(actual['events'])
        for c,job in zip(cases,actual['jobs']):
            req=c['request'];target=Path(req['destination']);require(job['operation']==req['operation'] and job['output'] is None,'Dictionary result confused with converter output')
            if c.get('refusal'):
                require(job['state']=='failed' and job['error']['code']==c['refusal'] and not job['error']['publication_uncertain'] and job['dictionary_output'] is None,f'{c["label"]}: wrong failure; return background-actual.json')
                if not c['label'].startswith('existing-'):require(not target.exists(),'Failed dictionary job published output')
                report['checks'].append({'case':c['label'],'status':'expected_failed_job','code':c['refusal']});continue
            require(job['state']=='succeeded' and job['error'] is None and not job['cancel_requested'],f'{c["label"]}: dictionary job failed; return background-actual.json')
            summary=job['dictionary_output'];require(summary['operation']==req['operation'] and summary['destination']==str(target),'Wrong dictionary output summary')
            require(job['latest_progress']['stage']=='publishing' and job['latest_progress']['phase']=='published','Dictionary commit progress missing')
            operation=req['operation'];check={'case':c['label'],'status':'passed','operation':operation}
            if operation=='pack_mdx':
                expected=reference_rows(source.read_bytes(),c['profile']);rows=read_python(target,'mdx');compare_rows(expected,rows)
                wire=audit(target);require(wire['status']=='structural_audit_passed','MDX independent wire audit failed')
                require(summary['entries']==len(expected) and summary['file_bytes']==target.stat().st_size and summary['policy']=='unicode16-literal-v1','MDX summary/policy differs')
                check.update(entries=len(rows),output_sha256=sha(target),wire_audit='passed',independent_python='passed')
            elif operation=='export_mdx':
                rows=read_python(Path(req['source']),'mdx');data=target.read_bytes();compare_rows([{'key':k,'text':v} for k,v in rows],[(e['key'],e['text']) for e in reference_rows(data,c['profile'])])
                exact=''.join(k+'\n'+v+('\n' if c['profile']=='canonical_v1' else '')+'</>\n' for k,v in rows).encode();require(data==exact,'Export changed physical entry order or TXT framing')
                require(summary['entries']==len(rows) and summary['file_bytes']==len(data) and summary['profile']==c['profile'],'Export summary differs');check.update(entries=len(rows),output_sha256=sha(target),bytes_exact=True)
            elif operation=='pack_mdd':
                compare_resources(expected_resources,read_python(target,'mdd'));wire=audit(target);require(wire['status']=='structural_audit_passed','MDD independent wire audit failed')
                require(summary['resources']==6 and summary['file_bytes']==target.stat().st_size and summary['policy']=='unicode16-resources-v1','MDD summary differs');check.update(resources=6,output_sha256=sha(target),wire_audit='passed',independent_python='passed')
            else:
                inventory=verify_extracted(target,expected_resources);require(summary['resources']==6 and summary['payload_bytes']==sum(len(r['bytes']) for r in expected_resources),'Extraction summary differs');check.update(resources=6,inventory=inventory)
            report['checks'].append(check)
        require(all(sha(Path(p))==h for p,h in hashes.items()),'Dictionary input files changed')
        verify_extracted(out/'extracted',expected_resources)
        require(not any(p.name.startswith(('.tmp','.studio-extract-')) for p in out.iterdir()),'Staging artifacts leaked')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during dictionary job batch');check_lock()
        report['dictionary_jobs_runtime_qualified']=True;report['status']='m2_dictionary_background_jobs_passed_remaining_M2_work_pending'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}'
    dest=out/'m2-dictionary-jobs-report.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {dest}",flush=True);return 0 if report['dictionary_jobs_runtime_qualified'] else 1
if __name__=='__main__':raise SystemExit(main())
