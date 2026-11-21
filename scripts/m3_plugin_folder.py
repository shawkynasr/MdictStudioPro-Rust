"""Focused native/desktop gate for explicit trusted plugin folder discovery."""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from m2_closeout import inventory
from m3_shell import ROOT, DESKTOP, sources
from m3_mac_preview import lock_state, verify_frontend_install


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('m3-shell-out-plugin-folder'))
    out=parser.parse_args().output.resolve()
    if not out.name.startswith('m3-shell-out'):parser.error('Use a fresh m3-shell-out-prefixed folder')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-plugin-folder-native-v1','status':'failed','steps':[],
            'native_tests_executed':False,'desktop_compile_executed':False,'GUI_smoke_executed':False,
            'M3_complete':False,'production_release_ready':False,'platform':platform.platform()}
    before=None
    protected=None
    def run(name,command,cwd=ROOT):
        report['stage']=name;print(name,flush=True)
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,timeout=1800)
        log=result.stdout+'\nSTDERR:\n'+result.stderr
        (out/(name+'.log')).write_text(log,encoding='utf-8')
        report['steps'].append({'name':name,'returncode':result.returncode,'log_tail':log[-24000:]})
        if result.returncode:raise AssertionError(name+' failed')
    try:
        before={k:v for k,v in sources().items() if 'mdict-studio-m0-m1/' not in k and '__pycache__' not in k and not k.endswith('.DS_Store')}
        protected=inventory()
        report.update(source_sha256=before,protected_source_sha256=protected)
        bindings=json.loads((ROOT/'m3/packaging/mac-lock-bindings.json').read_text())
        report['initial_locks']=lock_state(ROOT,bindings)
        report['installed_direct_frontend_versions']=verify_frontend_install(DESKTOP)
        cargo=shutil.which('cargo');npm=shutil.which('npm')
        if not cargo or not npm:raise RuntimeError('Run this gate on the Mac with existing Cargo/npm dependencies')
        env={**os.environ,'CARGO_NET_OFFLINE':'true','npm_config_offline':'true','STUDIO_TEST_PYTHON':sys.executable}
        for crate in ['native-adapter','export-io','indexed-sessions','txt-runtime']:
            run(crate+'-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',f'm3/{crate}/Cargo.toml'])
        report['resolved_locks']=lock_state(ROOT,bindings,resolved=True)
        run('wrapper-tests',[sys.executable,'-m','unittest','discover','-s','scripts','-p','test_m3_python_plugin.py','-v'])
        run('inspection-wrapper-tests',[sys.executable,'-m','unittest','discover','-s','scripts','-p','test_m3_plugin_inspection.py','-v'])
        run('folder-fixture-tests',[sys.executable,'-m','unittest','discover','-s','scripts','-p','test_m3_plugin_folder.py','-v'])
        run('runtime-tests',[cargo,'test','--offline','--locked','--manifest-path','m3/txt-runtime/Cargo.toml'])
        run('adapter-tests',[cargo,'test','--offline','--locked','--manifest-path','m3/native-adapter/Cargo.toml'])
        report['native_tests_executed']=True
        run('frontend-tests',[npm,'test'],DESKTOP)
        run('frontend-build',[npm,'run','build'],DESKTOP)
        run('desktop-check',[cargo,'check','--offline','--locked','--manifest-path','src-tauri/Cargo.toml'],DESKTOP)
        report['desktop_compile_executed']=True
        report['final_locks']=lock_state(ROOT,bindings,resolved=True)
        after={k:v for k,v in sources().items() if 'mdict-studio-m0-m1/' not in k and '__pycache__' not in k and not k.endswith('.DS_Store')}
        if before!=after or protected!=inventory():raise AssertionError('Qualification sources changed during gate')
        report.update(status='plugin_folder_native_and_frontend_passed_GUI_pending',stage='complete')
    except (Exception,KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        try:
            if protected is not None:report['protected_sources_unchanged']=protected==inventory()
        except Exception as error:report['source_inspection_error']=str(error)
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    return 0 if report.get('stage')=='complete' else 1


if __name__=='__main__':raise SystemExit(main())
