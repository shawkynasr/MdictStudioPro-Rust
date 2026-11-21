"""Qualification must preserve duplicate payload association and trailing LF."""
import unittest
from fresh_pack import ordered,boundary_source,check_rows,legacy_fixture_records


class FreshPackContract(unittest.TestCase):
    def test_sort_ties_preserve_each_duplicate_payload(self):
        source=[('a-b','dash\n'),('ab','plain\n'),('a b','space\n'),('ab','second\n')]
        for profile in ['mdict-utils','mdxbuilder']:
            self.assertEqual(ordered(source,profile),source)
        resources=[('a-b',b'dash'),('ab',b'plain'),('a b',b'space')]
        self.assertEqual([k for k,v in ordered(resources,'mdict-utils',True)],['a b','a-b','ab'])

    def test_boundaries_retain_blank_lines_redirect_and_duplicates(self):
        entries=legacy_fixture_records(boundary_source())
        self.assertEqual(len(entries),16)
        self.assertEqual(sum(k=='apple' for k,v in entries),2)
        self.assertTrue(all(v.endswith('\n') for k,v in entries))
        self.assertIn('\n\nlast line\n',entries[0][1])
        self.assertEqual(entries[-1],('redirect','@@@LINK=和\n'))

    def test_exact_comparison_does_not_hide_loss_or_normalization(self):
        rows=[('a','first\n'),('a','second\n')]
        check_rows(rows,list(rows))
        for changed in [rows[:1],list(reversed(rows)),[('a','first'),rows[1]]]:
            with self.assertRaises(AssertionError):check_rows(rows,changed)


if __name__=='__main__':unittest.main()
