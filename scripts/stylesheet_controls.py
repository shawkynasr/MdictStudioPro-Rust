"""Qualify stylesheet-only MDX controls offline, without MDD or reader launches."""
import argparse
import csv
import hashlib
import html
import importlib.metadata
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import zipfile
import zlib
from patched_interop import ROOT, require, compare, read_python, inspect_header, verify_candidate_source, hash_file
from minimal_reader_controls import expected_lookup
from check_native_wire import wire_contract
from v2_audit import audit

OFFICIAL_SHA256 = '4fe44ade9214315f5f75c6b38d136411c57bbec5cb8f03003cea30813535de7d'


def official_reference_stylesheet():
    """Read the exact user-built, native-tested synthetic reference, not an oracle we generated."""
    archive = ROOT/'docs/evidence/official-stylesheet-reference/official-stylesheet.zip'
    with zipfile.ZipFile(archive) as source:
        entry = source.getinfo('official-stylesheet.mdx')
        require(entry.file_size == 1446, 'Reference fixture size changed')
        data = source.read(entry)
    require(hashlib.sha256(data).hexdigest() == OFFICIAL_SHA256, 'Official fixture identity changed')
    size = struct.unpack('>I', data[:4])[0]
    require(2 <= size <= len(data)-8, 'Invalid reference header size')
    raw = data[4:4+size]
    require(zlib.adler32(raw) & 0xffffffff == struct.unpack('<I', data[4+size:8+size])[0], 'Reference header checksum differs')
    values = re.findall(r'StyleSheet="([^"]*)"', raw.decode('utf-16le'), re.S)
    require(len(values) == 1, 'Ambiguous reference stylesheet')
    return html.unescape(values[0])

def specification():
    red = '<span style="color:#9b1c31;font-weight:700;border:2px solid #9b1c31;">'
    blue = '<span style="color:#1d4ed8;text-decoration:underline;">'
    stylesheet = f"1\n{red}\n</span>\n2\n{blue}\n</span>"
    rows = [("inline-red", red + "STYLE_ONE_OK</span>"), ("marker-red", "`1`STYLE_ONE_OK"),
            ("inline-blue", blue + "STYLE_TWO_OK</span>"), ("marker-blue", "`2`STYLE_TWO_OK"),
            ("plain", "PLAIN_CONTROL_OK")]
    return {"profile": "HeaderLiteralC", "cases": [{"name": "04-stylesheet", "stylesheet": stylesheet,
        "entries": [{"key": k, "text": v} for k, v in rows],
        "queries": [k for k, _ in rows] + ["missing"]}],
        "rendered": {"marker-red": red + "STYLE_ONE_OK</span>", "marker-blue": blue + "STYLE_TWO_OK</span>"}}


def raw_stylesheet(path):
    with path.open("rb") as stream:
        prefix = stream.read(4)
        require(len(prefix) == 4, "Missing header length")
        size = struct.unpack(">I", prefix)[0]
        require(2 <= size <= 1024*1024, "Invalid diagnostic header length")
        payload = stream.read(size)
        require(len(payload) == size, "Truncated diagnostic header")
    values = re.findall(r'StyleSheet="([^"]*)"', payload.decode("utf-16le"), re.S)
    require(len(values) == 1, "Missing or duplicate stylesheet attribute")
    return html.unescape(values[0])


