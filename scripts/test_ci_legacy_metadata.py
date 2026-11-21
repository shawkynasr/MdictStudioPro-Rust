"""Do not turn changed or missing historical failures into passing CI."""
import copy
import unittest
import contextlib
import io
from pathlib import Path
import tempfile
from unittest.mock import patch
import ci_legacy_metadata
from ci_legacy_metadata import load_baseline, verify_observation


class HistoricalMetadataCITests(unittest.TestCase):
    def setUp(self):
        self.baseline = load_baseline()

    def test_exact_historical_observation_retains_failed_status(self):
        verdict = verify_observation(self.baseline, self.baseline, 1)
        self.assertEqual(verdict['status'], 'archived_diagnostic_reproduced')
        self.assertEqual(verdict['diagnostic_status'], 'failed')
        self.assertFalse(verdict['metadata_qualified'])
        self.assertEqual(verdict['counts'], {'passed': 91, 'failed': 10, 'unsupported': 2, 'blocked': 8})

    def test_missing_added_or_changed_checks_fail_even_if_totals_unchanged(self):
        for alteration in ('missing', 'added', 'failure', 'unexpected_pass', 'reason', 'dependency'):
            with self.subTest(alteration=alteration):
                actual = copy.deepcopy(self.baseline)
                checks = actual['checks']
                passed = next(k for k, v in checks.items() if v['status'] == 'passed')
                failed = next(k for k, v in checks.items() if v['status'] == 'failed')
                blocked = next(k for k, v in checks.items() if v['status'] == 'blocked')
                if alteration == 'missing': del checks[passed]
                if alteration == 'added': checks['new-check'] = {'status': 'passed'}
                if alteration == 'failure': checks[passed]['status'] = 'failed'
                if alteration == 'unexpected_pass': checks[failed]['status'] = 'passed'
                if alteration == 'reason': checks[failed]['error'] = 'Unrelated corruption'
                if alteration == 'dependency': checks[blocked]['dependencies'] = ['unexpected']
                with self.assertRaises(ValueError):
                    verify_observation(actual, self.baseline, 1)

    def test_existing_report_directory_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(ci_legacy_metadata.sys, 'argv', ['ci_legacy_metadata.py', '--output', temp]), patch.object(ci_legacy_metadata.subprocess, 'run') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): ci_legacy_metadata.main()
                run.assert_not_called()

    def test_setup_exit_or_revision_drift_fails(self):
        for field, value in [('setup_error', 'No cargo'), ('writer_patch_revision', 4), ('counts', {}), ('status', 'passed')]:
            actual = copy.deepcopy(self.baseline)
            actual[field] = value
            with self.assertRaises(ValueError): verify_observation(actual, self.baseline, 1)
        for code in (0, 2, -9):
            with self.assertRaises(ValueError): verify_observation(self.baseline, self.baseline, code)


if __name__ == '__main__': unittest.main()
