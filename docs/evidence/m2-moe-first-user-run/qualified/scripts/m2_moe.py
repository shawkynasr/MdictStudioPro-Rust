"""Qualify all five Rust MOE ports against the original Python plugins."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from m2_xlsx import ROOT,MANIFEST,LOCK,protected_sources,check_lock
from moe_fixtures import KINDS,generate,oracle,compare,parse_txt

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fingerprints():
    paths=[p for p in (ROOT/'m2/xlsx-reader').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/xlsx-reader').parts and p.suffix in {'.rs','.toml','.lock','.html'}]
    paths += [ROOT/'scripts/m2_moe.py',ROOT/'scripts/moe_fixtures.py',ROOT/'baseline/capture.py',ROOT/'baseline/cases.json',ROOT/'baseline/legacy/excel_utils.py',ROOT/'baseline/moe-converter-kit/expected.json']
    paths += [p for p in (ROOT/'baseline/legacy/plugins').glob('*.py')]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def require(condition,message):
    if not condition:raise AssertionError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_moe_failed','M1':'complete_unchanged','M2_complete':False,'Rust_MOE_ports_runtime_qualified':False,
        'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'profile':'moe-legacy-layout-v1-first-seen','native_readers':'NOT_REQUESTED',
        'intentional_difference':'Original unordered set iteration becomes first-seen order; comparator ignores only set-derived reference/alias order',
        'scope':'bounded synthetic common-cell XLSX conversion; ASCII numeric syntax and marker filenames; not full real MOE corpus'}
    def run(label,cmd,parse=False,refusal=None):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True)
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict')
        log.write_text(r.stdout+'\nSTDERR:\n'+r.stderr,encoding='utf-8');step={'name':label,'returncode':r.returncode,'log':log.name};report['steps'].append(step)
        if refusal:
            require(r.returncode==1 and not r.stdout.strip(),f'{label}: expected clean refusal; return {log.name}')
            error=json.loads(r.stderr.strip().splitlines()[-1]);require(error['error']['code']==refusal,f'{label}: wrong refusal; return {log.name}');step['expected_refusal']=refusal;return None
        require(r.returncode==0,f'{label} failed; return {log.name}');return json.loads(r.stdout) if parse else None
    try:
        require(importlib.metadata.version('openpyxl')=='3.1.5','Use existing .venv with openpyxl==3.1.5')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints()
        report['dependency_packages']=check_lock((ROOT/LOCK).read_text())
        previous=json.loads((ROOT/'docs/evidence/m2-xlsx-user-run/m2-xlsx-report.json').read_text())
        require(sha(ROOT/LOCK)==previous['source_sha256'][LOCK],'Qualified XLSX dependency lock changed')
        report['qualified_xlsx_lock_unchanged']=True
        cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        run('moe-and-reader-tests',[cargo,'test','--locked','--manifest-path',MANIFEST,'--workspace'])
        moe=[cargo,'run','--locked','--manifest-path',MANIFEST,'--bin','studio-moe','--']
        cli=[cargo,'run','--locked','--manifest-path','m2/Cargo.toml','-p','studio-cli','--']
        for case in generate(out/'inputs'):
            source=case['file'];before=sha(source)
            if case.get('refusal'):
                run(case['name'],moe+[case['kind'],str(source)],refusal=case['refusal'])
                report['checks'].append({'case':case['name'],'status':'expected_refusal','code':case['refusal'],'input_sha256':before})
            else:
                for kind in KINDS:
                    label=case['name']+'-'+kind;actual=run(label,moe+[kind,str(source)],parse=True)
                    actual_file=out/(label+'-actual.json');actual_file.write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n')
                    expected=oracle(source,kind,out/(label+'-python.txt'))
                    try:compare(actual['entries'],expected,kind)
                    except AssertionError as e:raise AssertionError(f'{e}; return {label}-actual.json and {label}-python.txt') from e
                    require(actual['txt_profile']=='canonical_v1' and actual['profile']==report['profile'],'Wrong conversion profile')
                    primary=sum(not e['text'].startswith('@@@LINK=') for e in expected)
                    require(actual['primary_entries']==primary and actual['alias_redirects']==len(expected)-primary,'Incorrect conversion metrics')
                    rows=out/(label+'-rows.json');rows.write_text(json.dumps(actual['entries'],ensure_ascii=False)+'\n')
                    target=out/(label+'-rust.txt');run(label+'-publish',cli+['txt-write',str(rows),str(target),'canonical_v1'],parse=True)
                    compare(parse_txt(target.read_bytes()),expected,kind)
                    # Publication must preserve exactly the converter's own
                    # canonical bytes, including Mini's multiline head.
                    exact=''.join(e['key']+'\n'+e['text']+'\n</>\n' for e in actual['entries']).encode()
                    require(target.read_bytes()==exact,'TXT publication changed converter bytes')
                    if case['name']=='baseline':compare(parse_txt((ROOT/'baseline/expected'/f'{kind}.txt').read_bytes()),expected,kind)
                    again=run(label+'-repeat',moe+[kind,str(source)],parse=True)
                    require(again==actual,'Rust converter ordering is not deterministic')
                    if case['name']=='baseline' and kind=='moe_mini':
                        run('no-overwrite',cli+['txt-write',str(rows),str(target),'canonical_v1'],refusal='destination_exists')
                        require(target.read_bytes()==exact,'Refused publication modified existing output')
                    report['checks'].append({'case':label,'status':'original_plugin_content_and_TXT_publication_match','entries':len(expected),
                        'primary_entries':primary,'alias_redirects':len(expected)-primary,'input_sha256':before,'output_sha256':sha(target),
                        'raw_python_bytes_equal':target.read_bytes()==(out/(label+'-python.txt')).read_bytes(),'deterministic_repeat':True})
            require(sha(source)==before,'Converter modified its source workbook')
        require(fingerprints()==report['source_sha256'],'Source changed during qualification')
        require(protected_sources()==report['protected_source_sha256'],'Qualified core/oracle changed')
        report['Rust_MOE_ports_runtime_qualified']=True
        report['status']='m2_five_MOE_ports_synthetic_parity_passed_remaining_M2_work_pending'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}'
    dest=out/'m2-moe-report.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f"{report['status']}: {dest}",flush=True)
    return 0 if report['Rust_MOE_ports_runtime_qualified'] else 1
if __name__=='__main__':raise SystemExit(main())
