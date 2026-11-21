"""Verify the additive M3 shell slice; write an honest, source-bound native receipt."""
import argparse
import hashlib
import json
import platform
import os
import shutil
import subprocess
import sys
import tomllib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = 'm3/native-adapter/Cargo.toml'
TXT_RUNTIME = 'm3/txt-runtime/Cargo.toml'
EXPORT_IO = 'm3/export-io/Cargo.toml'
SESSIONS = 'm3/indexed-sessions/Cargo.toml'
DESKTOP = ROOT / 'm3/desktop'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sources():
    excluded = {'target', 'node_modules', 'dist', 'gen'}
    paths = [p for p in (ROOT / 'm3').rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts) and p.name not in {'Cargo.lock', 'package-lock.json'}]
    paths += [ROOT / 'scripts/m3_shell.py', ROOT / 'scripts/test_m3_shell.py', ROOT / 'scripts/test_m3_preview.py', ROOT / 'docs/M3-SHELL.md', ROOT / 'docs/M3-PREVIEW.md', ROOT / 'docs/M3-TXT-BUILD.md', ROOT / 'scripts/test_m3_txt_build.py', ROOT / 'docs/M3-FOLDER-MDD.md', ROOT / 'scripts/test_m3_folder_build.py', ROOT / 'docs/M3-EXTRACT-GUI.md', ROOT / 'scripts/verify_gui_extraction.py', ROOT / 'scripts/test_m3_extract_gui.py', ROOT / 'docs/M3-METADATA-GUI.md', ROOT / 'docs/M3-REDIRECTS.md', ROOT / 'docs/M3-PYTHON-PLUGINS.md', ROOT / 'scripts/test_m3_python_plugin.py', ROOT / 'docs/M3-STYLESHEET-EXPORT.md']
    paths += [p for p in (ROOT/'m4/database').rglob('*') if p.is_file() and not excluded.intersection(p.relative_to(ROOT).parts)]
    paths += [ROOT/'m4/sqlite-registry.json',ROOT/'docs/M4-DATABASE-GUI.md',ROOT/'docs/M4-DATABASE-BROWSE.md',ROOT/'docs/M4-MDX-DATABASE.md',ROOT/'scripts/verify_mdx_database.py',ROOT/'scripts/test_m4_database.py',ROOT/'scripts/verify_database_mdx.py',ROOT/'docs/M4-DATABASE-MDX.md']
    paths += [ROOT/'scripts/m4_stylesheet_roundtrip.py', ROOT/'docs/M4-STYLESHEET-ROUNDTRIP.md']
    paths += [ROOT/'scripts/m4_database_failures.py', ROOT/'docs/M4-DATABASE-FAILURES.md']
    paths += [ROOT/'scripts/m4_gui_cancel.py', ROOT/'docs/M4-GUI-CANCEL.md']
    paths += [ROOT/'docs/M4-DATABASE-PREFIX.md']
    paths += [ROOT/'docs/M3-UI-COPY.md',ROOT/'docs/M3-SETTINGS-DIALOG.md',ROOT/'docs/M3-FIRST-RELEASE-CHECKLIST.md']
    paths += [ROOT/'scripts/m3_v1_ascii.py',ROOT/'scripts/m3_v1_ascii_fixture.py',ROOT/'scripts/test_m3_v1_ascii.py',ROOT/'docs/M3-MDX-V1-ASCII.md']
    paths += [ROOT/'scripts/m3_keyinfo.py',ROOT/'scripts/m3_keyinfo_fixture.py',ROOT/'scripts/test_m3_keyinfo.py',ROOT/'docs/M3-MDX-KEYINFO.md']
    paths += [ROOT/'scripts/m3_plugin_simple.py',ROOT/'docs/M3-PLUGIN-SIMPLE.md']
    paths += [ROOT/'scripts/m3_plugin_folder.py',ROOT/'scripts/test_m3_plugin_folder.py',ROOT/'docs/M3-PLUGIN-FOLDER.md']
    paths += [ROOT/'scripts/m3_plugin_discovery.py',ROOT/'scripts/test_m3_plugin_inspection.py',ROOT/'docs/M3-PLUGIN-DISCOVERY.md']
    paths += [ROOT/'scripts/m3_mac_preview.py', ROOT/'scripts/test_m3_mac_preview.py', ROOT/'docs/M3-MAC-PREVIEW.md', ROOT/'scripts/m3_capture_mac_locks.py', ROOT/'scripts/test_m3_capture_mac_locks.py', ROOT/'docs/M3-DESKTOP-AUDIT.md', ROOT/'scripts/m3_job_feedback.py', ROOT/'docs/M3-JOB-FEEDBACK.md', ROOT/'scripts/m3_plugin_presets.py', ROOT/'docs/M3-PLUGIN-PRESETS.md', ROOT/'docs/M3-PLUGIN-OPTIONS.md', ROOT/'scripts/run_contracts.py', ROOT/'scripts/check_cc_full_receipt.py', ROOT/'scripts/test_cc_full_receipt.py', ROOT/'scripts/m4_database_closeout.py', ROOT/'scripts/test_m4_database_closeout.py', ROOT/'docs/M4-DATABASE-CLOSEOUT.md', ROOT/'scripts/m4_database_preflight.py', ROOT/'scripts/test_m4_database_preflight.py', ROOT/'docs/M4-DATABASE-PREFLIGHT.md', ROOT/'scripts/m4_database_sizing.py', ROOT/'scripts/test_m4_database_sizing.py', ROOT/'docs/M4-DATABASE-SIZING.md', ROOT/'scripts/m4_database_workflow.py', ROOT/'scripts/test_m4_database_workflow.py', ROOT/'docs/M4-DATABASE-WORKFLOW.md', ROOT/'docs/M4-CLOSEOUT-CHECKPOINTS.md', ROOT/'scripts/m4_database_add.py', ROOT/'scripts/verify_database_add.py', ROOT/'scripts/test_m4_database_add.py', ROOT/'docs/M4-DATABASE-ADD.md', ROOT/'scripts/m4_database_delete.py', ROOT/'scripts/verify_database_delete.py', ROOT/'scripts/test_m4_database_delete.py', ROOT/'docs/M4-DATABASE-DELETE.md', ROOT/'scripts/m4_database_rename.py', ROOT/'docs/M4-DATABASE-RENAME.md', ROOT/'docs/M4-DATABASE-PREVIEW.md', ROOT/'docs/M4-DATABASE-READER-GUI.md', ROOT/'docs/M4-DATABASE-CASE.md', ROOT/'docs/M4-DATABASE-PATTERN.md', ROOT/'docs/M4-DATABASE-JSONL.md', ROOT/'docs/M4-DATABASE-DEFINITION.md', ROOT/'docs/M4-DATABASE-METADATA-COPY.md', ROOT/'docs/M4-DATABASE-STYLESHEET-COPY.md', ROOT/'docs/M4-DATABASE-ENTRY-COPY.md', ROOT/'scripts/m4_database_entry.py', ROOT/'scripts/verify_database_entry.py', ROOT/'scripts/test_m4_database_entry.py', ROOT/'scripts/m4_database_stylesheet_copy.py', ROOT/'scripts/m4_database_metadata.py', ROOT/'scripts/verify_database_metadata.py', ROOT/'scripts/test_m4_database_metadata.py', ROOT/'scripts/m4_database_definition.py', ROOT/'docs/M4-DATABASE-JSONL-IMPORT.md', ROOT/'scripts/m4_database_jsonl_import.py', ROOT/'scripts/m4_database_jsonl.py', ROOT/'scripts/verify_database_jsonl.py', ROOT/'scripts/test_m4_database_jsonl.py', ROOT/'scripts/m4_database_reader.py']
    paths += [ROOT/'scripts/m3_parent_death.py',ROOT/'scripts/test_m3_parent_death.py',ROOT/'docs/M3-PARENT-DEATH.md']
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}

