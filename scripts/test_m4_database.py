"""Checks for the independent SQLite oracle, not a substitute for Rust tests."""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from m4_database import APP_ID,META_SQL,MDX_SQL,check_database,framed,readonly


class DatabaseOracleTests(unittest.TestCase):
    def test_prefix_sql_matches_python_literal_prefix_and_exact_pagination(self):
        import re
        root = Path(__file__).resolve().parents[1]
        source = (root / 'm4/database/src/lib.rs').read_text()
        count_sql = re.search(r'query_row\("(SELECT count\(\*\) FROM mdx WHERE [^"\n]+)"', source).group(1)
        page_sql = re.search(r'prepare\("(SELECT rowid,entry,paraphrase FROM mdx WHERE [^"\n]+)"', source).group(1)
        keys = ['apple', 'application', 'Apple', 'apple', 'a%b', 'a_b', 'a?b', 'a b', '字典', '字', 'مرحبا', 'مرح']
        connection = sqlite3.connect(':memory:')
        try:
            connection.execute(MDX_SQL)
            connection.executemany('INSERT INTO mdx VALUES (?,?)', [(k, str(i)) for i, k in enumerate(keys)])
            for query in ['app', 'App', 'a%', 'a_', 'a?', 'a ', '字', 'مر', '%', "' OR 1=1 --", None]:
                for prefix in [False, True]:
                    expected = [(i + 1, key, str(i)) for i, key in enumerate(keys)
                                if query is None or (key.startswith(query) if prefix else key == query)]
                    self.assertEqual(connection.execute(count_sql, (query, prefix)).fetchone()[0], len(expected))
                    for offset in range(0, len(expected) + 2):
                        actual = connection.execute(page_sql, (query, prefix, 2, offset)).fetchall()
                        self.assertEqual(actual, expected[offset:offset + 2])
        finally:
            connection.close()

    def test_gui_cancel_check_catches_output_staging_and_source_changes(self):
        from m4_gui_cancel import prepare, check, SOURCE, DESTINATION
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'fixture'
            prepare(folder, count=3)
            self.assertEqual(check(folder)['status'], 'filesystem_checks_passed_GUI_state_pending')
            destination = folder / 'results' / DESTINATION
            destination.write_bytes(b'completed output')
            self.assertFalse(check(folder)['destination_absent'])
            destination.unlink()
            stage = folder / 'results' / '.private-stage'
            stage.mkdir()
            self.assertEqual(check(folder)['unexpected_result_paths'], ['.private-stage'])
            stage.rmdir()
            with (folder / SOURCE).open('ab') as stream:
                stream.write(b'changed')
            self.assertFalse(check(folder)['source_unchanged'])
            with self.assertRaises(FileExistsError):
                prepare(folder, count=3)

    def test_failure_runner_refuses_zero_tests_and_failed_tests(self):
        from m4_database_failures import require_one_test
        require_one_test('test result: ok. 1 passed; 0 failed; 15 filtered out; finished in 0.1s')
        for log in ['test result: ok. 0 passed; 0 failed;',
                    'test result: FAILED. 0 passed; 1 failed;',
                    'test result: ok. 2 passed; 0 failed;', '']:
            with self.assertRaises(RuntimeError):
                require_one_test(log)

    def test_mdx_header_preserves_literal_stylesheet_whitespace_and_entities(self):
        from verify_mdx_database import header_attributes
        xml = '<Dictionary StyleSheet="2\n&lt;span style=&quot;color:#0000ff&quot;&gt;\n&lt;/span&gt;\n" Description=\'a&#10;b &amp; c &quot;x&quot;\' Title="字 العربية" />'
        attrs = header_attributes(xml)
        self.assertEqual(attrs['StyleSheet'], '2\n<span style="color:#0000ff">\n</span>\n')
        self.assertEqual(attrs['Description'], 'a\nb & c "x"')
        self.assertEqual(attrs['Title'], '字 العربية')
        self.assertEqual(header_attributes('<Dictionary Description="&amp;#10;\t\r\n"/>')['Description'], '&#10;\t\r\n')

    def test_mdx_header_does_not_repair_malformed_xml(self):
        import xml.etree.ElementTree as ET
        from verify_mdx_database import header_attributes
        for xml in ['<Dictionary StyleSheet="2\n<b>\n</b>\n"/>', '<Dictionary Title="unclosed/>']:
            with self.assertRaises(ET.ParseError):
                header_attributes(xml)
        with self.assertRaises(AssertionError):
            header_attributes('<Library_Data/>')

    def test_rebuilt_oracle_allows_key_sort_but_rejects_duplicate_reordering(self):
        from verify_database_mdx import check
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'dictionary.db';rows=[('z','last'),('a','first'),('a','second')];self.create(path,rows)
            attrs={'Title':'dictionary','Description':'','StyleSheet':'','Encoding':'UTF-8','KeyCaseSensitive':'No','StripKey':'No'}
            sorted_rows=[rows[1],rows[2],rows[0]]
            self.assertEqual(check(path,sorted_rows,attrs)['status'],'passed')
            for bad in [[rows[2],rows[1],rows[0]],sorted_rows[:-1]]:
                with self.assertRaises(AssertionError):check(path,bad,attrs)
            with self.assertRaises(AssertionError):check(path,sorted_rows,{**attrs,'Title':'changed'})
    def test_mdx_oracle_rejects_metadata_and_record_corruption(self):
        import json
        from verify_mdx_database import check
        rows=[('字','`2`blue\n\n'),('字','second')]
        attrs={'Title':'字 / العربية','StyleSheet':'2\n<b>\n</b>\n'}
        raw=json.dumps(attrs,ensure_ascii=False,separators=(',',':'))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'mdx.db';source_hash=self.create(path,rows)
            with sqlite3.connect(path) as c:
                c.execute('PRAGMA user_version=2')
                c.execute("UPDATE studio_meta SET value='studio-sqlite-mdx-v1' WHERE key='profile'")
                c.executemany('INSERT INTO studio_meta VALUES (?,?)',[('mdx_header_json',raw),('mdx_header_sha256',hashlib.sha256(raw.encode()).hexdigest())])
            c.close()
            self.assertEqual(check(path,rows,attrs,source_hash)['records'],2)
            for expected_rows,expected_attrs in [(list(reversed(rows)),attrs),(rows,{**attrs,'StyleSheet':'changed'})]:
                with self.assertRaises(AssertionError):check(path,expected_rows,expected_attrs,source_hash)
    def create(self,path,rows):
        source_hash=hashlib.sha256(b'original input bytes').hexdigest()
        with sqlite3.connect(path) as connection:
            connection.execute(f'PRAGMA application_id={APP_ID}')
            connection.execute('PRAGMA user_version=1')
            connection.execute(MDX_SQL)
            connection.execute(META_SQL)
            connection.executemany('INSERT INTO mdx VALUES (?,?)',rows)
            connection.executemany('INSERT INTO studio_meta VALUES (?,?)',[
                ('profile','studio-sqlite-text-v1'),('records',str(len(rows))),
                ('rows_sha256',framed(rows)),('source_sha256',source_hash),('text_profile','canonical_v1')])
        connection.close()
        return source_hash

    def test_oracle_catches_changed_bodies_missing_duplicates_and_order(self):
        rows=[('字','first\n\nline'),('字',''),('مرحبا','العربية')]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'dict.db';digest=self.create(path,rows)
            self.assertEqual(check_database(path,rows,digest)['records'],3)
            for expected in [rows[:1]+rows[2:],list(reversed(rows)),[('字','changed')]+rows[1:]]:
                with self.assertRaises(AssertionError):check_database(path,expected,digest)
            with sqlite3.connect(path) as connection:connection.execute("UPDATE mdx SET paraphrase='changed' WHERE rowid=1")
            connection.close()
            with self.assertRaises(AssertionError):check_database(path,rows,digest)

    def test_framed_digest_distinguishes_boundaries_order_and_duplicate_counts(self):
        self.assertNotEqual(framed([('a','bc')]),framed([('ab','c')]))
        self.assertNotEqual(framed([('a','1'),('a','2')]),framed([('a','2'),('a','1')]))
        self.assertNotEqual(framed([('a','1')]),framed([('a','1'),('a','1')]))

    def test_readonly_oracle_quotes_uri_paths_and_does_not_modify_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'字 ?#%.db';self.create(path,[('hello','world')]);before=path.read_bytes()
            connection=readonly(path)
            try:
                self.assertEqual(connection.execute('SELECT entry FROM mdx').fetchone()[0],'hello')
                with self.assertRaises(sqlite3.OperationalError):connection.execute('DELETE FROM mdx')
            finally:connection.close()
            self.assertEqual(path.read_bytes(),before)
