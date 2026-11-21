"""Observe dictionary storage codecs and metadata without changing either reader.

Requires mdict-utils==1.3.14, Cargo, and the selected prepared vendor tree.
Individual failures are retained; independent checks continue. New outputs only.
"""
import argparse
import contextlib
import importlib.metadata
import io
import json
import locale
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback

from patched_interop import ROOT, compare, decode, hash_file, inspect_header, custom_writer_class, read_python, require, experiment_command, verify_candidate_source


class UnsupportedLegacyEncoding(Exception):
    """The original writer explicitly rejected this codec, not a Rust failure."""


def observe(checks, name, action, dependencies=()):
    blocked = [key for key in dependencies if checks.get(key, {}).get("status") != "passed"]
    if blocked:
        checks[name] = {"status": "blocked", "dependencies": blocked}
        return
    try:
        checks[name] = {"status": "passed", "detail": action()}
    except UnsupportedLegacyEncoding as error:
        checks[name] = {"status": "unsupported", "error": str(error)}
    except Exception as error:
        checks[name] = {"status": "failed", "error": str(error), "traceback": traceback.format_exc()}


def legacy_writer_encoding(case):
    # The writer API accepts utf16; Python's byte codec utf-16le is separate.
    return "utf16" if case["id"] == "utf16le" else case["python"]


def compare_metadata(expected, actual):
    mismatches = {key: {"expected": value, "actual": actual.get(key)}
                  for key, value in expected.items() if actual.get(key) != value}
    require(not mismatches, "Metadata differs: " + json.dumps(mismatches, ensure_ascii=False))
    return {"attributes": {key: actual[key] for key in expected}}


def fixture_rows(case):
    return [(entry["key"], entry["text"]) for entry in case["entries"]]


