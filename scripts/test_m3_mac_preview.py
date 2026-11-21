"""Reject lock drift, bundle path escapes and incorrect local preview identity."""
import copy
import json
import os
from pathlib import Path
import plistlib
import tempfile
import unittest
from m3_mac_preview import ROOT,BINDINGS,IDENTIFIER,lock_state,inspect_bundle

class MacPreviewTests(unittest.TestCase):
    def test_only_exact_reviewed_seed_and_resolved_hashes_are_allowed(self):
        bindings=json.loads((ROOT/BINDINGS).read_text())
        self.assertEqual(len(lock_state(ROOT,bindings)),7)
        bad=copy.deepcopy(bindings);name=next(iter(bad['locks']));bad['locks'][name]['accepted_sha256']=['0'*64]
        with self.assertRaises(AssertionError):lock_state(ROOT,bad)
        bad=copy.deepcopy(bindings);bad['locks'][name]['build_sha256']='0'*64
        with self.assertRaises(AssertionError):lock_state(ROOT,bad,resolved=True)

    def test_bundle_identity_executable_and_symlink_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            app=Path(temp)/'Preview.app';binary=app/'Contents/MacOS/preview';binary.parent.mkdir(parents=True)
            binary.write_bytes(b'test executable fixture');binary.chmod(0o755)
            info=app/'Contents/Info.plist';fields={'CFBundleIdentifier':IDENTIFIER,'CFBundleExecutable':'preview','CFBundleShortVersionString':'0.1.0'}
            info.write_bytes(plistlib.dumps(fields));self.assertFalse(inspect_bundle(app)['launch_tested'])
            for change in [{'CFBundleIdentifier':'wrong'},{'CFBundleExecutable':'../outside'}]:
                info.write_bytes(plistlib.dumps({**fields,**change}))
                with self.assertRaises(AssertionError):inspect_bundle(app)
            info.write_bytes(plistlib.dumps(fields));outside=Path(temp)/'outside';outside.write_bytes(b'private')
            (app/'escape').symlink_to(outside)
            with self.assertRaises(AssertionError):inspect_bundle(app)

    def test_preview_override_preserves_production_security_and_dev_configuration(self):
        base=json.loads((ROOT/'m3/desktop/src-tauri/tauri.conf.json').read_text())
        override=json.loads((ROOT/'m3/desktop/src-tauri/tauri.preview.conf.json').read_text())
        self.assertFalse(base['bundle']['active']);self.assertTrue(override['bundle']['active'])
        self.assertNotIn('app',override);self.assertNotIn('build',override)
        self.assertEqual(override['identifier'],IDENTIFIER)
        self.assertNotIn('http://localhost:1420',base['app']['security']['csp'])
        self.assertNotIn('ws://localhost:1420',base['app']['security']['csp'])
        self.assertEqual(override['bundle']['targets'],['app'])
