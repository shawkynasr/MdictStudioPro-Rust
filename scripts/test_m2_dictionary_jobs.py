import tempfile
import unittest
from pathlib import Path
from m2_dictionary_jobs import make_cases,protected_sources,fingerprints
from application_lock import check_lock
from m2_text import reference_rows

class DictionaryJobContracts(unittest.TestCase):
    def test_qualified_core_facade_and_locks_are_unchanged_except_reviewed_runner_dispatch(self):
        self.assertEqual(len(protected_sources()),95);self.assertEqual(len(check_lock()),60)
        self.assertIn('m2/application/src/runner/dictionary.rs',fingerprints())
    def test_matrix_covers_encodings_profiles_resources_failures_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases,resources,source=make_cases(Path(tmp));self.assertEqual(len(cases),19)
            self.assertEqual(sum('refusal' not in c for c in cases),12)
            self.assertEqual({c['refusal'] for c in cases if 'refusal' in c},{'destination_exists','unsafe_path','path_collision','io','malformed_source'})
            self.assertEqual(len(resources),6);self.assertTrue(any(not r['bytes'] for r in resources));self.assertTrue(any(len(r['bytes'])==256 for r in resources))
            self.assertEqual(len(reference_rows(source.read_bytes(),'canonical_v1')),13)
            self.assertEqual(cases[-1]['label'],'recovery-export')

if __name__=='__main__':unittest.main()
