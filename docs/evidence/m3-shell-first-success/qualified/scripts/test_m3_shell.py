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
    def test_seed_normalization_before_locked_tests_fresh_and_cached(self):
        # Simulate uncached archives AND a restored seed lock. These are runner
        # regression checks, not substitutes for executing the Rust tests.
        import m3_shell
        for install in [False, True]:
            with self.subTest(install=install), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                (root/'vendor/mdictlib-0.2.8-studio-sort-v6').mkdir(parents=True)
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
                def check_lock():
                    checks.append(normalized)
                    return {}
                out=root/'m3-shell-out-test'
                argv=['m3_shell.py','--adapter-only','--output',str(out)]+(['--install'] if install else [])
                with patch.object(m3_shell,'ROOT',root), patch.object(m3_shell,'sources',return_value={}), patch.object(m3_shell,'check_structure',return_value={}), patch.object(m3_shell,'check_adapter_lock',side_effect=check_lock), patch('m2_closeout.inventory',return_value={}), patch.object(m3_shell.shutil,'which',return_value='/stub/cargo'), patch.object(m3_shell.subprocess,'run',side_effect=run), patch('sys.argv',argv):
                    self.assertEqual(m3_shell.main(),0)
                commands=[c for c in commands if c[0]=='/stub/cargo']
                self.assertIn('--no-deps',commands[0])
                full=[c for c in commands if c[1]=='metadata' and '--no-deps' not in c]
                self.assertEqual(len(full),1)
                self.assertNotIn('--locked',full[0])
                self.assertIn('--offline',full[0])
                self.assertTrue(checks[-1], 'Recheck normalized graph before tests')
                self.assertEqual(json.loads((out/'m3-shell-report.json').read_text())['status'],'adapter_tests_passed')

    def test_config_boundary(self):
        self.assertTrue(all(check_structure().values()))
        cap=json.loads((DESKTOP/'src-tauri/capabilities/main.json').read_text())
        self.assertIn('studio-native',cap['permissions'])
        self.assertNotIn('core:default',cap['permissions'])
        build=(DESKTOP/'src-tauri/build.rs').read_text()
        self.assertIn('.commands(&["studio_call"])',build)

    def test_isolated_graph_does_not_upgrade_backend(self):
        self.assertTrue(check_adapter_lock()['no_new_registry_versions'])
        for path in ['m3/native-adapter/Cargo.toml','m3/desktop/src-tauri/Cargo.toml']:
            text=(ROOT/path).read_text()
            self.assertIn('[workspace]',text)
            self.assertIn('mdictlib-0.2.8-studio-sort-v6',text)

    def test_no_arbitrary_html_or_simulated_jobs_in_shell(self):
        app=(DESKTOP/'src/App.svelte').read_text()
        self.assertNotIn('{@html',app)
        self.assertNotIn('<iframe',app)
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
