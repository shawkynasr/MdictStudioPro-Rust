"""Source-bound frontend-only gate for job feedback; no Rust rerun."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import traceback
from m2_closeout import inventory

ROOT=Path(__file__).resolve().parents[1]
DESKTOP=ROOT/'m3/desktop'

def sources():
    paths=[p for directory in ['src','tests'] for p in (DESKTOP/directory).rglob('*') if p.is_file() and p.name!='.DS_Store']
    paths += [DESKTOP/n for n in ['package.json','package-lock.json','tsconfig.json','vite.config.ts','svelte.config.js'] if (DESKTOP/n).is_file()]
    paths += [Path(__file__).resolve(),ROOT/'docs/M3-JOB-FEEDBACK.md']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('m3-shell-out-job-feedback'))
    out=parser.parse_args().output.resolve()
    if not out.name.startswith('m3-shell-out'):parser.error('Use a fresh m3-shell-out-prefixed folder')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-job-feedback-frontend-v1','status':'failed','steps':[],
            'native_tests_executed':False,'GUI_smoke_executed':False,'M3_complete':False,'production_release_ready':False}
    try:
        before=sources();protected=inventory()
        report.update(source_sha256=before,protected_source_sha256=protected)
        npm=shutil.which('npm')
        if not npm:raise RuntimeError('Node/npm required; run this check on the Mac with installed frontend dependencies')
        for name,command in [('frontend-tests',[npm,'test']),('frontend-build',[npm,'run','build'])]:
            report['stage']=name;print(name,flush=True)
            result=subprocess.run(command,cwd=DESKTOP,capture_output=True,text=True,timeout=1200)
            log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log,encoding='utf-8')
            report['steps'].append({'name':name,'returncode':result.returncode,'log_tail':log[-24000:]})
            if result.returncode:raise AssertionError(name+' failed')
        assert before==sources(),'Frontend qualification sources changed during the check'
        assert protected==inventory(),'Protected backend sources changed'
        report.update(status='job_feedback_frontend_tests_and_build_passed_GUI_smoke_pending',stage='complete',
                      scope='Frontend job presentation and interpreter-selection preflight only. Runtime plugin options use the earlier accepted native implementation; no new Rust execution or GUI interaction claimed.')
    except (Exception,KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    return 0 if report.get('stage')=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
