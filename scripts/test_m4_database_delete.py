"""Deletion oracle detects wrong duplicate removal even with regenerated digests."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_m4_database_metadata import write
from verify_database_delete import check


class EntryDeleteOracleTests(unittest.TestCase):
    def test_exact_duplicate_metadata_and_order_are_checked(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','first'),('字','second'),('empty','')]
            attrs={'Title':'keep','Description':'same','Encoding':'UTF-16'}
            write(source,rows,attrs,'a'*64);origin=hashlib.sha256(source.read_bytes()).hexdigest()
            expected=[rows[0],rows[2]]
            write(copy,expected,attrs,origin)
            self.assertEqual(check(source,copy,'2')['records'],2)
            for values,header in [([rows[1],rows[2]],attrs),(list(reversed(expected)),attrs),
                                  (expected,{**attrs,'Title':'changed'}),(rows,attrs),([rows[0]],attrs)]:
                write(copy,values,header,origin)
                with self.assertRaises(AssertionError):check(source,copy,'2')

    def test_sparse_ids_and_large_bodies_are_not_renumbered_before_selection(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','x'*9000),('字','second'),('empty','')];attrs={'Title':'same'}
            write(source,rows,attrs,'a'*64)
            with sqlite3.connect(source) as c:
                c.execute('UPDATE mdx SET rowid=-2 WHERE rowid=1')
                c.execute('UPDATE mdx SET rowid=7 WHERE rowid=2')
                c.execute('UPDATE mdx SET rowid=99 WHERE rowid=3')
            c.close();origin=hashlib.sha256(source.read_bytes()).hexdigest()
            for rowid,index in [('-2',0),('7',1),('99',2)]:
                write(copy,[r for i,r in enumerate(rows) if i!=index],attrs,origin)
                self.assertEqual(check(source,copy,rowid)['records'],2)
            for rowid in ['2','07','+7','-0','9223372036854775808']:
                with self.assertRaises(AssertionError):check(source,copy,rowid)

    def test_only_entry_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            write(source,[('only','')],{'Title':'keep'},'a'*64)
            with self.assertRaises(AssertionError):check(source,copy,'1')
