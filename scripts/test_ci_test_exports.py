"""Check seed normalization ordering and pin-drift rejection without Rust."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from ci_collect_preview import ROOT, TARGETS
from ci_test_exports import run_tests


class ExportTestPreparation(unittest.TestCase):
    def fixture(self, root, suite):
        relative = 'm3/txt-runtime' if suite == 'runtime' else 'm3/export-io'
        for name in ['m2/cc-pack-runtime/Cargo.lock', 'm4/sqlite-registry.json',
                     relative + '/Cargo.lock']:
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)
        return root / relative / 'Cargo.lock'

    def test_all_targets_normalize_each_seed_before_locked_offline_tests(self):
        for target in TARGETS:
            for suite in ['export', 'runtime']:
                with self.subTest(target=target, suite=suite), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    lock = self.fixture(root, suite)
                    before = lock.read_bytes()
                    calls = []
                    cached = False
                    def execute(command, **kwargs):
                        nonlocal cached
                        calls.append(command)
                        if command[1] == 'fetch':
                            self.assertNotIn('--offline', command)
                            self.assertNotIn('--locked', command)
                            self.assertIn(target, command)
                            cached = True
                        elif command[1] == 'metadata':
                            self.assertTrue(cached, 'Fresh standalone graph must be fetched first')
                            self.assertIn('--offline', command)
                            self.assertNotIn('--locked', command)
                            self.assertIn(target, command)
                            lock.write_bytes(before + b'\n# Simulated local-edge normalization\n')
                        else:
                            self.assertNotEqual(lock.read_bytes(), before)
                            self.assertIn('--locked', command)
                            self.assertIn('--offline', command)
                            self.assertIn(target, command)
                        return subprocess.CompletedProcess(command, 0)
                    with patch('ci_test_exports.subprocess.run', side_effect=execute):
                        self.assertEqual(run_tests(root, target, suite), 0)
                    self.assertEqual([c[1] for c in calls], ['fetch', 'metadata', 'test'])
                    self.assertEqual('large_export::tests' in calls[-1], suite == 'runtime')

    def test_registry_drift_after_metadata_stops_before_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = self.fixture(root, 'runtime')
            def execute(command, **kwargs):
                if command[1] == 'metadata':
                    with lock.open('a') as out:
                        out.write('\n[[package]]\nname = "unapproved"\nversion = "9.0.0"\n'
                                  'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
                                  'checksum = "changed"\n')
                return subprocess.CompletedProcess(command, 0)
            with patch('ci_test_exports.subprocess.run', side_effect=execute) as run:
                with self.assertRaises(AssertionError):
                    run_tests(root, 'aarch64-apple-darwin', 'runtime')
                self.assertEqual(run.call_count, 2)

    def test_fetch_pin_changes_stop_before_metadata_or_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = self.fixture(root, 'runtime')
            def execute(command, **kwargs):
                text = lock.read_text()
                start = text.index('checksum = "') + len('checksum = "')
                lock.write_text(text[:start] + 'changed' + text[start:])
                return subprocess.CompletedProcess(command, 0)
            with patch('ci_test_exports.subprocess.run', side_effect=execute) as run:
                with self.assertRaises(AssertionError):
                    run_tests(root, 'x86_64-pc-windows-msvc', 'runtime')
                self.assertEqual(run.call_count, 1)

    def test_corrupt_seed_is_rejected_before_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock = self.fixture(root, 'runtime')
            text = lock.read_text()
            start = text.index('checksum = "') + len('checksum = "')
            lock.write_text(text[:start] + 'changed' + text[start:])
            with patch('ci_test_exports.subprocess.run') as run:
                with self.assertRaises(AssertionError):
                    run_tests(root, 'x86_64-pc-windows-msvc', 'runtime')
                run.assert_not_called()

    def test_failed_download_does_not_run_metadata_or_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 'runtime')
            with patch('ci_test_exports.subprocess.run', side_effect=subprocess.CalledProcessError(101, 'cargo fetch')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    run_tests(root, 'x86_64-apple-darwin', 'runtime')
                self.assertEqual(run.call_count, 1)

    def test_failed_offline_resolution_after_fetch_does_not_run_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 'runtime')
            def execute(command, **kwargs):
                if command[1] == 'metadata':
                    raise subprocess.CalledProcessError(101, command)
                return subprocess.CompletedProcess(command, 0)
            with patch('ci_test_exports.subprocess.run', side_effect=execute) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    run_tests(root, 'aarch64-apple-darwin', 'runtime')
                self.assertEqual(run.call_count, 2)


if __name__ == '__main__':
    unittest.main()
