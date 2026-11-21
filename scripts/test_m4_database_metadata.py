"""Tamper the independent metadata-copy oracle, including consistent forged digests."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from m4_database import APP_ID, MDX_SQL, META_SQL, framed
from verify_database_metadata import check


def write(path, rows, attrs, origin):
    if path.exists():
        path.unlink()
    raw = json.dumps(attrs, ensure_ascii=False, separators=(',', ':'))
    with sqlite3.connect(path) as c:
        c.execute(MDX_SQL)
        c.executemany('INSERT INTO mdx VALUES (?,?)', rows)
        c.execute(META_SQL)
        c.execute(f'PRAGMA application_id={APP_ID}')
        c.execute('PRAGMA user_version=2')
        c.executemany('INSERT INTO studio_meta VALUES (?,?)', [
            ('profile', 'studio-sqlite-mdx-v1'), ('text_profile', 'canonical_v1'),
            ('source_sha256', origin), ('records', str(len(rows))), ('rows_sha256', framed(rows)),
            ('mdx_header_json', raw), ('mdx_header_sha256', hashlib.sha256(raw.encode()).hexdigest())])
    c.close()


class MetadataCopyOracleTests(unittest.TestCase):
    def test_oracle_rejects_row_changes_and_unselected_metadata_even_with_updated_digests(self):
        rows = [('字', '`2`first\r\n'), ('字', 'second'), ('مرحبا', 'أهلاً'), ('empty', '')]
        attrs = {'Title': 'before', 'Description': 'original', 'StyleSheet': '2\n<b>\n</b>\n', 'Encoding': 'UTF-16'}
        with tempfile.TemporaryDirectory() as d:
            source, copy = Path(d)/'source.db', Path(d)/'copy.db'
            write(source, rows, attrs, 'a'*64)
            before = source.read_bytes()
            origin = hashlib.sha256(before).hexdigest()
            edited = {**attrs, 'Title': 'new 字'}
            write(copy, rows, edited, origin)
            self.assertEqual(check(source, copy, {'title': 'new 字'})['records'], 4)
            for forged_rows, forged_attrs, forged_origin in [
                (list(reversed(rows)), edited, origin),
                ([rows[0], rows[0], *rows[2:]], edited, origin),
                (rows, {**edited, 'StyleSheet': 'changed'}, origin),
                (rows, {**edited, 'Description': 'changed'}, origin),
                (rows, edited, '0'*64)]:
                write(copy, forged_rows, forged_attrs, forged_origin)
                with self.assertRaises(AssertionError):
                    check(source, copy, {'title': 'new 字'})
            self.assertEqual(source.read_bytes(), before)

    def test_selected_empty_values_clear_fields_and_unselected_fields_stay(self):
        with tempfile.TemporaryDirectory() as d:
            source, copy = Path(d)/'source.db', Path(d)/'copy.db'
            rows = [('empty', '')]
            attrs = {'Title': 'before', 'Description': 'keep', 'Encoding': 'UTF-8'}
            write(source, rows, attrs, 'a'*64)
            write(copy, rows, {**attrs, 'Title': ''}, hashlib.sha256(source.read_bytes()).hexdigest())
            result = check(source, copy, {'title': ''})
            self.assertEqual(result['title'], '')
            self.assertEqual(result['description'], 'keep')
            with self.assertRaises(AssertionError):
                check(source, copy, {})

    def test_stylesheet_selection_uses_exact_header_name_and_preserves_title(self):
        with tempfile.TemporaryDirectory() as d:
            source, copy = Path(d)/'source.db', Path(d)/'copy.db'
            rows = [('字', '`2`first'), ('字', '`2`second')]
            attrs = {'Title': 'keep', 'Description': 'keep description', 'StyleSheet': '2\n<b>\n</b>\n', 'Encoding': 'UTF-8'}
            style = '2\n<span style="color:#008000">\n</span>\n'
            write(source, rows, attrs, 'a'*64)
            origin = hashlib.sha256(source.read_bytes()).hexdigest()
            write(copy, rows, {**attrs, 'StyleSheet': style}, origin)
            self.assertEqual(check(source, copy, {'stylesheet': style})['title'], 'keep')
            write(copy, rows, {**attrs, 'StyleSheet': style, 'Title': 'changed'}, origin)
            with self.assertRaises(AssertionError):
                check(source, copy, {'stylesheet': style})
