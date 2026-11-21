"""Build and exercise the first reusable core slice; no M1 or native reruns."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib

from patched_interop import ROOT, read_python, require, verify_candidate_source
from v2_audit import audit

SHA16 = "f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_layout():
    """M2 may change application packages, not silently replace dependencies."""
    original = tomllib.loads((ROOT / "experiments/real-rebuild/Cargo.lock").read_text())
    current = tomllib.loads((ROOT / "m2/Cargo.lock").read_text())
    def external(packages):
        return {(p["name"], p["version"]): p for p in packages if not p["name"].startswith("studio-")}
    require(external(original["package"]) == external(current["package"]), "M2 dependency graph differs from pinned engine graph")
    require({p["name"] for p in current["package"] if p["name"].startswith("studio-")} == {"studio-core", "studio-cli"}, "Wrong M2 workspace packages")
    require(sha(ROOT / "baseline/unicode/unicode16-casing.json") == SHA16, "Pinned casing data changed")
    manifest = tomllib.loads((ROOT / "m2/Cargo.toml").read_text())
    require(manifest["patch"]["crates-io"]["mdictlib"]["path"] == "../vendor/mdictlib-0.2.8-studio-sort-v6", "Wrong writer patch")


def fingerprints():
    paths = sorted(p for p in (ROOT / "m2").rglob("*") if p.is_file()
                   and "target" not in p.relative_to(ROOT / "m2").parts
                   and p.suffix in {".rs", ".toml", ".lock"})
    paths.extend([ROOT / "scripts/m2_foundation.py", ROOT / "baseline/unicode/unicode16-casing.json"])
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def compare_rows(expected, actual):
    pairs = [(e["key"], e["text"]) for e in expected]
    require(Counter(pairs) == Counter(actual), "Independent Python read lost or changed a key/body/duplicate")
    for key in {key for key, _ in pairs}:
        require([body for k, body in actual if k == key] == [body for k, body in pairs if k == key], "Duplicate payload order changed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=False, exist_ok=False)
    report = {"status": "m2_foundation_failed", "M1": "complete_unchanged", "M2_complete": False,
              "python": sys.version, "platform": platform.platform(), "steps": [], "checks": [],
              "native_readers": "NOT_REQUESTED", "scope": "first bounded studio-core MDX slice"}
    def run(label, command, parse=False):
        log = out / (label + ".log")
        print(f"Running {label}; log: {log}", flush=True)
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="strict")
        log.write_text(completed.stdout + "\nSTDERR:\n" + completed.stderr, encoding="utf-8")
        report["steps"].append({"name": label, "returncode": completed.returncode, "log": log.name})
        require(completed.returncode == 0, f"{label} failed; return {log.name}")
        return json.loads(completed.stdout) if parse else None
    try:
        check_layout()
        report["source_sha256"] = fingerprints()
        require(importlib.metadata.version("mdict-utils") == "1.3.14", "Use existing .venv with mdict-utils==1.3.14")
        verify_candidate_source(ROOT / "vendor/mdictlib-0.2.8-studio-sort-v6", 6)
        cargo = shutil.which("cargo")
        require(cargo is not None, "Cargo unavailable; run on the Rust-enabled Mac")
        command = [cargo, "run", "--locked", "--manifest-path", "m2/Cargo.toml", "-p", "studio-cli", "--"]
        run("core-tests", [cargo, "test", "--locked", "--manifest-path", "m2/Cargo.toml", "--workspace"])
        smoke = run("core-smoke", command + ["smoke", str(out / "smoke")], parse=True)
        require(smoke["status"] == "core_foundation_smoke_passed" and len(smoke["cases"]) == 2, "Incomplete core smoke")
        (out / "core-smoke.json").write_text(json.dumps(smoke, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for case in smoke["cases"]:
            path = Path(case["file"])
            require(path.parent == out / "smoke", "Unexpected smoke output path")
            before = sha(path)
            compare_rows(case["expected_entries"], read_python(path, "mdx"))
            wire = audit(path)
            require(wire["status"] == "structural_audit_passed", "Independent v2 audit failed")
            for query, count in [("ΟΣ", 2), ("Ος", 3), ("duplicate", 8), ("a꟏Σ", 0)]:
                value = run(f"reopen-{case['encoding']}-{len(report['steps'])}", command + ["lookup", str(path), query], parse=True)
                require(len(value["rows"]) == count, f"Separate-process lookup count differs: {query}")
                if query == "duplicate":
                    require([r["text"] for r in value["rows"]] == [f"DUP_{i:02d}" for i in range(1, 9)], "Duplicate order differs after process reopen")
            require(sha(path) == before, "Output changed during read checks")
            report["checks"].append({"encoding": case["encoding"], "records": len(case["expected_entries"]),
                "sha256": before, "independent_python_exact_rows": "passed", "wire_audit": "passed",
                "separate_process_reopen": "passed"})
        require(fingerprints() == report["source_sha256"], "Source or lock changed during run")
        report["status"] = "m2_foundation_passed_remaining_M2_work_pending"
    except (Exception, KeyboardInterrupt) as error:
        report["error"] = f"{type(error).__name__}: {error}"
    destination = out / "m2-foundation-report.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {destination}", flush=True)
    return 0 if report["status"] == "m2_foundation_passed_remaining_M2_work_pending" else 1


if __name__ == "__main__":
    raise SystemExit(main())
