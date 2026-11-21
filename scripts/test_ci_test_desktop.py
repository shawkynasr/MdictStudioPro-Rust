"""Exercise config propagation across subprocess boundaries without Rust installed."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from ci_collect_preview import ROOT
from ci_test_desktop import run_tests


class DesktopTestConfiguration(unittest.TestCase):
    def fixture(self, root):
        tauri = root / 'm3/desktop/src-tauri'
        tauri.mkdir(parents=True)
        config = json.loads((ROOT / 'm3/desktop/src-tauri/tauri.ci.conf.json').read_text())
        (tauri / 'tauri.ci.conf.json').write_text(json.dumps(config))
        for name in config['bundle']['icon']:
            icon = tauri / name
            icon.parent.mkdir(parents=True, exist_ok=True)
            icon.write_bytes(b'generated icon fixture')
        return tauri, config

    def test_windows_cargo_receives_actual_preview_json_and_locked_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tauri, config = self.fixture(root)
            with patch('ci_test_desktop.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
                self.assertEqual(run_tests(root, 'x86_64-pc-windows-msvc'), 0)
            args, kwargs = run.call_args
            self.assertEqual(json.loads(kwargs['env']['TAURI_CONFIG']), config)
            self.assertIn('icons/ci/icon.ico', json.loads(kwargs['env']['TAURI_CONFIG'])['bundle']['icon'])
            self.assertIn('--locked', args[0])
            self.assertIn('x86_64-pc-windows-msvc', args[0])
            self.assertEqual(args[0][-1], 'project_link_tests')
            self.assertTrue(kwargs['check'])

    def test_missing_generated_icon_stops_before_cargo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tauri, _ = self.fixture(root)
            (tauri / 'icons/ci/icon.ico').unlink()
            with patch('ci_test_desktop.subprocess.run') as run:
                with self.assertRaises(FileNotFoundError): run_tests(root, 'x86_64-pc-windows-msvc')
                run.assert_not_called()

    def test_cargo_failure_is_propagated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            with patch('ci_test_desktop.subprocess.run', side_effect=subprocess.CalledProcessError(101, 'cargo')):
                with self.assertRaises(subprocess.CalledProcessError): run_tests(root, 'x86_64-pc-windows-msvc')


if __name__ == '__main__': unittest.main()