def check_adapter_lock(path=None):
    def registry(path):
        return {(p['name'], p['version']): p.get('checksum') for p in tomllib.loads(path.read_text())['package'] if p.get('source')}
    expected = registry(ROOT / 'm2/cc-pack-runtime/Cargo.lock')
    lock_path = path or ROOT / 'm3/native-adapter/Cargo.lock'
    actual = registry(lock_path)
    allowed=dict(expected)
    if lock_path in [ROOT/'m3/native-adapter/Cargo.lock',ROOT/'m3/txt-runtime/Cargo.lock']:
        additions=json.loads((ROOT/'m4/sqlite-registry.json').read_text())['registry_packages']
        base_names={name for name,_ in expected}
        assert all(p['name'] not in base_names for p in additions),'SQLite additions cannot upgrade existing M2 crates'
        allowed.update({(p['name'],p['version']):p['checksum'] for p in additions})
    if any(key not in allowed or allowed[key] != checksum for key, checksum in actual.items()):
        raise AssertionError('Registry version/checksum outside accepted M2 plus qualified SQLite additions')
    return {'registry_packages':len(actual),'no_unapproved_registry_versions':True,
            'no_new_registry_versions':all(key in expected for key in actual),
            'database_additions':sorted(name for name,version in actual if (name,version) not in expected),'sha256':sha(lock_path)}

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
    assert "frame-src about:" in config['app']['security']['csp']
    app=(DESKTOP/'src/App.svelte').read_text()
    assert 'sandbox=""' in app and 'allow-scripts' not in app and 'allow-same-origin' not in app
    assert config['bundle']['active'] is False
    return {'JSON_TOML_parse':True,'main_only_capability':True,'static_preview_opaque_sandbox':True,'release_bundling_disabled':True}

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
            done = subprocess.run(command,cwd=cwd,text=True,capture_output=True,timeout=1200,env={**os.environ,"STUDIO_TEST_PYTHON":sys.executable})
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
        report['export_io_lock'] = check_adapter_lock(ROOT/'m3/export-io/Cargo.lock')
        run('export-io-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',EXPORT_IO])
        report['export_io_lock'] = check_adapter_lock(ROOT/'m3/export-io/Cargo.lock')
        run('export-io-tests',[cargo,'test','--offline','--locked','--manifest-path',EXPORT_IO])
        report['export_io_tests_executed'] = True
        report['indexed_sessions_lock'] = check_adapter_lock(ROOT/'m3/indexed-sessions/Cargo.lock')
        run('indexed-sessions-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',SESSIONS])
        report['indexed_sessions_lock'] = check_adapter_lock(ROOT/'m3/indexed-sessions/Cargo.lock')
        run('indexed-sessions-tests',[cargo,'test','--offline','--locked','--manifest-path',SESSIONS])
        report['indexed_sessions_tests_executed'] = True
        report['txt_runtime_lock'] = check_adapter_lock(ROOT/'m3/txt-runtime/Cargo.lock')
        run('txt-runtime-resolve',[cargo,'metadata','--offline','--format-version','1','--manifest-path',TXT_RUNTIME])
        report['txt_runtime_lock'] = check_adapter_lock(ROOT/'m3/txt-runtime/Cargo.lock')
        run('database-backend-tests',[cargo,'test','--offline','--locked','--manifest-path','m4/database/Cargo.toml'])
        report['database_backend_tests_executed'] = True
        run('txt-runtime-tests',[cargo,'test','--offline','--locked','--manifest-path',TXT_RUNTIME])
        report['txt_runtime_tests_executed'] = True
        run('python-plugin-wrapper-tests',[sys.executable,'-m','unittest','discover','-s','scripts','-p','test_m3_python_plugin.py','-v'])
        report['python_plugin_wrapper_tests_executed'] = True
        run('adapter-tests',[cargo,'test','--offline','--locked','--manifest-path',ADAPTER])
        report['native_tests_executed'] = True
        if not args.adapter_only:
            npm = shutil.which('npm')
            if not npm:
                raise RuntimeError('Node.js 22.12+ and npm are required')
            if args.install:
                run('frontend-install',[npm,'ci' if (DESKTOP / 'package-lock.json').exists() else 'install'],DESKTOP)
            run('preview-contract-tests',[npm,'test'],DESKTOP)
            run('frontend-build',[npm,'run','build'],DESKTOP)
            run('tauri-info',[npm,'run','tauri','--','info'],DESKTOP)
            run('desktop-check',[cargo,'check','--manifest-path','src-tauri/Cargo.toml'],DESKTOP)
        if inventory() != report['protected_source_sha256'] or sources() != report['source_sha256']:
            raise AssertionError('Source identities changed during native checks')
        report['locks'] = {str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'m3/native-adapter/Cargo.lock', ROOT/'m3/txt-runtime/Cargo.lock', ROOT/'m3/export-io/Cargo.lock', ROOT/'m3/indexed-sessions/Cargo.lock', DESKTOP/'package-lock.json', DESKTOP/'src-tauri/Cargo.lock'] if p.is_file()}
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
