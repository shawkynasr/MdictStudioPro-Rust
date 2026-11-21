"""Qualify the shared Rust conversion API without changing qualified crates."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from application_lock import ROOT,MANIFEST,LOCK,check_lock
from moe_fixtures import KINDS,generate,oracle,compare,parse_txt
from m2_text import extended_cedict,load_oracle,oracle_convert
from xlsx_fixtures import oracle as workbook_oracle

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise AssertionError(message)

def protected_sources():
    # Later accepted receipts supersede earlier versions of overlapping files.
    latest={}
    for name in ['m2-xlsx-user-run','m2-moe-user-run']:
        r=json.loads((ROOT/'docs/evidence'/name/('m2-xlsx-report.json' if 'xlsx' in name else 'm2-moe-report.json')).read_text())
        latest.update(r.get('protected_source_sha256',{}));latest.update(r['source_sha256'])
    for name,digest in latest.items():require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return latest

def fingerprints():
    paths=[p for p in (ROOT/'m2/application').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/application').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_application.py',ROOT/'scripts/application_lock.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}

def check_progress(events,publishing,workbook=True):
    require(bool(events),'Missing shared progress events')
    allowed=['reading_workbook','converting','validating_output','publishing']
    sequence=[]
    for p in events:
        require(set(p)=={'job_id','stage','phase','completed','total'} and p['job_id']=='cli-conversion','Shared job identity/schema changed')
        require(p['stage'] in allowed and isinstance(p['phase'],str),'Unknown progress stage/phase')
        require(type(p['completed']) is int and type(p['total']) is int and 0<=p['completed']<=p['total'],'Invalid local progress counters')
        sequence.append(allowed.index(p['stage']))
    require(sequence==sorted(sequence),'Shared stages ran out of order')
    expected={'converting','validating_output'}|({'reading_workbook'} if workbook else set())|({'publishing'} if publishing else set())
    require({p['stage'] for p in events}==expected,'Missing or unexpected progress stage')
    require(sum(p['phase']=='published' for p in events)==int(publishing),'Published event must occur exactly once after commit')
    if publishing:require(events[-1]['stage']=='publishing' and events[-1]['phase']=='published','Commit must be final progress event')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_application_failed','M1':'complete_unchanged','M2_complete':False,'application_runtime_qualified':False,
        'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'shared synchronous conversion API, six converters, staged TXT publication, common errors/progress/cancellation; bounded synthetic inputs',
        'native_readers':'NOT_REQUESTED','dependency_upgrade_allowed':False}
    def run(label,command,parse=False,refusal=None):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True)
        r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict')
        combined=r.stdout+'\nSTDERR:\n'+r.stderr;log.write_text(combined,encoding='utf-8')
        step={'name':label,'returncode':r.returncode,'log':log.name};report['steps'].append(step)
        if refusal:
            if r.returncode!=1 or r.stdout.strip():step['failure_log_tail']=combined[-64000:]
            require(r.returncode==1 and not r.stdout.strip(),f'{label}: wrong refusal; see embedded output or {log.name}')
            error=json.loads(r.stderr.strip().splitlines()[-1])
            require(error.get('status')=='failed' and error['error']['code']==refusal,f'{label}: wrong typed error; return {log.name}')
            step['expected_refusal']=refusal;return None,[]
        if r.returncode!=0:step['failure_log_tail']=combined[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded output or {log.name}')
        events=[]
        for line in r.stderr.splitlines():
            if line.startswith('{'):
                value=json.loads(line)
                if 'job_id' in value:events.append(value)
        return (json.loads(r.stdout) if parse else None),events
    def request_file(label,value):
        path=out/(label+'-request.json');path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');return path
    try:
        require(importlib.metadata.version('openpyxl')=='3.1.5','Use existing .venv with openpyxl==3.1.5')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on the Rust-enabled Mac')
        run('application-tests',[cargo,'test','--locked','--manifest-path',MANIFEST,'--workspace'])
        cmd=[cargo,'run','--locked','--manifest-path',MANIFEST,'--bin','studio-application','--']
        fixture_cases=generate(out/'inputs');cases=[]
        for c in fixture_cases[:2]:
            for kind in KINDS:cases.append((c['name']+'-'+kind,kind,c['file']))
        for name,data in [('baseline',json.loads((ROOT/'baseline/cases.json').read_text())['cedict'].encode()),('extended',extended_cedict())]:
            path=out/'inputs'/('cedict-'+name+'.u8');path.write_bytes(data);cases.append((name+'-cc_cedict','cc_cedict',path))
        for label,kind,source in cases:
            before=sha(source);req={'converter':kind,'input':str(source),'worksheet':None};path=request_file(label,req)
            actual,events=run(label,cmd+['convert',str(path)],parse=True);check_progress(events,False,kind!='cc_cedict')
            (out/(label+'-actual.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n')
            expected_file=out/(label+'-python.txt')
            if kind=='cc_cedict':
                metrics=oracle_convert(load_oracle(),source,expected_file);expected=parse_txt(expected_file.read_bytes())
                require(actual['comments']==metrics['comments'],'CEDICT comments changed at facade')
                require(actual['metrics']=={'primary_entries':metrics['primary_entries'],'traditional_entries':metrics['traditional_entries'],'alias_redirects':0,'skipped_rows_or_lines':metrics['skipped_lines']},'CEDICT metrics changed at facade')
            else:
                expected=oracle(source,kind,expected_file);primary=sum(not e['text'].startswith('@@@LINK=') for e in expected)
                require(actual['metrics']=={'primary_entries':primary,'traditional_entries':0,'alias_redirects':len(expected)-primary,'skipped_rows_or_lines':1} and actual['comments']==[],'MOE metrics changed at facade')
            compare(actual['entries'],expected,kind);require(actual['converter']==kind and actual['txt_profile']=='canonical_v1','Converter/profile identity changed')
            target=out/(label+'-rust.txt');pub_path=request_file(label+'-publish',{'conversion':req,'destination':str(target)})
            published,events=run(label+'-publish',cmd+['publish',str(pub_path)],parse=True);check_progress(events,True,kind!='cc_cedict')
            exact=''.join(e['key']+'\n'+e['text']+'\n</>\n' for e in actual['entries']).encode()
            require(target.read_bytes()==exact,'Shared publication changed conversion bytes');compare(parse_txt(exact),expected,kind)
            require(published['entries']==len(expected) and published['file_bytes']==len(exact) and published['metrics']==actual['metrics'] and published['comments']==actual['comments'],'Published summary differs')
            repeated,_=run(label+'-repeat',cmd+['convert',str(path)],parse=True);require(repeated==actual,'Facade conversion not repeatable')
            if label=='baseline-moe_mini':
                run('existing-output',cmd+['publish',str(pub_path)],refusal='destination_exists');require(target.read_bytes()==exact,'Existing output changed')
            require(sha(source)==before,'Source modified by facade')
            report['checks'].append({'case':label,'status':'original_plugin_content_publication_progress_repeat_passed','entries':len(expected),
                'input_sha256':before,'output_sha256':sha(target),'raw_python_bytes_equal':exact==expected_file.read_bytes()})
        # Exercise the public workbook boundary independently of conversion.
        active=ROOT/'baseline/xlsx-reader-kit/active.xlsx'
        for label,sheet in [('active-workbook',None),('named-workbook','First')]:
            command=cmd+['read-workbook',str(active)]+([] if sheet is None else [sheet]);actual,_=run(label,command,parse=True);expected=workbook_oracle(active,sheet)
            require(all(actual[k]==expected[k] for k in ['sheet_name','headers','rows']),'Shared workbook boundary changed normalization')
            report['checks'].append({'case':label,'status':'workbook_boundary_match'})
        for c in fixture_cases[2:]:
            target=out/(c['name']+'-refused.txt');req={'conversion':{'converter':c['kind'],'input':str(c['file']),'worksheet':None},'destination':str(target)}
            run(c['name'],cmd+['publish',str(request_file(c['name'],req))],refusal=c['refusal']);require(not target.exists(),'Refused conversion published output')
        for label,file,code in [('date-cell','date.xlsx','unsupported_cell'),('invalid-workbook','invalid.xlsx','malformed_workbook')]:
            req={'converter':'moe_mini','input':str(ROOT/'baseline/xlsx-reader-kit'/file),'worksheet':None}
            run(label,cmd+['convert',str(request_file(label,req))],refusal=code)
        run('missing-sheet',cmd+['read-workbook',str(active),'missing'],refusal='sheet_not_found')
        req={'converter':'cc_cedict','input':str(cases[-1][2]),'worksheet':'Sheet'}
        run('cedict-sheet-option',cmd+['convert',str(request_file('cedict-sheet-option',req))],refusal='invalid_input')
        req['converter']='unknown_converter';req['worksheet']=None
        run('unknown-converter',cmd+['convert',str(request_file('unknown-converter',req))],refusal='invalid_input')
        require(protected_sources()==report['protected_source_sha256'],'Qualified sources changed during integration')
        require(fingerprints()==report['source_sha256'],'Application sources/lock changed during integration');check_lock()
        report['application_runtime_qualified']=True;report['status']='m2_shared_application_conversion_passed_remaining_M2_work_pending'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}'
    path=out/'m2-application-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f"{report['status']}: {path}",flush=True);return 0 if report['application_runtime_qualified'] else 1
if __name__=='__main__':raise SystemExit(main())
