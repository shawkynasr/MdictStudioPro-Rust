import unittest
from unicode_profiles import words,scalar_lower,lookup,mapping_differences


class UnicodeProfiles(unittest.TestCase):
    def test_contextual_lowercase_and_exact_first_are_distinct_contracts(self):
        self.assertEqual('ΟΣ'.lower(),'ος');self.assertEqual(scalar_lower('ΟΣ'),'οσ')
        rows=[{'key':'ΟΣ','text':'upper'},{'key':'ος','text':'final'},{'key':'οσ','text':'ordinary'}]
        self.assertEqual(lookup(rows,'ΟΣ'),[rows[0]])
        self.assertEqual(lookup(rows,'οΣ'),[rows[0],rows[2]])
        self.assertEqual(lookup([{'key':'ß','text':'sharp'}],'SS'),[])

    def test_single_scalar_scan_is_exhaustive_and_detects_wrong_mappings(self):
        import unicodedata
        pairs=[[n,chr(n).lower()] for n in range(0x110000) if not 0xd800<=n<=0xdfff and chr(n).lower()!=chr(n)]
        value={'scalars_scanned':0x110000-0x800,'changed_scalar_mappings':pairs}
        count,diff=mapping_differences(value);self.assertEqual(count,len(pairs));self.assertEqual(diff,[])
        value['changed_scalar_mappings']=[p for p in pairs if p[0]!=ord('A')]
        self.assertEqual(mapping_differences(value)[1],[{'codepoint':'U+0041','input':'A','python':'a','rust':'A'}])
        value['scalars_scanned']=1
        with self.assertRaises(AssertionError):mapping_differences(value)

    def test_fixture_contains_distinguishable_unicode_order_and_normalization_cases(self):
        self.assertEqual(len(words()),len(set(words())))
        for key in ['Ａ','𐐀','é','e\u0301','İ','i\u0307','a\\b','a\u00a0b']:self.assertIn(key,words())


if __name__=='__main__':unittest.main()
