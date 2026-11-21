"""Build and qualify isolated v5 lookup controls offline. Never launch readers."""
import argparse
import csv
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from patched_interop import (ROOT, require, compare, read_python, inspect_header,
                             verify_candidate_source, hash_file, experiment_command)
from check_native_wire import wire_contract
from v2_audit import audit


def specification():
    cases = []
    groups = [
        ("01-plain", [("alpha", "ALPHA_OK"), ("beta", "BETA_OK"),
                      ("delta", "DELTA_OK"), ("gamma", "GAMMA_OK"),
                      ("omega", "OMEGA_OK"), ("zeta", "ZETA_OK")]),
        ("02-punctuation", [("a-b", "DASH_OK"), ("ab", "PLAIN_OK"),
                            ("a b", "SPACE_OK"), ("a.b", "DOT_OK"),
                            ("a!b", "EXCLAMATION_OK"), ("Apple", "TITLE_CASE_OK"),
                            ("apple", "LOWER_CASE_OK"), ("APPLE", "UPPER_CASE_OK"),
                            ("duplicate", "DUPLICATE_ONE"), ("duplicate", "DUPLICATE_TWO"),
                            ("zebra", "LAST_KEY_OK")]),
        ("03-multilingual", [("alpha", "LATIN_OK"), ("字", "中文显示正常：字"),
                             ("和", "中文显示正常：和"), ("مرحبا", "أهلاً بالعالم"),
                             ("سلام", "السلام عليكم"), ("Äpfel", "UMLAUT_TITLE_OK"),
                             ("äpfel", "UMLAUT_LOWER_OK"), ("𠀀", "CJK_SUPPLEMENTARY_OK")]),
    ]
    for name, rows in groups:
        queries = list(dict.fromkeys(k for k, _ in rows)) + ["missing"]
        if name == "02-punctuation": queries += ["aPpLe", "a?b"]
        cases.append({"name": name, "entries": [{"key": k, "text": v} for k, v in rows],
                      "queries": queries})
    return {"profile": "HeaderLiteralC", "cases": cases}


def expected_lookup(entries, query):
    exact = [e for e in entries if e["key"] == query]
    return exact or [e for e in entries if e["key"].lower() == query.lower()]


def validate_case(spec, result, python_rows, attributes):
    require(attributes.get("KeyCaseSensitive") == "No" and attributes.get("StripKey") == "No",
            "Control header does not declare the tested literal, lowercase policy")
    require(attributes.get("StyleSheet") == "", "Minimal control contains an embedded stylesheet")
    expected = sorted(spec["entries"], key=lambda e: e["key"].lower())
    compare([(e["key"], e["text"]) for e in expected],
            [(e["key"], e["text"]) for e in result["rows"]], order=True)
    compare([(e["key"], e["text"]) for e in expected], python_rows, order=True)
    require(result["key_blocks"] > 1, "Control did not cross key block boundaries")
    require([q["query"] for q in result["lookups"]] == spec["queries"], "Missing or repeated query")
    for lookup in result["lookups"]:
        require(lookup["rows"] == expected_lookup(expected, lookup["query"]),
                f"Lookup differs for {lookup['query']!r}")
    return {"status": "passed", "records": len(expected), "lookups": len(spec["queries"]),
            "key_blocks": result["key_blocks"], "physical_order": [e["key"] for e in expected]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {"status": "blocked", "writer_revision": 5, "profile": "HeaderLiteralC",
              "native_readers": "NOT_RUN_DO_NOT_IMPORT", "steps": [], "checks": {},
              "not_proven": ["native_crash_fixed", "native_lookup_compatibility",
                             "legacy_profiles_native_compatibility", "stylesheet_rendering",
                             "MDD_resource_rendering", "all_Unicode_case_equivalence"]}
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
        # Existing tests still exercise both original legacy profiles and reader semantics.
        run("legacy-regression", experiment_command(5)[:3] + ["test", "--locked", "--manifest-path", "experiments/legacy-sort/Cargo.toml"])
        spec = specification()
        spec_path = out / "control-spec.json"
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        built = json.loads(run("controls-build", ["cargo", "run", "--locked", "--manifest-path",
            "experiments/native-controls/Cargo.toml", "--", spec_path, out / "dictionaries"]))
        (out / "rust-observations.json").write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        require(built["profile"] == "HeaderLiteralC" and len(built["cases"]) == 6, "Incomplete controls")
        expected_files = {f"{s['name']}-{encoding}.mdx": s for s in spec["cases"] for encoding in ["utf8", "utf16"]}
        require({c["file"] for c in built["cases"]} == set(expected_files), "Wrong or duplicate control files")
        require({p.name for p in (out / "dictionaries").iterdir()} == set(expected_files), "Unexpected control outputs")
        for case in built["cases"]:
            name = case["file"]; path = out / "dictionaries" / name
            observation = audit(path)
            wire = wire_contract(path, observation)
            require(wire["status"] == "passed", f"Wire check failed: {name}")
            check = validate_case(expected_files[name], case, read_python(path, "mdx"),
                                  inspect_header(path)["attributes"])
            require(observation["records"] == check["records"], "Independent record count differs")
            report["checks"][name] = {**check, "wire": wire, "structural_audit": observation}
        with (out / "reader-results.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["reader", "version", "fixture", "sha256", "query", "expected_texts", "result", "notes"])
            writer.writeheader()
            for case in built["cases"]:
                for reader in ["MDict", "GoldenDict"]:
                    for lookup in case["lookups"]:
                        writer.writerow({"reader": reader, "fixture": case["file"],
                            "sha256": report["checks"][case["file"]]["wire"]["sha256"],
                            "query": lookup["query"], "expected_texts": json.dumps([e["text"] for e in lookup["rows"]], ensure_ascii=False),
                            "result": "NOT_RUN"})
        report["status"] = "offline_controls_passed_native_untested"
    except Exception as error:
        report["error"] = str(error)
    finally:
        (out / "minimal-controls-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{report['status']}: {out / 'minimal-controls-report.json'}")
    return 0 if report["status"] == "offline_controls_passed_native_untested" else 1


if __name__ == "__main__": raise SystemExit(main())
