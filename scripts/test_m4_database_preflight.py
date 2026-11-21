"""Preflight counts bytes, stops early and cannot claim native qualification."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib
import m4_database_preflight as p
import m4_database_sizing as sizing


def mdx_header(path):
    raw=('<Dictionary Encoding="UTF-8" Title="fixture"/>\0').encode('utf-16le')
    path.write_bytes(struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff))


class PreflightTests(unittest.TestCase):
    def test_record_violation_stops_at_first_crossing_and_marks_prefix_counts(self):
        def stream():
            yield 'a','';yield 'a','';yield 'a',''
            raise AssertionError('Should stop before consuming the rest')
        with patch.object(p,'RECORD_CAP',2):result,rows=p.scan_rows(stream(),True)
        self.assertEqual(result['first_issue'],{'name':'record_count','observed':3,'maximum':2,'record_ordinal':3})
        self.assertEqual(result['counts_scope'],'observed_prefix_only');self.assertFalse(result['scan_complete']);self.assertEqual(rows,[])

    def test_utf8_bytes_and_other_limits_are_identified_without_trimming(self):
        with patch.object(p,'DECODED_CAP',6):
            result,_=p.scan_rows([('字','甲'),('字','甲')])
        self.assertEqual(result['first_issue']['name'],'decoded_text_bytes');self.assertEqual(result['first_issue']['observed'],12)
        for row,name in [(('字'*1366,''),'headword_bytes'),(('a','x'*(p.BODY_CAP+1)),'definition_bytes'),(('</>',''),'invalid_headword')]:
            result,_=p.scan_rows([row]);self.assertEqual(result['first_issue']['name'],name)
        expected=[(' 字 مرحبا %_*? ',''),('duplicate','first'),('duplicate','second')]
        result,rows=p.scan_rows(expected,True);self.assertEqual(rows,expected)
        self.assertEqual(result['status'],'fits_size_profile');self.assertEqual(result['counts_scope'],'whole_dictionary')
        self.assertEqual(p.scan_rows([])[0]['status'],'invalid_input')

    def test_header_read_hashes_and_retained_rows_match_read_only_scan(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fixture.mdx';mdx_header(path);before=path.read_bytes()
            class Reader:
                def __init__(self,path,substyle):assert substyle is False
                def items(self):yield b'duplicate',b'first';yield '字','second'
            result,rows,attrs=p.inspect_mdx(path,True,Reader)
            self.assertEqual(result['status'],'fits_size_profile');self.assertTrue(result['source_unchanged'])
            self.assertEqual(result['records_observed'],2);self.assertEqual(rows,[('duplicate','first'),('字','second')]);self.assertEqual(attrs['Title'],'fixture')
            self.assertEqual(p.inspect_mdx(path,False,Reader)[1],[]);self.assertEqual(path.read_bytes(),before)
            path.write_bytes(before[:-1]+bytes([before[-1]^1]))
            with self.assertRaises(ValueError):p.inspect_mdx(path,reader_factory=Reader)

    def test_file_cap_skips_decoding_and_source_mutation_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fixture.mdx';mdx_header(path)
            with patch.object(p,'FILE_CAP',1):result,rows,_=p.inspect_mdx(path,reader_factory=lambda *a,**k:self.fail('No decoder expected'))
            self.assertEqual(result['first_issue']['name'],'file_bytes');self.assertEqual(result['counts_scope'],'not_decoded')
            class ChangedReader:
                def __init__(self,*a,**k):pass
                def items(self):
                    yield 'a',''
                    path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Source changed'):p.inspect_mdx(path,reader_factory=ChangedReader)

    def test_sizing_rejection_writes_report_before_any_native_step(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fixture.mdx';mdx_header(path);out=Path(d)/'m4-database-out-rejected'
            result={'status':'exceeds_size_profile','source':{'name':path.name,'sha256':p.sha(path),'bytes':path.stat().st_size},'first_issue':{'name':'record_count','observed':100001,'maximum':100000}}
            with patch('sys.argv',['sizing','--output',str(out),'--mdx',str(path)]),patch.object(sizing,'inventory',return_value={}),patch.object(sizing,'sources',return_value={}),patch.object(sizing,'inspect_mdx',return_value=(result,[],None)),patch.object(sizing.shutil,'which',side_effect=AssertionError('Native lookup must not run')),redirect_stdout(io.StringIO()):
                self.assertEqual(sizing.main(),1)
            report=json.loads((out/'report.json').read_text());self.assertEqual(report['status'],'preflight_rejected_choose_supported_dictionary')
            self.assertEqual(report['steps'],[]);self.assertFalse(report['native_tests_executed']);self.assertFalse(report['native_jobs_executed'])
