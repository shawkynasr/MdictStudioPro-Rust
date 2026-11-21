import hashlib
import json
import unittest
from integrated_casing import ROOT,SHA16,fixture,expected_lookup


class IntegratedCasing(unittest.TestCase):
    def test_embedded_policy_is_exactly_the_reviewed_upload(self):
        path=ROOT/'baseline/unicode/unicode16-casing.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),SHA16)
        data=json.loads(path.read_text());self.assertEqual(data['unicode_version'],'16.0.0')
        self.assertEqual(len(data['lower_mappings']),1460)

    def test_exact_first_preserves_duplicate_identity_and_order(self):
        rows=[{'key':'ΟΣ','text':'one'},{'key':'ος','text':'other'},{'key':'ΟΣ','text':'two'}]
        norms={'ΟΣ':'ος','ος':'ος','Ος':'ος','missing':'missing'}
        self.assertEqual(expected_lookup(rows,'ΟΣ',norms),[rows[0],rows[2]])
        self.assertEqual(expected_lookup(rows,'Ος',norms),rows)
        self.assertEqual(expected_lookup(rows,'missing',norms),[])

    def test_fixture_distinguishes_unicode16_from_unicode17(self):
        report=json.loads((ROOT/'docs/evidence/unicode-version-user-run/unicode-profile-report.json').read_text())
        rows,queries=fixture(report['lowercase_mapping']['differences'])
        self.assertEqual(sum(r['key']=='duplicate' for r in rows),8)
        self.assertEqual(sum(r['key']=='ΟΣ' for r in rows),2)
        self.assertIn('A꟎Σ',[r['key'] for r in rows]);self.assertIn('a꟏Σ',queries)
        self.assertLess(len(rows),1000);self.assertLess(len(queries),1024)


if __name__=='__main__':unittest.main()
