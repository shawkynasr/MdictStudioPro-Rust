import unittest
from casing_policy import property_flags,intervals,contexts


class VersionedCasing(unittest.TestCase):
    def test_cased_and_ignorable_are_independent_properties(self):
        self.assertEqual(property_flags('A'),(True,False))
        self.assertEqual(property_flags('-'),(False,False))
        self.assertEqual(property_flags('\u0301'),(False,True))
        self.assertEqual(property_flags('\u0345'),(True,True))
        self.assertEqual(property_flags("'"),(False,True))

    def test_ranges_preserve_property_membership_and_gaps(self):
        self.assertEqual(intervals([0,1,3,7,8]),[[0,1],[3,3],[7,8]])
        self.assertEqual(intervals([]),[])

    def test_contexts_cover_new_cased_characters_both_sides_of_sigma(self):
        sample=[{'input':'\U00016ea0'}]
        a=contexts(sample);self.assertEqual(a,contexts(sample))
        self.assertEqual(len(a),len(set(a)));self.assertLess(len(a),4096)
        for word in ['\U00016ea0Σ','AΣ\U00016ea0A','\u0345Σ','AΣ\u0345']:self.assertIn(word,a)


if __name__=='__main__':unittest.main()