def source_records(case, directory):
    """Raw binary bodies with an explicit encoded NUL, avoiding TXT policy.

    The original writer consumes path/size/pos records and expects that final
    terminator within size. No newline, BOM, or lossy codec replacement is added.
    """
    directory.mkdir()
    data = []
    encoding = case["python"]
    for index, (key, body) in enumerate(fixture_rows(case)):
        key.encode(encoding, errors="strict")
        payload = body.encode(encoding, errors="strict") + "\0".encode(encoding)
        path = directory / f"{index}.record"
        path.write_bytes(payload)
        data.append({"key": key, "path": str(path), "pos": 0, "size": len(payload)})
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--writer-revision", type=int, choices=[2, 3, 4], default=2)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    log = out / "metadata-codecs.log"
    log.touch()
    report = {"status": "running", "suite": "metadata-storage-codecs-v1", "harness_revision": 3, "writer_patch_revision": args.writer_revision,
              "environment": {"python": sys.version, "os": platform.system(), "release": platform.release(), "machine": platform.machine()},
              "checks": {}, "not_proven": ["native_readers", "all_codepoint_mapping_equivalence", "source_file_decoding", "large_files", "non_C_locale", "stylesheet_rendering"]}

    def run(*cmd):
        completed = subprocess.run(list(map(str, cmd)), cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="strict")
        with log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(list(map(str, cmd))) + "\n" + completed.stdout + "\nSTDERR:\n" + completed.stderr + "\n")
        require(completed.returncode == 0, f"Command exited {completed.returncode}; see {log.name}")
        return completed.stdout

    def rust(*command_args):
        return json.loads(run(*experiment_command(args.writer_revision, *command_args)))

    def step(name, action, dependencies=()):
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                observe(report["checks"], name, action, dependencies)
        finally:
            with log.open("a", encoding="utf-8") as stream:
                stream.write(f"CHECK {name}\n" + captured.getvalue() + "\n")

    def python_records(path, kind, expected):
        compare(expected, read_python(path, kind))
        return {"records": len(expected), "comparison": "exact_multiset"}

    def xml_metadata(path, expected):
        header = inspect_header(path)
        return {**compare_metadata(expected, header["attributes"]), "header": header}

    def python_metadata(path, kind, expected):
        from mdict_utils.base.readmdict import MDX, MDD
        reader = (MDX if kind == "mdx" else MDD)(str(path))
        attrs = {decode(key): decode(value) for key, value in reader.header.items()}
        return compare_metadata(expected, attrs)

    try:
        version = importlib.metadata.version("mdict-utils")
        require(version == "1.3.14", f"Expected mdict-utils==1.3.14, found {version}")
        require(shutil.which("cargo") is not None, "Cargo unavailable")
        vendor = ROOT / f"vendor/mdictlib-0.2.8-studio-sort-v{args.writer_revision}"
        require(vendor.is_dir(), f"First run python3 scripts/prepare_sort_experiment.py --revision {args.writer_revision}")
        verify_candidate_source(vendor, args.writer_revision)
        locale.setlocale(locale.LC_COLLATE, "C")
        report["environment"].update({"mdict-utils": version, "rustc": run("rustc", "--version").strip(), "cargo": run("cargo", "--version").strip(), "collation": "C"})
        files = [ROOT / "baseline/codec-cases.json", ROOT / "Cargo.lock", ROOT / "experiments/legacy-sort/Cargo.lock",
                 ROOT / "baseline/legacy/MdictStudio.py", ROOT / "scripts/patched_interop.py",
                 ROOT / "experiments/legacy-sort/src/main.rs", ROOT / "experiments/legacy-sort/src/lib.rs",
                 ROOT / "experiments/legacy-sort/src/codec.rs", ROOT / "scripts/metadata_codecs.py",
                 vendor / "src/write/mod.rs", vendor / "src/write/studio_legacy_sort.rs"]
        report["source_sha256"] = {str(path.relative_to(ROOT)): hash_file(path) for path in files}
        fixture = json.loads((ROOT / "baseline/codec-cases.json").read_text(encoding="utf-8"))
        forward = out / "rust"
        rust_report = rust("codec", forward)
        require(rust_report.get("suite") == report["suite"], "Unexpected Rust report")
        require(rust_report.get("writer_patch_revision") == args.writer_revision, "Cargo built the wrong writer candidate")
        report["rust_report"] = "rust/rust-codec-report.json"
        for name, result in rust_report["checks"].items():
            report["checks"]["rust-" + name] = result

        writer = custom_writer_class()
        for case in fixture["encodings"]:
            expected = fixture_rows(case)
            for style in ["mdict-utils", "mdxbuilder"]:
                label = f"{case['id']}-{style}"
                path = forward / f"{label}.mdx"
                step(f"forward-{label}-records", lambda p=path, e=expected: python_records(p, "mdx", e))
                step(f"forward-{label}-xml", lambda p=path: xml_metadata(p, fixture["metadata"]))
                step(f"forward-{label}-python-metadata", lambda p=path: python_metadata(p, "mdx", fixture["metadata"]))
                output = out / f"python-{label}.mdx"

                def write_reverse(case=case, style=style, label=label, output=output):
                    data = source_records(case, out / f"source-{label}")
                    from mdict_utils.base.writemdict import ParameterError
                    try:
                        engine = writer(data, title=fixture["metadata"]["Title"], description=fixture["metadata"]["Description"],
                                        encoding=legacy_writer_encoding(case), is_mdd=False, sort_style=style, key_size=40, record_size=48)
                    except ParameterError as error:
                        if case["id"] == "gb18030" and str(error) == "Unknown encoding":
                            raise UnsupportedLegacyEncoding("mdict-utils 1.3.14 writer rejects GB18030; reverse interoperability is unproven") from error
                        raise
                    with output.open("wb") as stream:
                        engine.write(stream)
                    return {"sha256": hash_file(output), "source_policy": "exact binary body plus encoded NUL; no TXT conversion"}

                step(f"reverse-{label}-write", write_reverse)

                def reverse_records(p=output, e=expected):
                    value = rust("inspect-json", p)
                    compare(e, [(entry["key"], entry["text"]) for entry in value["entries"]])
                    return {"records": len(e), "comparison": "exact_multiset"}

                dependencies = (f"reverse-{label}-write",)
                step(f"reverse-{label}-rust-records", reverse_records, dependencies)
                step(f"reverse-{label}-python-records", lambda p=output, e=expected: python_records(p, "mdx", e), dependencies)
                reverse_meta = {key: fixture["metadata"][key] for key in ["Title", "Description"]}
                step(f"reverse-{label}-rust-metadata", lambda p=output, e=reverse_meta: compare_metadata(e, rust("inspect-json", p)["attributes"]), dependencies)
                step(f"reverse-{label}-xml", lambda p=output, e=reverse_meta: xml_metadata(p, e), dependencies)

        resources = [(item["key"], bytes(item["bytes"])) for item in fixture["resources"]]
        path = forward / "unicode-resources.mdd"
        step("mdd-python-records", lambda: python_records(path, "mdd", resources))
        step("mdd-xml-metadata", lambda: xml_metadata(path, fixture["mdd_metadata"]))
        step("mdd-python-metadata", lambda: python_metadata(path, "mdd", fixture["mdd_metadata"]))
        report["status"] = "passed" if report["checks"] and all(v["status"] == "passed" for v in report["checks"].values()) else "failed"
    except Exception as error:
        report.update(status="blocked", setup_error=str(error), setup_traceback=traceback.format_exc())
    finally:
        report["artifact_sha256"] = {str(path.relative_to(out)): hash_file(path) for path in out.rglob("*") if path.suffix in {".mdx", ".mdd"}}
        report["counts"] = {status: sum(v["status"] == status for v in report["checks"].values()) for status in ["passed", "failed", "unsupported", "blocked"]}
        path = out / "metadata-codec-report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{report['status']}: {path}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
