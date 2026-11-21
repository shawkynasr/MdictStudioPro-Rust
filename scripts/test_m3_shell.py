"""Contract checks only. These do not substitute for Rust/Svelte/native execution."""
import json
import unittest
import subprocess
import tempfile
import struct
import zlib
from unittest.mock import patch
from pathlib import Path
from m3_shell import ROOT, DESKTOP, check_structure, check_adapter_lock, sources

class ShellContracts(unittest.TestCase):
    def test_read_only_job_adapter_keeps_inherited_publication_assertions(self):
        expected=(ROOT/'m2/cc-pack-runtime/src/tests.rs').read_text().replace('.destination()', '.destination().unwrap()').replace('"../../revised-render/','"../../../m2/revised-render/').replace('"../../concise-runtime/','"../../../m2/concise-runtime/')
        self.assertEqual((ROOT/'m3/txt-runtime/src/inherited_tests.rs').read_text(),expected)
        import re
        for relative in re.findall(r'include_bytes!\("([^"]+)"\)',expected):
            self.assertTrue((ROOT/'m3/txt-runtime/src'/relative).is_file(),relative)
        runtime=(ROOT/'m3/txt-runtime/src/lib.rs').read_text()
        self.assertIn('Self::DatabasePage(_)',runtime)
        self.assertIn('Option<&std::path::Path>',runtime)
    def test_seed_normalization_before_locked_tests_fresh_and_cached(self):
        # Simulate uncached archives AND a restored seed lock. These are runner
        # regression checks, not substitutes for executing the Rust tests.
        import m3_shell
        for install in [False, True]:
            with self.subTest(install=install), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                (root/'vendor/mdictlib-0.2.8-studio-sort-v6').mkdir(parents=True)
                desktop=root/'m3/desktop'
                (desktop/'src-tauri').mkdir(parents=True)
                for name in ['package-lock.json','src-tauri/Cargo.lock']:
                    (desktop/name).write_text('isolated test lock')
                commands=[]
                fetched=not install
                normalized=False
                def run(command, **kwargs):
                    nonlocal fetched,normalized
                    commands.append(command)
                    if command[0]!='/stub/cargo':
                        return subprocess.CompletedProcess(command,0,'stub platform','')
                    if command[1]=='fetch':fetched=True
                    if command[1]=='metadata' and '--no-deps' not in command:
                        if not fetched:
                            return subprocess.CompletedProcess(command,101,'','missing archive while offline')
                        if '--locked' in command and not normalized:
                            return subprocess.CompletedProcess(command,101,'','seed lock needs normalization')
                        normalized=True
                    if command[1]=='test':
                        self.assertTrue(normalized)
                        self.assertIn('--locked',command)
                        self.assertIn('--offline',command)
                    return subprocess.CompletedProcess(command,0,'stubbed orchestration check','')
                checks=[]
                def check_lock(*args):
                    checks.append(normalized)
                    return {}
                out=root/'m3-shell-out-test'
                argv=['m3_shell.py','--adapter-only','--output',str(out)]+(['--install'] if install else [])
                with patch.object(m3_shell.platform,'platform',return_value='test-platform'), patch.object(m3_shell,'ROOT',root), patch.object(m3_shell,'DESKTOP',desktop), patch.object(m3_shell,'sources',return_value={}), patch.object(m3_shell,'check_structure',return_value={}), patch.object(m3_shell,'check_adapter_lock',side_effect=check_lock), patch('m2_closeout.inventory',return_value={}), patch.object(m3_shell.shutil,'which',return_value='/stub/cargo'), patch.object(m3_shell.subprocess,'run',side_effect=run), patch('sys.argv',argv):
                    result=m3_shell.main()
                    receipt=json.loads((out/'m3-shell-report.json').read_text())
                    self.assertEqual(result,0,receipt.get('traceback',receipt.get('error')))
                    self.assertEqual(set(receipt['locks']),{'m3/desktop/package-lock.json','m3/desktop/src-tauri/Cargo.lock'})
                commands=[c for c in commands if c[0]=='/stub/cargo']
                self.assertIn('--no-deps',commands[0])
                full=[c for c in commands if c[1]=='metadata' and '--no-deps' not in c]
                self.assertEqual(len(full),4)
                self.assertNotIn('--locked',full[0])
                self.assertIn('--offline',full[0])
                self.assertTrue(checks[-1], 'Recheck normalized graph before tests')
                self.assertEqual(json.loads((out/'m3-shell-report.json').read_text())['status'],'adapter_tests_passed')

    def test_seed_orchestration_ignores_installed_desktop_locks(self):
        # Reproduce the installed Mac environment: these locks exist outside the
        # test root and must never leak into the simulated runner receipt.
        import m3_shell
        with tempfile.TemporaryDirectory() as tmp:
            host=Path(tmp)/'installed-desktop'
            (host/'src-tauri').mkdir(parents=True)
            for name in ['package-lock.json','src-tauri/Cargo.lock']:
                (host/name).write_text('external host lock')
            with patch.object(m3_shell,'DESKTOP',host):
                self.test_seed_normalization_before_locked_tests_fresh_and_cached()

    def test_config_boundary(self):
        self.assertTrue(all(check_structure().values()))
        cap=json.loads((DESKTOP/'src-tauri/capabilities/main.json').read_text())
        self.assertIn('studio-native',cap['permissions'])
        self.assertNotIn('core:default',cap['permissions'])
        build=(DESKTOP/'src-tauri/build.rs').read_text()
        self.assertIn('.commands(&["studio_call"])',build)

    def test_isolated_graph_does_not_upgrade_backend(self):
        self.assertTrue(check_adapter_lock()['no_unapproved_registry_versions'])
        for path in ['m3/native-adapter/Cargo.toml','m3/desktop/src-tauri/Cargo.toml']:
            text=(ROOT/path).read_text()
            self.assertIn('[workspace]',text)
            self.assertIn('mdictlib-0.2.8-studio-sort-v6',text)

    def test_database_additions_match_qualified_lock_and_cannot_upgrade_m2(self):
        import tomllib
        from m3_shell import sha
        approved=json.loads((ROOT/'m4/sqlite-registry.json').read_text())
        self.assertEqual(approved['source_lock_sha256'],sha(ROOT/'m4/database/Cargo.lock'))
        backend=tomllib.loads((ROOT/'m4/database/Cargo.lock').read_text())['package']
        base={p['name'] for p in tomllib.loads((ROOT/'m2/cc-pack-runtime/Cargo.lock').read_text())['package']}
        self.assertEqual(approved['registry_packages'],[p for p in backend if p.get('source') and p['name'] not in base])
        for relative in ['m3/native-adapter/Cargo.lock','m3/txt-runtime/Cargo.lock']:
            result=check_adapter_lock(ROOT/relative)
            self.assertEqual(set(result['database_additions']),{p['name'] for p in approved['registry_packages']})
            self.assertFalse(result['no_new_registry_versions'])
        # An unrelated dependency or altered checksum must still be refused.
        for change in ['checksum','version']:
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                for relative in ['m2/cc-pack-runtime/Cargo.lock','m3/native-adapter/Cargo.lock','m4/sqlite-registry.json']:
                    p=root/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/relative).read_bytes())
                p=root/'m3/native-adapter/Cargo.lock';text=p.read_text()
                package=approved['registry_packages'][0]
                text=text.replace(package[change],('0'*64 if change=='checksum' else '999.0.0'),1);p.write_text(text)
                with patch('m3_shell.ROOT',root),self.assertRaises(AssertionError):check_adapter_lock()

    def test_no_arbitrary_html_or_simulated_jobs_in_shell(self):
        app=(DESKTOP/'src/App.svelte').read_text()
        self.assertNotIn('{@html',app)
        self.assertIn('<iframe',app)
        self.assertIn('sandbox=""',app)
        self.assertNotIn('allow-scripts',app)
        self.assertNotIn('allow-same-origin',app)
        self.assertNotIn('progress+5',app)
        self.assertIn("call({ action:'submit', request })",app)
        self.assertIn("call<Poll>({ action:'poll' })",app)

    def test_native_cleanup_is_off_ui_thread(self):
        main=(DESKTOP/'src-tauri/src/main.rs').read_text()
        self.assertIn('spawn_blocking',main)
        self.assertIn('api.prevent_close()',main)
        self.assertIn('api.prevent_exit()',main)
        self.assertIn('adapter.shutdown()',main)
        self.assertIn('Menu::default(app.handle())',main)
        self.assertIn('"studio-shutdown-error", payload',main)

    def test_tauri_context_icon_is_present_and_rgba(self):
        config=json.loads((DESKTOP/'src-tauri/tauri.conf.json').read_text())
        for relative in config['bundle']['icon']:
            data=(DESKTOP/'src-tauri'/relative).read_bytes()
            self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
            offset=8
            compressed=b''
            while offset<len(data):
                length=struct.unpack('>I',data[offset:offset+4])[0]
                kind=data[offset+4:offset+8];body=data[offset+8:offset+8+length]
                crc=struct.unpack('>I',data[offset+8+length:offset+12+length])[0]
                self.assertEqual(crc,zlib.crc32(kind+body)&0xffffffff)
                if kind==b'IHDR':
                    width,height,depth,color,*_=struct.unpack('>IIBBBBB',body)
                    self.assertEqual((width,height,depth,color),(256,256,8,6))
                if kind==b'IDAT':compressed+=body
                offset+=length+12
            self.assertEqual(len(zlib.decompress(compressed)),256*(1+256*4))

    def test_receipt_inventory_is_scoped(self):
        paths=sources()
        self.assertIn('m3/native-adapter/src/lib.rs',paths)
        self.assertIn('m3/desktop/src/App.svelte',paths)
        self.assertTrue(all(not p.startswith('m2/') for p in paths))

if __name__=='__main__':unittest.main()
