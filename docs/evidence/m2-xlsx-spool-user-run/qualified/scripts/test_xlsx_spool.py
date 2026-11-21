"""Independent row oracle, source isolation and framing contracts."""
import json
import unittest
from m2_sizing import ROOT,sha
from m2_xlsx_spool import protected_sources,fingerprints,REFERENCE
from xlsx_spool_lock import check_lock
from xlsx_spool_oracle import RowDigest,inspect

class DiskRowContracts(unittest.TestCase):
    def test_qualified_sources_and_exact_dependency_subset_are_unchanged(self):
        self.assertEqual(len(protected_sources()),241);self.assertEqual(len(check_lock()),52)
        self.assertIn('m2/xlsx-spool/src/rows.rs',fingerprints())
        ref=json.loads((ROOT/REFERENCE).read_text());self.assertFalse(ref['native_run'])
        for name,digest in ref['legacy_normalizer_sha256'].items():self.assertEqual(sha(ROOT/name),digest)
        self.assertEqual(ref['expected']['row_digest']['rows'],163909)
        self.assertEqual(ref['expected']['row_digest']['pairs'],2950362)
    def test_independent_oracle_matches_existing_captured_golden_rows(self):
        cases=json.loads((ROOT/'baseline/xlsx-reader-kit/expected.json').read_text())
        for name,case in cases.items():
            actual=inspect(ROOT/'baseline/xlsx-reader-kit'/case['file'],case.get('sheet'));digest=RowDigest()
            for row in case['rows']:digest.add(row)
            self.assertEqual(actual['headers'],case['headers'],name);self.assertEqual(actual['row_digest'],digest.finish(),name)
    def test_framing_preserves_row_order_empty_values_unicode_and_duplicate_rows(self):
        rows=[{'字詞名':'字','釋義':''},{'字詞名':'مرحبا','釋義':'a\nb'}]
        def digest(values):
            d=RowDigest()
            for value in values:d.add(value)
            return d.finish()
        want=digest(rows);self.assertEqual(want,digest([dict(reversed(list(r.items()))) for r in rows]))
        self.assertNotEqual(want,digest(list(reversed(rows))));self.assertNotEqual(want,digest(rows+rows[:1]));self.assertNotEqual(want,digest([{'字詞名':'字'},{'字詞名':'مرحبا','釋義':'a\nb'}]))

if __name__=='__main__':unittest.main()
