"""Tests for exact fixture expectations, independent of Rust/package availability."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import subprocess
import contextlib
import io
import xml.etree.ElementTree as ET
import metadata_codecs

from metadata_codecs import ROOT, compare_metadata, fixture_rows, source_records, observe, UnsupportedLegacyEncoding, legacy_writer_encoding


class MetadataCodecContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "baseline/codec-cases.json").read_text(encoding="utf-8"))

    def test_positive_samples_representable_without_replacement(self):
        self.assertEqual(len(self.fixture["encodings"]), 5)
        for case in self.fixture["encodings"]:
            for key, body in fixture_rows(case):
                for value in [key, body]:
                    self.assertEqual(value.encode(case["python"], "strict").decode(case["python"], "strict"), value)
            self.assertEqual(sum(key == "字" for key, _ in fixture_rows(case)), 2)

    def test_negative_legacy_samples_cannot_encode(self):
        codecs = {case["rust"]: case["python"] for case in self.fixture["encodings"]}
        for case in self.fixture["negative_entries"]:
            if "unencodable" in case["id"]:
                with self.assertRaises(UnicodeEncodeError):
                    (case["key"] + case["text"]).encode(codecs[case["encoding"]], "strict")

    def test_raw_sources_preserve_bytes_and_two_byte_terminators(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case in self.fixture["encodings"]:
                data = source_records(case, Path(tmp) / case["id"])
                for record, (_, body) in zip(data, fixture_rows(case)):
                    payload = Path(record["path"]).read_bytes()
                    self.assertEqual(payload, (body + "\0").encode(case["python"]))
                    self.assertEqual(record["size"], len(payload))
                    self.assertEqual(record["pos"], 0)

    def test_metadata_comparison_catches_newline_normalization(self):
        expected = self.fixture["metadata"]
        compare_metadata(expected, dict(expected))
        normalized = {**expected, "StyleSheet": expected["StyleSheet"].replace("\n", " ")}
        with self.assertRaises(AssertionError):
            compare_metadata(expected, normalized)
        with self.assertRaises(AssertionError):
            compare_metadata(expected, {"Title": expected["Title"]})

    def test_xml_literal_newline_and_reference_have_different_contracts(self):
        self.assertEqual(ET.fromstring('<D StyleSheet="1\n2"/>').attrib["StyleSheet"], "1 2")
        self.assertEqual(ET.fromstring('<D StyleSheet="1&#10;2"/>').attrib["StyleSheet"], "1\n2")

    def test_failed_writer_blocks_reads_without_attempting_them(self):
        checks = {}
        def fail():
            raise ValueError("Writer failed")
        observe(checks, "write", fail)
        observe(checks, "read", lambda: self.fail("A missing output must not be read"), ("write",))
        self.assertEqual(checks["write"]["status"], "failed")
        self.assertEqual(checks["read"], {"status": "blocked", "dependencies": ["write"]})

    def test_unsupported_writer_is_distinct_from_failed_reader(self):
        checks = {}
        def unsupported():
            raise UnsupportedLegacyEncoding("GB18030")
        observe(checks, "write", unsupported)
        observe(checks, "read", lambda: self.fail("Unsupported producer cannot produce a read verdict"), ("write",))
        self.assertEqual(checks["write"]["status"], "unsupported")
        self.assertEqual(checks["read"]["status"], "blocked")
        observe(checks, "independent-read", lambda: 4)
        self.assertEqual(checks["independent-read"], {"status": "passed", "detail": 4})

    def test_utf16_writer_parameter_does_not_change_raw_byte_codec(self):
        case = next(c for c in self.fixture["encodings"] if c["id"] == "utf16le")
        self.assertEqual(legacy_writer_encoding(case), "utf16")
        self.assertEqual(case["python"], "utf-16le")
        self.assertEqual("字".encode(case["python"]), b"\x57\x5b")

    def test_cli_dispatches_selected_candidate_to_cargo(self):
        # Exercise main(), including argument parsing and the nested Rust call.
        # External dependencies are stubbed; this is not engine qualification.
        for revision in [2, 3, 4]:
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as tmp:
                # The CLI resolves output paths; macOS temp roots may use a
                # /var alias for /private/var. Compare canonical paths.
                root = Path(tmp).resolve()
                out = root / "result"
                (root / f"vendor/mdictlib-0.2.8-studio-sort-v{revision}").mkdir(parents=True)
                (root / "baseline").mkdir()
                (root / "baseline/codec-cases.json").write_text(json.dumps({"encodings": [], "resources": [], "mdd_metadata": {}}))
                rust_report = {"suite": "metadata-storage-codecs-v1", "writer_patch_revision": revision,
                               "checks": {"dispatch-probe": {"status": "passed"}}}
                commands = []
                def fake_run(cmd, **kwargs):
                    commands.append(cmd)
                    stdout = json.dumps(rust_report) if "run" in cmd else "test-version"
                    return subprocess.CompletedProcess(cmd, 0, stdout, "")
                with mock.patch.object(metadata_codecs, "ROOT", root), \
                     mock.patch.object(metadata_codecs.sys, "argv", ["metadata_codecs.py", "--writer-revision", str(revision), "--output", str(out)]), \
                     mock.patch.object(metadata_codecs.importlib.metadata, "version", return_value="1.3.14"), \
                     mock.patch.object(metadata_codecs.shutil, "which", return_value="cargo"), \
                     mock.patch.object(metadata_codecs, "verify_candidate_source"), \
                     mock.patch.object(metadata_codecs, "hash_file", return_value="test-fingerprint"), \
                     mock.patch.object(metadata_codecs, "custom_writer_class", return_value=object), \
                     mock.patch.object(metadata_codecs, "read_python", return_value=[]), \
                     mock.patch.object(metadata_codecs, "inspect_header", return_value={"attributes": {}}), \
                     mock.patch.object(metadata_codecs.subprocess, "run", side_effect=fake_run), \
                     contextlib.redirect_stdout(io.StringIO()):
                    status = metadata_codecs.main()
                report = json.loads((out / "metadata-codec-report.json").read_text())
                self.assertNotIn("setup_error", report)
                self.assertEqual(report["checks"]["rust-dispatch-probe"]["status"], "passed")
                cargo_calls = [cmd for cmd in commands if "run" in cmd]
                self.assertEqual(len(cargo_calls), 1)
                self.assertIn(f"studio-sort-v{revision}", cargo_calls[0][2])
                self.assertEqual(cargo_calls[0][-2:], ["codec", str(out / "rust")])
                # No package import was simulated for Python MDD metadata.
                # Its outcome is independent of proving Cargo was reached.
                self.assertIn(status, [0, 1])


if __name__ == "__main__":
    unittest.main()
