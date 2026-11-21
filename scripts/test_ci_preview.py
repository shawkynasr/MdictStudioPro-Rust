"""Check release input integrity, complete installer sets and publication boundaries."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import ci_prepare_desktop as bootstrap
from ci_collect_preview import collect, TARGETS

ROOT = Path(__file__).resolve().parents[1]


class PreviewCITests(unittest.TestCase):
    def test_rejects_archive_and_root_lock_drift(self):
        data = b'fixture crate'
        pin = hashlib.sha256(data).hexdigest()
        lock = {'package': [{'name': 'mdictlib', 'version': '0.2.8', 'checksum': pin}]}
        with patch.object(bootstrap, 'PIN', pin):
            bootstrap.verify_archive(data, lock)
            with self.assertRaises(ValueError):
                bootstrap.verify_archive(data + b'corruption', lock)
            with self.assertRaises(ValueError):
                bootstrap.verify_archive(data, {'package': []})
            with patch.object(bootstrap, 'MAX_BYTES', len(data) - 1):
                with self.assertRaises(ValueError):
                    bootstrap.verify_archive(data, lock)

    def test_installer_names_hashes_and_unqualified_report_per_target(self):
        for target, extensions in TARGETS.items():
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                bundle = root / 'm3/desktop/src-tauri/target' / target / 'release/bundle/test'
                bundle.mkdir(parents=True)
                for extension in extensions:
                    (bundle / ('preview' + extension)).write_bytes(b'native installer fixture')
                for relative in ['m3/fixtures/cedict.txt', 'docs/PRERELEASE-TESTING.md']:
                    p = root / relative
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text('fixture', encoding='utf-8')
                output = root / 'assets'
                report = collect(root, target, output, 'a' * 40)
                self.assertEqual(len(report['installers']), len(extensions))
                self.assertFalse(report['clean_machine_qualified'])
                self.assertFalse(report['runtime_launch_tested'])
                self.assertEqual(report['commit'], 'a' * 40)
                for row in report['installers']:
                    self.assertIn(target, row['name'])
                    self.assertEqual(row['sha256'], hashlib.sha256((output / row['name']).read_bytes()).hexdigest())
                with self.assertRaises(FileExistsError):
                    collect(root, target, output, 'a' * 40)

    def test_missing_installer_aborts_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, 'Missing installer'):
                collect(root, 'x86_64-unknown-linux-gnu', root / 'assets', 'sha')
            self.assertFalse((root / 'assets').exists())

    def test_preview_does_not_override_production_security(self):
        config = json.loads((ROOT / 'm3/desktop/src-tauri/tauri.ci.conf.json').read_text())
        self.assertNotIn('app', config)
        self.assertNotIn('build', config)
        self.assertEqual(config['bundle']['macOS']['signingIdentity'], '-')
        self.assertEqual(config['identifier'], 'com.mdictstudio.pro.rust.preview')

    def test_release_is_tag_only_draft_after_matrix_and_locked_builds(self):
        workflow = (ROOT / '.github/workflows/preview-builds.yml').read_text()
        for target in TARGETS:
            self.assertEqual(workflow.count('target: ' + target), 1)
        self.assertIn('needs: build', workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("contains(github.ref_name, '-preview.')", workflow)
        self.assertIn('--verify-tag --draft --prerelease', workflow)
        self.assertNotIn('pull_request_target', workflow)
        self.assertNotIn('--clobber', workflow)
        self.assertIn('npm ci', workflow)
        self.assertIn('--ci -- --locked', workflow)


if __name__ == '__main__':
    unittest.main()
