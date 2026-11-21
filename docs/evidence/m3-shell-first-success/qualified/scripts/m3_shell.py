"""Verify the additive M3 shell slice; write an honest, source-bound native receipt."""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tomllib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = 'm3/native-adapter/Cargo.toml'
DESKTOP = ROOT / 'm3/desktop'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sources():
    excluded = {'target', 'node_modules', 'dist', 'gen'}
    paths = [p for p in (ROOT / 'm3').rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts) and p.name not in {'Cargo.lock', 'package-lock.json'}]
    paths += [ROOT / 'scripts/m3_shell.py', ROOT / 'scripts/test_m3_shell.py', ROOT / 'docs/M3-SHELL.md']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}

def check_adapter_lock():
    def registry(path):
        return {(p['name'], p['version']): p.get('checksum') for p in tomllib.loads(path.read_text())['package'] if p.get('source')}
    expected = registry(ROOT / 'm2/cc-pack-runtime/Cargo.lock')
    actual = registry(ROOT / 'm3/native-adapter/Cargo.lock')
    if any(key not in expected or expected[key] != checksum for key, checksum in actual.items()):
        raise AssertionError('Adapter introduced a registry version/checksum outside the accepted M2 graph')
    return {'registry_packages':len(actual), 'no_new_registry_versions':True, 'sha256':sha(ROOT / 'm3/native-adapter/Cargo.lock')}

def check_structure():
    for p in (ROOT / 'm3').rglob('*.json'):
        if not {'target','node_modules','dist','gen'}.intersection(p.relative_to(ROOT).parts):
            json.loads(p.read_text())
    for p in (ROOT / 'm3').rglob('*.toml'):
        if not {'target','node_modules','dist','gen'}.intersection(p.relative_to(ROOT).parts):
            tomllib.loads(p.read_text())
    config = json.loads((DESKTOP / 'src-tauri/tauri.conf.json').read_text())
    cap = json.loads((DESKTOP / 'src-tauri/capabilities/main.json').read_text())
    assert cap['windows'] == ['main'] and cap['local'] and not cap.get('remote')
    assert not any(p.startswith(('fs:', 'shell:', 'http:')) for p in cap['permissions'])
    assert "frame-src 'none'" in config['app']['security']['csp']
    assert config['bundle']['active'] is False
    return {'JSON_TOML_parse':True,'main_only_capability':True,'rendered_HTML_disabled':True,'release_bundling_disabled':True}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m3-shell-out'))
    parser.add_argument('--install', action='store_true', help='Fetch adapter crates and install frontend dependencies (npm ci when a lock exists)')
    parser.add_argument('--adapter-only', action='store_true', help='Run the GUI-independent Rust adapter tests only')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m3-shell-out'):
        parser.error('Use an m3-shell-out prefix to keep reports excluded from packages')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema':'studio-m3-shell-v1','status':'failed','native_tests_executed':False,'native_desktop_launched':False,'M3_complete':False,'steps':[], 'platform':platform.platform()}
    def run(name, command, cwd=ROOT):
        report['stage'] = name
        print(name, flush=True)
        try:
            done = subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=1200)
            log = done.stdout + '\nSTDERR:\n' + done.stderr
        except subprocess.TimeoutExpired as e:
            log = str(e.stdout or '') + '\n' + str(e.stderr or '')
            (out / (name + '.log')).write_text(log)
            raise RuntimeError(name + ' exceeded 1200 seconds') from e
        (out / (name + '.log')).write_text(log)
        report['steps'].append({'name':name,'command':command,'returncode':done.returncode,'log_tail':log[-48000:]})
        if done.returncode:
            raise RuntimeError('Command failed: ' + name)
    try:
        from m2_closeout import inventory
        report['protected_source_sha256'] = inventory()
        report['source_sha256'] = sources()
        report['structure'] = check_structure()
        cargo = shutil.which('cargo')
        if not cargo:
            report['status'] = 'blocked_missing_Rust_toolchain'
            raise RuntimeError('Rust toolchain not available; run on the Rust-enabled Mac')
        vendor = ROOT / 'vendor/mdictlib-0.2.8-studio-sort-v6'
        if not vendor.is_dir():
            raise RuntimeError('Keep the existing verified vendor tree; see docs/M3-SHELL.md for preparation')
        # Only the new isolated lock may be resolved. Registry changes are checked
        # against the accepted graph before any adapter code is built or run.
        # --no-deps avoids downloading uncached optional/platform dependencies
        # during the initial manifest inspection. A first installation cannot
        # assume that every archive selected by the accepted lock is cached.
        run('adapter-inspect',[cargo,'metadata','--offline','--no-deps','--format-version','1','--manifest-path',ADAPTER])
        report['adapter_lock'] = check_adapter_lock()
        if args.install:
            # Resolution is confined to the new adapter lock. Cargo may remove
            # obsolete dev-only edges from the seed. Refuse registry drift below
            # before compiling anything, then freeze the resolved lock.
            run('adapter-fetch',[cargo,'fetch','--manifest-path',ADAPTER])
            report['adapter_lock'] = check_adapter_lock()
        # Merging a source update can restore the distributed seed lock even
        # when all archives are cached. Normalize only this isolated lock before
        # freezing it; --no-deps inspection above does not normalize its edges.
        run('adapter-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',ADAPTER])
        report['adapter_lock'] = check_adapter_lock()
        run('adapter-tests',[cargo,'test','--offline','--locked','--manifest-path',ADAPTER])
        report['native_tests_executed'] = True
        if not args.adapter_only:
            npm = shutil.which('npm')
            if not npm:
                raise RuntimeError('Node.js 22.12+ and npm are required')
            if args.install:
                run('frontend-install',[npm,'ci' if (DESKTOP / 'package-lock.json').exists() else 'install'],DESKTOP)
            run('frontend-build',[npm,'run','build'],DESKTOP)
            run('tauri-info',[npm,'run','tauri','--','info'],DESKTOP)
            run('desktop-check',[cargo,'check','--manifest-path','src-tauri/Cargo.toml'],DESKTOP)
        if inventory() != report['protected_source_sha256'] or sources() != report['source_sha256']:
            raise AssertionError('Source identities changed during native checks')
        report['locks'] = {str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'m3/native-adapter/Cargo.lock', DESKTOP/'package-lock.json', DESKTOP/'src-tauri/Cargo.lock'] if p.is_file()}
        report['status'] = 'adapter_tests_passed' if args.adapter_only else 'adapter_tests_and_shell_compile_passed_native_launch_pending'
        report['stage'] = 'complete'
    except (Exception,KeyboardInterrupt) as e:
        report['error'] = f'{type(e).__name__}: {e}'
        report['traceback'] = traceback.format_exc()
    path = out / 'm3-shell-report.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(report['status'] + ': ' + str(path))
    return 0 if report['status'].endswith('passed') or report['status'].endswith('pending') else 1

if __name__ == '__main__':
    raise SystemExit(main())
