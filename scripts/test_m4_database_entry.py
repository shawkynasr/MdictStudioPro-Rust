"""Independent oracle refuses a changed sibling duplicate even with valid new digests."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from m4_database import MDX_SQL
from test_m4_database_metadata import write
from verify_database_entry import check


class EntryCopyOracleTests(unittest.TestCase):
    def test_exact_duplicate_and_metadata_are_checked_after_digest_regeneration(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','first'),('字','second'),('empty','')]
            attrs={'Title':'keep','Description':'same','Encoding':'UTF-8'}
            write(source,rows,attrs,'a'*64);origin=hashlib.sha256(source.read_bytes()).hexdigest()
            expected=[rows[0],('字','edited'),rows[2]]
            write(copy,expected,attrs,origin)
            self.assertEqual(check(source,copy,'2','edited')['output_rowid'],'2')
            for values,header in [([('字','edited'),rows[1],rows[2]],attrs),
                                  (expected,{**attrs,'Title':'changed'}),
                                  ([rows[0],('字','edited'),('empty','changed')],attrs)]:
                write(copy,values,header,origin)
                with self.assertRaises(AssertionError):check(source,copy,'2','edited')

    def test_sparse_source_ids_are_distinct_from_output_row_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            with sqlite3.connect(source) as c:
                c.execute(MDX_SQL)
                c.executemany('INSERT INTO mdx(rowid,entry,paraphrase) VALUES (?,?,?)',[(-2,'字','first'),(7,'字','second')])
            c.close()
            # The normal writer creates canonical row IDs and text-profile metadata.
            import json
            from m4_database import APP_ID,framed,META_SQL
            with sqlite3.connect(copy) as c:
                c.execute(MDX_SQL);c.executemany('INSERT INTO mdx VALUES (?,?)',[('字','first'),('字','')])
                c.execute(META_SQL);c.execute(f'PRAGMA application_id={APP_ID}');c.execute('PRAGMA user_version=1')
                c.executemany('INSERT INTO studio_meta VALUES (?,?)',[('profile','studio-sqlite-text-v1'),('records','2'),('rows_sha256',framed([('字','first'),('字','')])),('source_sha256',hashlib.sha256(source.read_bytes()).hexdigest()),('text_profile','canonical_v1')])
            c.close()
            result=check(source,copy,'7','');self.assertEqual((result['source_rowid'],result['output_rowid']),('7','2'))
            with self.assertRaises(AssertionError):check(source,copy,'2','')

    def test_rename_selects_one_duplicate_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            source,copy=Path(d)/'source.db',Path(d)/'copy.db'
            rows=[('字','first'),('字','second'),('empty','')]
            attrs={'Title':'keep','Encoding':'UTF-16'}
            write(source,rows,attrs,'a'*64);origin=hashlib.sha256(source.read_bytes()).hexdigest()
            for key in ['empty',' renamed 字 مرحبا %_*? ']:
                expected=[rows[0],(key,'second'),rows[2]]
                write(copy,expected,attrs,origin)
                self.assertEqual(check(source,copy,'2','second',key)['records'],3)
                with self.assertRaises(AssertionError):check(source,copy,'1','second',key)
                with self.assertRaises(AssertionError):check(source,copy,'2','second')
            for key in ['', '</>', 'a\n', 'a\0', '字'*1366]:
                with self.assertRaises(AssertionError):check(source,copy,'2','second',key)
