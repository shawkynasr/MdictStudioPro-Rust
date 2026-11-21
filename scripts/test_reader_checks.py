"""Local harness contract tests; no native application or engine pass implied."""
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib
import real_corpus
from reader_fixtures import crlf_header,specification
from v2_audit import block,css_urls


class CorpusContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.db=real_corpus.connect(self.root/"rows.sqlite")

    def tearDown(self):
        self.db.close();self.tmp.cleanup()

    def lines(self,rows,kind="mdx",end=True):
        messages=[{"type":"header","kind":kind,"attributes":{}}]
        messages += [{"type":"row",**row} for row in rows]
        if end: messages.append({"type":"end","records":len(rows)})
        return [json.dumps(row) for row in messages]

    def test_duplicate_counts_and_whitespace_are_significant(self):
        rows=[{"key":"字","text":"body\n"}]*2
        real_corpus.ingest(self.lines(rows),self.db,"r","mdx")
        real_corpus.ingest(self.lines(rows[:1]),self.db,"p","mdx")
        self.assertEqual(real_corpus.differences(self.db),1)
        real_corpus.record(self.db,"p","字",b"body\n")
        self.assertEqual(real_corpus.differences(self.db),0)
        real_corpus.record(self.db,"p","字",b"body")
        self.assertEqual(real_corpus.differences(self.db),1)

    def test_truncated_worker_never_becomes_a_complete_scan(self):
        with self.assertRaisesRegex(AssertionError,"no end marker"):
            real_corpus.ingest(self.lines([{"key":"a","text":"body"}],end=False),self.db,"r","mdx")

    def test_binary_resources_and_exact_keys_remain_distinct(self):
        rows=[{"key":"\\字.bin","bytes":[0,255,128,0]}]
        real_corpus.ingest(self.lines(rows,"mdd"),self.db,"r","mdd")
        real_corpus.ingest(self.lines(rows,"mdd"),self.db,"p","mdd")
        self.assertEqual(real_corpus.differences(self.db),0)
        real_corpus.record(self.db,"p","\\字.BIN",bytes([0,255,128,0]))
        self.assertEqual(real_corpus.differences(self.db),1)

    def test_manifest_discovery_is_read_only_and_refuses_overwrite(self):
        path=self.root/"sample.mdx";path.write_bytes(b"unchanged")
        manifest=self.root/"manifest.json"
        self.assertEqual(real_corpus.create_manifest(self.root,manifest),1)
        self.assertEqual(path.read_bytes(),b"unchanged")
        self.assertEqual(json.loads(manifest.read_text())["cases"][0]["path"],str(path))
        with self.assertRaises(FileExistsError): real_corpus.create_manifest(self.root,manifest)

    def test_cli_check_executes_complete_comparison_with_stubbed_readers(self):
        path=self.root/"sample.mdx";path.write_bytes(b"original bytes")
        manifest=self.root/"manifest.json"
        manifest.write_text(json.dumps({"cases":[{"id":"one","path":str(path)}]}))
        out=self.root/"out"
        def scan(cmd,db,engine,kind,log,timeout):
            real_corpus.record(db,engine,"字",b"body")
            db.commit()
            return {"records":1,"attributes":{"Encoding":"UTF-8"}}
        def command(cmd,**kwargs):
            return subprocess.CompletedProcess(cmd,0,json.dumps({"rows":[{"key":"字","text":"body"}]}),"")
        with mock.patch.object(real_corpus.sys,"argv",["real_corpus.py","check","--manifest",str(manifest),"--output",str(out)]), \
             mock.patch.object(real_corpus.importlib.metadata,"version",return_value="1.3.14"), \
             mock.patch.object(real_corpus,"verify_candidate_source"), \
             mock.patch.object(real_corpus,"file_hash",return_value="unchanged"), \
             mock.patch.object(real_corpus,"stream_command",side_effect=scan), \
             mock.patch.object(real_corpus.platform,"platform",return_value="contract-test-platform"), \
             mock.patch.object(real_corpus.subprocess,"run",side_effect=command), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(real_corpus.main(),0)
        report=json.loads((out/"corpus-report.json").read_text())
        self.assertEqual(report["status"],"passed_reader_comparison_only")
        self.assertEqual(report["cases"][0]["lookups"]["字"]["status"],"passed")
        self.assertEqual(path.read_bytes(),b"original bytes")


class ReaderFixtureContract(unittest.TestCase):
    def test_independent_auditor_rejects_bad_checksum_and_wrong_size(self):
        body=b"actual raw bytes\0\xff"
        packed=struct.pack("<I",2)+struct.pack(">I",zlib.adler32(body)&0xffffffff)+zlib.compress(body)
        self.assertEqual(block(packed,len(body)),body)
        with self.assertRaises(AssertionError):block(packed,len(body)+1)
        corrupt=packed[:4]+b"\0\0\0\0"+packed[8:]
        with self.assertRaisesRegex(AssertionError,"ADLER32"):block(corrupt,len(body))

    def test_css_font_inventory_distinguishes_local_and_remote(self):
        css='/* url(ignored.ttf) */ @font-face {src:url(fonts/amiri-regular.ttf)} a{src:url("icon.svg#font")} b{src:url(data:image/png,123)}'
        self.assertEqual(css_urls(css),["fonts/amiri-regular.ttf","icon.svg"])

    def test_fixture_has_real_markers_and_matching_inline_controls(self):
        spec=specification();entries={v["key"]:v["text"] for v in spec["entries"]}
        self.assertEqual(entries["style-marker-red"],"`1`STYLE_ONE_OK")
        self.assertEqual(spec["rendered"]["style-marker-red"],entries["style-inline-red"])
        self.assertEqual(spec["rendered"]["style-marker-blue"],entries["style-inline-blue"])
        self.assertEqual(spec["metadata"]["Compact"],"Yes")
        self.assertEqual(len(spec["metadata"]["StyleSheet"].splitlines()),6)

    def test_crlf_variant_changes_only_header_and_recomputes_checksum(self):
        header='<Dictionary StyleSheet="1\n&lt;b&gt;\n&lt;/b&gt;"/>'.encode("utf-16le")+b"\0\0"
        tail=b"opaque keys and records\0\xff"
        raw=struct.pack(">I",len(header))+header+struct.pack("<I",zlib.adler32(header)&0xffffffff)+tail
        changed=crlf_header(raw)
        length=struct.unpack(">I",changed[:4])[0];payload=changed[4:4+length]
        self.assertIn("1\r\n",payload[:-2].decode("utf-16le"))
        self.assertEqual(changed[8+length:],tail)
        self.assertEqual(struct.unpack("<I",changed[4+length:8+length])[0],zlib.adler32(payload)&0xffffffff)
        with self.assertRaises(AssertionError): crlf_header(changed)


if __name__=="__main__": unittest.main()