def validate_case(spec, result, python_rows, styled_rows, attributes, stylesheet, expected_wire_style=None):
    case = spec["cases"][0]
    require(attributes.get("KeyCaseSensitive") == "No" and attributes.get("StripKey") == "No", "Wrong sort policy")
    require(attributes.get("Compact") == "Yes", "Stylesheet control must declare Compact=Yes")
    expected_style = case["stylesheet"] if expected_wire_style is None else expected_wire_style
    require(stylesheet == expected_style, "Raw stylesheet differs from selected wire contract")
    expected = sorted(case["entries"], key=lambda e: e["key"].lower())
    expected_rows = [(e["key"], e["text"]) for e in expected]
    compare(expected_rows, [(e["key"], e["text"]) for e in result["rows"]], order=True)
    compare(expected_rows, python_rows, order=True)
    require(result["key_blocks"] > 1, "Expected multiple key blocks")
    require([q["query"] for q in result["lookups"]] == case["queries"], "Lookup inventory differs")
    for lookup in result["lookups"]:
        require(lookup["rows"] == expected_lookup(expected, lookup["query"]), f"Lookup differs: {lookup['query']}")
    rendered = [(k, spec["rendered"].get(k, v)) for k, v in expected_rows]
    compare(rendered, styled_rows, order=True)
    return {"status": "passed", "records": len(expected), "lookups": len(case["queries"]),
            "key_blocks": result["key_blocks"], "raw_stylesheet_preserved": stylesheet == case["stylesheet"],
            "raw_stylesheet_matches_selected_contract": True,
            "python_marker_expansion_matches_inline_controls": True,
            "standard_XML_stylesheet_matches_raw": attributes.get("StyleSheet") == stylesheet,
            "XML_contract": "Literal attribute newlines are normalized by standard XML; native behavior remains to be tested"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--wire-candidate", action="store_true", help="Use isolated reference-matching stylesheet serialization; preserve all definition text")
    args = parser.parse_args(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {"status": "blocked", "writer_revision": 5, "profile": "HeaderLiteralC",
              "fixture_wrapper_revision": 6 if args.wire_candidate else 5,
              "native_readers": "NOT_RUN_DO_NOT_IMPORT", "steps": [], "checks": {},
              "not_proven": ["native_stylesheet_rendering", "generic_XML_stylesheet_contract",
                             "MDD_resource_rendering", "production_writer_qualification"]}
    def run(name, command):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", timeout=1800)
        (out / f"{name}.log").write_text(result.stdout + "\nSTDERR:\n" + result.stderr, encoding="utf-8")
        report["steps"].append({"name": name, "returncode": result.returncode, "log": f"{name}.log"})
        require(result.returncode == 0, f"{name} failed; see {name}.log")
        return result.stdout
    try:
        require(importlib.metadata.version("mdict-utils") == "1.3.14", "Expected mdict-utils 1.3.14")
        run("prepare", [sys.executable, ROOT / "scripts/prepare_sort_experiment.py", "--revision", "5", "--reuse"])
        vendor = ROOT / "vendor/mdictlib-0.2.8-studio-sort-v5"
        verify_candidate_source(vendor, 5)
        report["source_sha256"] = {str(p.relative_to(ROOT)): hash_file(p) for p in
            [vendor / "src/write/mod.rs", vendor / "src/write/studio_legacy_sort.rs",
             ROOT / "experiments/native-controls/src/main.rs", Path(__file__).resolve(),
             ROOT / "experiments/native-controls/Cargo.lock"]}
        spec = specification(); expected_wire_style = None
        if args.wire_candidate:
            spec['cases'][0]['name'] = '05-stylesheet-wire'
            expected_wire_style = official_reference_stylesheet()
            require(expected_wire_style == spec['cases'][0]['stylesheet'] + '\n', 'Official stylesheet differs beyond the selected final LF')
            report['official_reference_sha256'] = OFFICIAL_SHA256
            report['candidate_scope'] = 'Rust fixture writer serializes stylesheet as LF plus final LF; all five definition strings unchanged from failed control; engine remains v5'
            run('rust-wrapper-tests', ['cargo', 'test', '--locked', '--manifest-path', 'experiments/native-controls/Cargo.toml'])
        spec_path = out / "stylesheet-spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        built = json.loads(run("stylesheet-build", ["cargo", "run", "--locked", "--manifest-path",
            "experiments/native-controls/Cargo.toml", "--", spec_path, out / "dictionaries"]))
        (out / "rust-observations.json").write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        base_name = spec['cases'][0]['name']
        names = {f"{base_name}-utf8.mdx", f"{base_name}-utf16.mdx"}
        require(built["profile"] == "HeaderLiteralC" and len(built["cases"]) == 2 and
                {c["file"] for c in built["cases"]} == names, "Wrong stylesheet output inventory")
        require({p.name for p in (out / "dictionaries").iterdir()} == names, "Unexpected companion files")
        from mdict_utils.base.readmdict import MDX
        for case in built["cases"]:
            path = out / "dictionaries" / case["file"]
            observation = audit(path); wire = wire_contract(path, observation)
            require(wire["status"] == "passed", "Wire check failed")
            require(observation["records"] == 5 and observation["style_markers"] == 2 and
                    observation["redirect_records"] == 0 and not observation["local_asset_references"],
                    "Stylesheet control has unexpected records, markers or assets")
            styled = [(k.decode("utf-8"), v.decode("utf-8")) for k, v in MDX(str(path), substyle=True).items()]
            check = validate_case(spec, case, read_python(path, "mdx"), styled,
                                  inspect_header(path)["attributes"], raw_stylesheet(path), expected_wire_style)
            if args.wire_candidate:
                check['stylesheet_matches_native_tested_official_reference'] = True
                check['definition_text_matches_original_failed_control'] = True
            report["checks"][path.name] = {**check, "wire": wire, "structural_audit": observation}
        with (out / "reader-results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["reader", "version", "fixture", "sha256", "key", "expected", "result", "notes"])
            writer.writeheader()
            tests = {"inline-red": "Dark red bold STYLE_ONE_OK with red border", "marker-red": "Same appearance as inline-red; no literal `1`",
                     "inline-blue": "Blue underlined STYLE_TWO_OK", "marker-blue": "Same appearance as inline-blue; no literal `2`",
                     "plain": "PLAIN_CONTROL_OK without inherited marker formatting", "missing": "No exact entry"}
            for name in sorted(names):
                for reader in ["MDict", "GoldenDict"]:
                    for key, expected in tests.items():
                        writer.writerow({"reader": reader, "fixture": name, "sha256": report["checks"][name]["wire"]["sha256"],
                                         "key": key, "expected": expected, "result": "NOT_RUN"})
        report["status"] = "offline_stylesheet_controls_passed_native_untested"
        if args.wire_candidate:
            report['native_readers'] = 'NOT_RUN_READY_FOR_STAGED_MANUAL_TEST'
    except Exception as error:
        report["error"] = str(error)
    finally:
        (out / "stylesheet-controls-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{report['status']}: {out / 'stylesheet-controls-report.json'}")
    return 0 if report["status"] == "offline_stylesheet_controls_passed_native_untested" else 1


if __name__ == "__main__": raise SystemExit(main())
