"""Addition oracle rejects replacement/merging and metadata changes despite valid digests."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from test_m4_database_metadata import write
from verify_database_add import check


class EntryAddOracleTests(unittest.TestCase):
    def test_duplicate_appends_without_changing_siblings_or_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','first'),('字','second'),('empty','')];attrs={'Title':'keep','Encoding':'UTF-16'}
            write(source,rows,attrs,'a'*64);origin=hashlib.sha256(source.read_bytes()).hexdigest()
            expected=rows+[('字','third')]
            write(copy,expected,attrs,origin)
            self.assertEqual(check(source,copy,'字','third')['output_rowid'],'4')
            for values,header in [(rows[:1]+[('字','third')]+rows[2:],attrs),
                                  (expected+[('字','third')],attrs),(list(reversed(expected)),attrs),
                                  (expected,{**attrs,'Title':'changed'}),(rows,attrs)]:
                write(copy,values,header,origin)
                with self.assertRaises(AssertionError):check(source,copy,'字','third')

    def test_sparse_source_and_literal_empty_definition(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','x'*9000),('字','second')];attrs={'Title':'same'}
            write(source,rows,attrs,'a'*64)
            with sqlite3.connect(source) as c:
                c.execute('UPDATE mdx SET rowid=-2 WHERE rowid=1');c.execute('UPDATE mdx SET rowid=99 WHERE rowid=2')
            c.close();origin=hashlib.sha256(source.read_bytes()).hexdigest();key=' 字 مرحبا %_*? '
            write(copy,rows+[(key,'')],attrs,origin)
            self.assertEqual(check(source,copy,key,'')['records'],3)
            for bad in ['', '</>', 'a\n', 'a\0', '字'*1366]:
                with self.assertRaises(AssertionError):check(source,copy,bad,'')
            with self.assertRaises(AssertionError):check(source,copy,key,'x'*8193)
