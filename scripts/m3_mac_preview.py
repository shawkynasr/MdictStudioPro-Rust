"""Build a source-bound local Mac .app using reviewed lock identities only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import time
import traceback
from m2_closeout import inventory
from m3_shell import sources,check_adapter_lock,check_structure

ROOT=Path(__file__).resolve().parents[1]
DESKTOP=ROOT/'m3/desktop'
BINDINGS='m3/packaging/mac-lock-bindings.json'
OVERRIDE='m3/desktop/src-tauri/tauri.preview.conf.json'
PRODUCT='Mdict Studio Pro Preview'
IDENTIFIER='com.mdictstudio.pro.preview'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def lock_state(root,bindings,resolved=False):
    actual={}
    for name,item in bindings['locks'].items():
        p=root/name
        assert p.is_file() and not p.is_symlink(),f'Missing or symlinked lock: {name}'
        h=digest(p)
        assert h in ([item['build_sha256']] if resolved else item['accepted_sha256']),f'Unreviewed lock identity: {name}'
        actual[name]=h
    return actual

def verify_frontend_install(desktop):
    lock=json.loads((desktop/'package-lock.json').read_text());manifest=json.loads((desktop/'package.json').read_text())
    actual={}
    for name in {**manifest['dependencies'],**manifest['devDependencies']}:
        version=json.loads((desktop/'node_modules'/name/'package.json').read_text())['version']
        assert version==lock['packages']['node_modules/'+name]['version'],f'Installed frontend version differs from lock: {name}'
        actual[name]=version
    return actual

def inspect_bundle(app):
    plist=app/'Contents/Info.plist'
    assert plist.is_file() and not plist.is_symlink() and plist.resolve().is_relative_to(app.resolve()),'Invalid bundle Info.plist'
    info=plistlib.loads(plist.read_bytes())
    assert info['CFBundleIdentifier']==IDENTIFIER,'Unexpected preview bundle identity'
    executable=info['CFBundleExecutable']
    assert executable and Path(executable).name==executable and '/' not in executable and '\\' not in executable,'Invalid executable name'
    binary=app/'Contents/MacOS'/executable
    assert binary.is_file() and not binary.is_symlink() and binary.stat().st_size>0 and os.access(binary,os.X_OK),'Bundle executable missing or not executable'
    files={};links={}
    for path in sorted(app.rglob('*')):
        name=str(path.relative_to(app))
        if path.is_symlink():
            assert path.resolve().is_relative_to(app.resolve()),'Bundle symlink escapes app'
            links[name]=os.readlink(path)
        elif path.is_file():files[name]={'sha256':digest(path),'bytes':path.stat().st_size}
    return {'identifier':info['CFBundleIdentifier'],'version':info.get('CFBundleShortVersionString'),
            'executable':executable,'executable_sha256':digest(binary),'files':files,'symlinks':links,
            'launch_tested':False}

def source_hashes():
    result={n:h for n,h in sources().items() if not n.startswith('m3/desktop/mdict-studio-m0-m1/') and '__pycache__' not in Path(n).parts and Path(n).name!='.DS_Store'}
    for n in [BINDINGS,OVERRIDE,'scripts/m3_mac_preview.py','scripts/test_m3_mac_preview.py','docs/M3-MAC-PREVIEW.md']:
        result[n]=digest(ROOT/n)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('m3-shell-out-mac-preview'))
    out=p.parse_args().output.resolve()
    if not out.name.startswith('m3-shell-out'):p.error('Use a fresh m3-shell-out-prefixed folder')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-Mac-preview-build-v1','status':'failed','steps':[],
            'native_tests_executed':False,'native_build_executed':False,'app_launch_tested':False,'M3_complete':False,
            'production_release_ready':False,'signing_requested':False,'notarization_requested':False,
            'platform':platform.platform()}
    before=None;protected=None
    env={k:v for k,v in os.environ.items() if not k.startswith('APPLE_')}
    env.update(CARGO_NET_OFFLINE='true',CARGO_TARGET_DIR=str(DESKTOP/'src-tauri/target'),npm_config_offline='true')
    def run(name,command,cwd=ROOT,timeout=3600):
        report['stage']=name;print(name,flush=True);start=time.monotonic()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        text=(out/(name+'.log')).read_text(encoding='utf-8',errors='replace')
        report['steps'].append({'name':name,'command':command,'returncode':result.returncode,'elapsed_ms':(time.monotonic()-start)*1000,'log_tail':text[-24000:]})
        assert result.returncode==0,f'{name} failed; see {out/(name+".log")}'
    try:
        assert platform.system()=='Darwin','This .app build must run on the Mac'
        before=source_hashes();protected=inventory()
        bindings=json.loads((ROOT/BINDINGS).read_text())
        report.update(source_sha256=before,protected_source_sha256=protected,locks_before=lock_state(ROOT,bindings))
        report['structure']=check_structure()
        report['installed_direct_frontend_versions']=verify_frontend_install(DESKTOP)
        report['frontend_install_scope']='Direct package versions checked against the reviewed lock; existing node_modules reused, not a clean or bit-reproducible install.'
        cargo=shutil.which('cargo');npm=shutil.which('npm')
        assert cargo and npm,'Existing Cargo and npm toolchains are required'
        run('tauri-build-help',[npm,'run','tauri','--','build','--help'],DESKTOP,60)
        assert '--no-sign' in (out/'tauri-build-help.log').read_text(),'Installed Tauri CLI lacks --no-sign'
        # Distributed M3 seed locks may be pruned by Cargo. Only the exact
        # resolved hashes already observed in the passing native gate are accepted.
        for name in ['native-adapter','export-io','indexed-sessions','txt-runtime']:
            run(name+'-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',f'm3/{name}/Cargo.toml'])
            report.setdefault('registry_checks',{})[name]=check_adapter_lock(ROOT/f'm3/{name}/Cargo.lock')
        report['locks_after_normalization']=lock_state(ROOT,bindings,resolved=True)
        run('desktop-locked-metadata',[cargo,'metadata','--offline','--locked','--no-deps','--format-version','1','--manifest-path','src-tauri/Cargo.toml'],DESKTOP)
        run('frontend-tests',[npm,'test'],DESKTOP)
        report['native_build_requested']=True
        run('preview-app-build',[npm,'run','tauri','--','build','--config',str(ROOT/OVERRIDE),'--bundles','app','--ci','--no-sign','--','--locked','--offline'],DESKTOP)
        report['native_build_executed']=True
        original=DESKTOP/'src-tauri/target/release/bundle/macos'/(PRODUCT+'.app')
        report['bundle_before_copy']=inspect_bundle(original)
        app=out/(PRODUCT+'.app');shutil.copytree(original,app,symlinks=True)
        report['bundle']=inspect_bundle(app)
        assert report['bundle']==report['bundle_before_copy'],'Copied app bundle differs'
        report['locks_after_build']=lock_state(ROOT,bindings,resolved=True)
        assert source_hashes()==before,'Source files changed during preview build'
        assert inventory()==protected,'Protected backend sources changed'
        report.update(status='Mac_preview_built_GUI_checks_pending',stage='complete',app=str(app),
                      scope='Local unsigned development preview on the reported Mac platform; release CSP inherited, no launch/notarization/distribution or full M3 qualification.')
    except (Exception,KeyboardInterrupt) as error:
        report.update(error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        try:
            if before is not None:
                after=source_hashes();report['changed_sources']=[n for n in before if before[n]!=after.get(n)]
                if after!=before:report.update(status='failed',error='Build source identities changed; review changed_sources')
            if protected is not None:
                report['protected_sources_unchanged']=inventory()==protected
                if not report['protected_sources_unchanged']:report.update(status='failed',error='Protected source identities changed')
        except Exception as error:report.update(status='failed',final_identity_error=str(error))
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    if report.get('app'):print(report['app'],flush=True)
    return 0 if report['status']=='Mac_preview_built_GUI_checks_pending' else 1

if __name__=='__main__':raise SystemExit(main())
