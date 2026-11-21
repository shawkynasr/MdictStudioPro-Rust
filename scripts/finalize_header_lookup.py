"""Finish the known header batch after correcting its conflict-message checker.

Reuse verified fixture bytes and observations. Re-run only the conflict refusal.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from header_lookup import entries,rewrite_header,validate_literal,conflict_rejected,publish_candidates
from patched_interop import ROOT,require
from real_corpus import file_hash
from real_rebuild import run,stop


def finalize(out,timeout):
    require(timeout>0,'Timeout must be positive')
    evidence=ROOT/'docs/evidence/header-lookup-user-run'
    report_path=out/'header-lookup-report.json';original=report_path.read_bytes();report=json.loads(original)
    require(file_hash(report_path)==file_hash(evidence/'header-lookup-report.json'),'Resume accepts only the received, source-bound failed report')
    require(report['status']=='failed_header_lookup_qualification' and report['error']=='Conflicting flags were not rejected before rows/lookup','Unexpected failure to resume')
    require(not (out/'native-candidates').exists() and not (out/'native-checklist.csv').exists(),'Native outputs already exist; refusing overwrite')
    backup=out/'header-lookup-report.before-finalize.json';require(not backup.exists(),'Resume backup already exists; refusing overwrite')
    for name,expected in report['source_sha256'].items():
        path=evidence/'qualified-header_lookup.py' if name=='scripts/header_lookup.py' else ROOT/name
        require(file_hash(path)==expected,f'Qualified source changed: {name}')
    require(set(report['checks'])=={'literal-utf8','literal-utf16'},'Incomplete literal matrix')
    require(set(report['alias_checks'])=={'alias-no','alias-yes'} and all(c['status']=='passed' and c['lookup_and_rows_equal'] for c in report['alias_checks'].values()),'Alias checks did not pass')
    require(report['flag_only_negative_control']['status']=='passed_mismatch_detected','Ordering negative control did not pass')
    paths={};observations={};rows=entries()
    queries=list(dict.fromkeys(r['key'] for r in rows))+['missing','aPpLe','a?b','DUPLICATE','edge?031','A\\B']
    for name,encoding in [('literal-utf8','utf8'),('literal-utf16','utf16')]:
        path=out/name/'policy.mdx';paths[name]=path
        require(file_hash(path)==report['checks'][name]['sha256'],f'Qualified dictionary changed: {name}')
        spec=json.loads((out/f'{name}.json').read_text(encoding='utf-8'))
        require(spec=={'entries':rows,'queries':queries,'profile':'literal','encoding':encoding,'title':'07-header-'+name},'Saved specification differs')
        observed=json.loads((out/f'{name}-observations.json').read_text(encoding='utf-8'));observations[name]=observed
        # Check the existing small files and saved observations; no Rust lookup
        # matrix or dictionary generation is repeated.
        require(validate_literal(spec,observed,path)==report['checks'][name],'Saved literal observations differ from the received report')
    conflict=out/'conflicting-aliases.mdx'
    require(conflict.read_bytes()==rewrite_header(paths['literal-utf8'].read_bytes(),[(' StripKey="No"',' StripKey="No" Stripkey="Yes"')]),'Conflicting fixture changed')
    built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'finalize-build.log',timeout)
    binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
    require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
    process=subprocess.Popen([str(binary),'policy-inspect',str(out/'literal-utf8.json'),str(conflict)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
    try:stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:stop(process);process.communicate();raise RuntimeError('Final conflict refusal timed out')
    (out/'conflicting-aliases.recheck.log').write_bytes(stdout+b'\nSTDERR:\n'+stderr)
    require(conflict_rejected(process.returncode,stdout,stderr),'Conflict refusal did not match either known rejection; see conflicting-aliases.recheck.log')
    report.pop('error');report['conflicting_aliases']={'status':'passed_rejected_before_lookup','returncode':process.returncode,'stdout_empty':not stdout.strip(),'diagnostic':stderr.decode('utf-8').strip()}
    report['finalization']={'original_report_sha256':file_hash(report_path),'conflict_rechecked':True,'dictionaries_regenerated':False,'Rust_full_lookup_matrix_repeated':False,
        'source_sha256':{str(p.relative_to(ROOT)):file_hash(p) for p in [Path(__file__).resolve(),ROOT/'scripts/header_lookup.py']}}
    report['status']='literal_header_lookup_offline_passed_legacy_diagnostics_recorded_native_pending'
    with tempfile.TemporaryDirectory(prefix='header-finalize-',dir=out) as tmp:
        stage=Path(tmp);report['native_candidates']=publish_candidates(stage,observations,paths)
        require(report['native_candidates']=={f'07-header-{name}.mdx':report['checks'][name]['sha256'] for name in paths},'Published bytes differ')
        (stage/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        with backup.open('xb') as stream:stream.write(original)
        published=False;checklist=False
        try:
            (stage/'native-candidates').rename(out/'native-candidates');published=True
            (stage/'native-checklist.csv').rename(out/'native-checklist.csv');checklist=True
            os.replace(stage/'report.json',report_path)
        except Exception:
            if published:shutil.rmtree(out/'native-candidates')
            if checklist:(out/'native-checklist.csv').unlink()
            raise
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=600);args=p.parse_args()
    out=args.output.resolve()
    try:
        report=finalize(out,args.timeout);print(f"{report['status']}: {out/'header-lookup-report.json'}");return 0
    except Exception as error:
        print(f'Finalize failed: {error}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
