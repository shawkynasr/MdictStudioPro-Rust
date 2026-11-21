"""Qualify the isolated Rust XLSX reader against the captured openpyxl helper."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib

from patched_interop import ROOT,require
from xlsx_fixtures import generate,oracle

MANIFEST='m2/xlsx-reader/Cargo.toml'
LOCK='m2/xlsx-reader/Cargo.lock'
PINS={'calamine':'0.31.0','quick-xml':'0.38.3','zip':'4.6.1','serde':'1.0.229','serde_json':'1.0.154'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_sources():
    qualified=json.loads((ROOT/'docs/evidence/m2-text-user-run/m2-text-report.json').read_text())['source_sha256']
    for name,expected in qualified.items():require(sha(ROOT/name)==expected,f'Qualified core/oracle changed: {name}')
    locks=['Cargo.lock','experiments/legacy-sort/Cargo.lock','experiments/real-rebuild/Cargo.lock','m2/Cargo.lock']
    return {**qualified,**{name:sha(ROOT/name) for name in locks}}


def source_fingerprints():
    paths=[p for p in (ROOT/'m2/xlsx-reader').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/xlsx-reader').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_xlsx.py',ROOT/'scripts/xlsx_fixtures.py',ROOT/'baseline/legacy/excel_utils.py',ROOT/'baseline/cases.json']
    paths += [p for p in (ROOT/'baseline/xlsx-reader-kit').iterdir() if p.is_file()]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}


def check_reader_manifest():
    manifest=tomllib.loads((ROOT/MANIFEST).read_text())
    require(manifest['package']['name']=='studio-xlsx' and manifest['workspace']['members']==['.'],'XLSX crate must remain an isolated workspace')
    for name,pin in PINS.items():
        dependency=manifest['dependencies'][name]
        require((dependency if isinstance(dependency,str) else dependency['version'])=='='+pin,f'Expected exact reader pin: {name}={pin}')


def check_lock(contents):
    packages=tomllib.loads(contents)['package']
    for name,version in PINS.items():
        found=[p for p in packages if p['name']==name]
        require(len(found)==1 and found[0]['version']==version and len(found[0].get('checksum',''))==64,f'Reader lock does not preserve direct pin {name}={version}')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in packages]


def compare_table(actual,expected):
    require(actual['profile']=='openpyxl-values-v1','Unknown XLSX normalization profile')
    require(actual['sheet_name']==expected['sheet_name'],'Active/named worksheet selection differs')
    require(actual['headers']==expected['headers'],'Header normalization or geometry differs')
    require(actual['rows']==expected['rows'],'Normalized rows differ (including blanks, duplicate keys or numeric text)')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_xlsx_failed','M1':'complete_unchanged','M2_complete':False,'Rust_MOE_converters_ported':False,
        'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded common-cell XLSX compatibility; dates/durations explicitly unsupported','native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False,refusal=None):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict')
        log.write_text(result.stdout+'\nSTDERR:\n'+result.stderr,encoding='utf-8')
        step={'name':label,'returncode':result.returncode,'log':log.name};report['steps'].append(step)
        if refusal:
            require(result.returncode==1 and not result.stdout.strip(),f'{label} did not refuse cleanly; return {log.name}')
            error=json.loads(result.stderr.strip().splitlines()[-1]);require(error.get('status')=='failed' and error['error']['code']==refusal,f'{label} refused for wrong reason; return {log.name}')
            step['expected_refusal']=refusal;return None
        require(result.returncode==0,f'{label} failed; return {log.name}')
        return json.loads(result.stdout) if parse else None
    try:
        require(importlib.metadata.version('openpyxl')=='3.1.5','Use existing .venv with openpyxl==3.1.5')
        check_reader_manifest();report['protected_source_sha256']=protected_sources()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on the Rust-enabled Mac')
        lock=ROOT/LOCK
        if not lock.exists():
            run('reader-lock-resolve',[cargo,'generate-lockfile','--manifest-path',MANIFEST])
            report['dependency_lock_created']=True
        else:report['dependency_lock_created']=False
        # Return the complete generated lock so the exact new dependency graph
        # can be reviewed and retained without asking for a second upload.
        report['dependency_lock_contents']=lock.read_text(encoding='utf-8')
        report['dependency_packages']=check_lock(report['dependency_lock_contents'])
        report['source_sha256']=source_fingerprints()
        run('xlsx-tests',[cargo,'test','--locked','--manifest-path',MANIFEST,'--workspace'])
        fixtures=out/'inputs';cases=generate(fixtures)
        command=[cargo,'run','--locked','--manifest-path',MANIFEST,'--bin','studio-xlsx','--','read']
        for case in cases:
            source=fixtures/case['file'];before=sha(source);cmd=command+[str(source)]
            if case['sheet'] is not None:cmd.append(case['sheet'])
            actual=run(case['name'],cmd,parse=not case['refusal'],refusal=case['refusal'])
            if case['refusal']:
                report['checks'].append({'case':case['name'],'status':'expected_refusal','code':case['refusal'],'input_sha256':before})
            else:
                expected=oracle(source,case['sheet'])
                expected_path=out/(case['name']+'-expected.json');actual_path=out/(case['name']+'-actual.json')
                expected_path.write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                actual_path.write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                try:compare_table(actual,expected)
                except AssertionError as error:raise AssertionError(f'{error}; return {case["name"]}-expected.json and {case["name"]}-actual.json') from error
                report['checks'].append({'case':case['name'],'status':'exact_rows_and_headers','sheet_name':actual['sheet_name'],
                    'rows':len(actual['rows']),'headers':len(actual['headers']),'input_sha256':before,
                    'normalized_rows_sha256':hashlib.sha256(json.dumps(expected['rows'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()})
            require(sha(source)==before,'Reader or oracle modified a fixture')
        require(source_fingerprints()==report['source_sha256'],'XLSX source/dependency lock changed during verification')
        require(protected_sources()==report['protected_source_sha256'],'Qualified dictionary workspaces changed during XLSX verification')
        report['status']='m2_xlsx_common_cells_passed_MOE_ports_and_date_profile_pending'
    except (Exception,KeyboardInterrupt) as error:report['error']=f'{type(error).__name__}: {error}'
    destination=out/'m2-xlsx-report.json';destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {destination}",flush=True)
    return 0 if report['status']=='m2_xlsx_common_cells_passed_MOE_ports_and_date_profile_pending' else 1


if __name__=='__main__':raise SystemExit(main())
