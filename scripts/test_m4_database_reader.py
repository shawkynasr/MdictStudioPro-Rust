"""Tamper checks for the independent persistent reader page oracle."""
import copy
import unittest
from m4_database_reader import check_page


class PersistentReaderOracleTests(unittest.TestCase):
    def test_page_oracle_rejects_lost_duplicates_wrong_rowids_and_stale_offsets(self):
        rows = [{'rowid': '1', 'key': '字', 'text': 'first'},
                {'rowid': '4', 'key': '字', 'text': 'second'},
                {'rowid': '8', 'key': '字典', 'text': 'third'}]
        page = {'profile': 'studio-sqlite-text-v1', 'source_sha256': 'a' * 64,
                'total': 3, 'offset': 0, 'next_offset': 2, 'rows': rows[:2]}
        check_page(page, rows, 'a' * 64, 0)
        for field, value in [('total', 2), ('offset', 2), ('next_offset', None),
                             ('source_sha256', 'b' * 64), ('rows', rows[:1]),
                             ('rows', list(reversed(rows[:2])))]:
            changed = copy.deepcopy(page)
            changed[field] = value
            with self.assertRaises(AssertionError):
                check_page(changed, rows, 'a' * 64, 0)
        changed = copy.deepcopy(page)
        changed['rows'][1]['rowid'] = '2'
        with self.assertRaises(AssertionError):
            check_page(changed, rows, 'a' * 64, 0)

    def test_empty_and_last_page_require_no_next_offset(self):
        page = {'profile': 'studio-sqlite-text-v1', 'source_sha256': 'a' * 64,
                'total': 0, 'offset': 0, 'next_offset': None, 'rows': []}
        check_page(page, [], 'a' * 64, 0)
        page['next_offset'] = 0
        with self.assertRaises(AssertionError):
            check_page(page, [], 'a' * 64, 0)
