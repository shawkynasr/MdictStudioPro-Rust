"""Copy existing resolved locks into a review ZIP without resolving or installing."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile
from m2_closeout import inventory

ROOT=Path(__file__).resolve().parents[1]
LOCKS=('m3/native-adapter/Cargo.lock','m3/txt-runtime/Cargo.lock','m3/export-io/Cargo.lock',
       'm3/indexed-sessions/Cargo.lock','m3/desktop/src-tauri/Cargo.lock',
       'm3/desktop/package-lock.json','m4/database/Cargo.lock')
REFERENCE='docs/evidence/m3-plugin-options-qualified/m3-shell-report.json'
CAP=8*1024*1024

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def collect(root,out,expected):
    captured={};issues=[]
    for name in LOCKS:
        source=root/name
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            issues.append({'path':name,'error':'Lock must be a regular in-project file, not a symlink'});continue
        if not source.is_file():issues.append({'path':name,'error':'Lockfile is missing; no replacement generated'});continue
        if source.stat().st_size>CAP:issues.append({'path':name,'error':'Lockfile exceeds 8 MiB capture limit'});continue
        data=source.read_bytes();before=hashlib.sha256(data).hexdigest()
        try:
            if name.endswith('.json'):json.loads(data)
            else:tomllib.loads(data.decode('utf-8'))
        except (ValueError,UnicodeError) as error:
            issues.append({'path':name,'error':'Invalid lock syntax: '+str(error)});continue
        target=out/'locks'/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as handle:handle.write(data)
        captured[name]={'sha256':before,'bytes':len(data),'copy_sha256':digest(target),
                        'matches_last_reviewed':before==expected.get(name),'expected_sha256':expected.get(name)}
    unchanged=all(digest(root/name)==item['sha256'] for name,item in captured.items())
    return captured,issues,unchanged

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('m3-shell-out-lock-capture'))
    out=parser.parse_args().output.resolve()
    if not out.name.startswith('m3-shell-out'):parser.error('Use a fresh m3-shell-out-prefixed output folder')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-mac-lock-capture-v1','status':'failed','dependencies_resolved':False,
            'build_executed':False,'production_release_ready':False,'locks':{},'issues':[]}
    try:
        protected=inventory();report['protected_source_sha256']=protected
        reference=json.loads((ROOT/REFERENCE).read_text());expected=dict(reference['locks'])
        expected['m4/database/Cargo.lock']=json.loads((ROOT/'m4/sqlite-registry.json').read_text())['source_lock_sha256']
        report['reference_report_sha256']=digest(ROOT/REFERENCE)
        report['capture_script_sha256']=digest(Path(__file__))
        captured,issues,unchanged=collect(ROOT,out,expected)
        report.update(locks=captured,issues=issues,source_locks_unchanged=unchanged,
                      protected_sources_unchanged=protected==inventory())
        assert unchanged and report['protected_sources_unchanged'],'Source identity changed during capture'
        if issues:report['status']='incomplete_lock_capture'
        else:report['status']='captured_matches_last_reviewed' if all(v['matches_last_reviewed'] for v in captured.values()) else 'captured_lock_changes_require_review'
    except (Exception,KeyboardInterrupt) as error:report['error']=f'{type(error).__name__}: {error}'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    archive=out/'lock-snapshot.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as target:
        target.write(out/'report.json','report.json')
        for path in sorted((out/'locks').rglob('*')) if (out/'locks').exists() else []:
            if path.is_file():target.write(path,path.relative_to(out))
    print(report['status']);print(archive)
    return 0 if report['status'].startswith('captured_') else 1

if __name__=='__main__':raise SystemExit(main())
