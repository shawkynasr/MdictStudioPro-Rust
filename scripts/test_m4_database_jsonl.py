"""Tamper checks for the independent SQLite/JSONL verifier."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from m4_database import MDX_SQL
from verify_database_jsonl import check, read_jsonl


class JsonlOracleTests(unittest.TestCase):
    def test_export_oracle_checks_duplicates_order_controls_and_source_immutability(self):
        rows = [('字', 'first\r\n\n</>\n"quoted"\\tail\0'), ('字', 'second'), ('مرحبا', ''), ('empty', '')]
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            database, output = folder / 'source.db', folder / 'rows.jsonl'
            connection = sqlite3.connect(database)
            connection.execute(MDX_SQL)
            connection.executemany('INSERT INTO mdx VALUES (?,?)', rows)
            connection.commit()
            connection.close()
            before = database.read_bytes()

            def write(values):
                output.write_bytes(b''.join(json.dumps({'key': k, 'text': t}, ensure_ascii=False).encode() + b'\n' for k, t in values))

            write(rows)
            self.assertEqual(check(database, output)['records'], 4)
            self.assertEqual(read_jsonl(output), rows)
            for values in [rows[:-1], list(reversed(rows)), [rows[0], rows[0], *rows[2:]], [('字', 'changed'), *rows[1:]]]:
                write(values)
                with self.assertRaises(AssertionError):
                    check(database, output)
            self.assertEqual(database.read_bytes(), before)

    def test_jsonl_shape_and_complete_lines_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'bad.jsonl'
            for data in [b'{"key":"a","text":"body"}', b'\n', b'[]\n',
                         b'{"key":"a","text":null}\n', b'{"key":"a","text":"b","rowid":1}\n',
                         b'{"key":"a","key":"b","text":"body"}\n', b'\xef\xbb\xbf{"key":"a","text":"b"}\n',
                         b'{"key":"a","text":"\xff"}\n']:
                output.write_bytes(data)
                with self.assertRaises((AssertionError, ValueError, UnicodeError)):
                    read_jsonl(output)
