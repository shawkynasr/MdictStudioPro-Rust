"""Final regression runner; never auto-selects a production engine."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    evidence = ROOT / "docs/evidence/integrated-casing-user-run/integrated-casing-report.json"
    qualified = json.loads(evidence.read_text(encoding="utf-8"))
    for name, expected in qualified["source_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"Current integration source differs from qualified run: {name}")
    return qualified["source_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    # Deliberate no-replace behavior: never merge logs from separate runs.
    out.mkdir(parents=False, exist_ok=False)
    report = {"status": "regression_failed", "M1_complete": False,
              "engine_selected": False, "python": sys.version,
              "platform": platform.platform(), "steps": [],
              "native_tests_repeated": False, "corpus_or_casing_regenerated": False,
              "scope_document": "docs/M1-CLOSEOUT.md"}
    report_path = out / "m1-closeout-report.json"
    try:
        report["qualified_source_sha256"] = source_identity()
        report["lock_sha256"] = {name: sha(ROOT / name) for name in (
            "Cargo.lock", "experiments/legacy-sort/Cargo.lock",
            "experiments/real-rebuild/Cargo.lock")}
        cargo = shutil.which("cargo")
        if not cargo:
            raise RuntimeError("cargo is unavailable; run this final gate on the Rust-enabled Mac")
        for revision in (2, 6):
            if not (ROOT / f"vendor/mdictlib-0.2.8-studio-sort-v{revision}").is_dir():
                raise RuntimeError(f"Missing existing v{revision} vendor tree; retain vendor when updating")
        commands = [
            ("evidence", [sys.executable, "scripts/validate_evidence.py"]),
            ("vendor-v2", [sys.executable, "scripts/prepare_sort_experiment.py", "--revision", "2", "--reuse"]),
            ("vendor-v6", [sys.executable, "scripts/prepare_sort_experiment.py", "--revision", "6", "--reuse"]),
            ("baseline", [sys.executable, "-m", "unittest", "discover", "-s", "baseline", "-v"]),
            ("python-contracts", [sys.executable, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py", "-v"]),
            ("rust-root", [cargo, "test", "--locked", "--workspace"]),
            ("rust-legacy-sort", [cargo, "test", "--locked", "--manifest-path", "experiments/legacy-sort/Cargo.toml"]),
            ("rust-adapter", [cargo, "test", "--locked", "--manifest-path", "experiments/real-rebuild/Cargo.toml"]),
        ]
        for label, command in commands:
            log = out / f"{label}.log"
            step = {"name": label, "command": command, "log": log.name, "status": "running"}
            report["steps"].append(step)
            print(f"Running {label}; log: {log}", flush=True)
            with log.open("w", encoding="utf-8") as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            step.update(status="passed" if result.returncode == 0 else "failed", returncode=result.returncode)
            if result.returncode:
                raise RuntimeError(f"{label} failed; return {log.name} with the report")
        # Locked builds must not leave silently updated lockfiles.
        for name, expected in report["lock_sha256"].items():
            if sha(ROOT / name) != expected:
                raise ValueError(f"Lock changed during regression: {name}")
        source_identity()
        report["status"] = "regression_passed_engine_decision_pending"
    except (Exception, KeyboardInterrupt) as error:
        report["error"] = f"{type(error).__name__}: {error}"
        for step in report["steps"]:
            if step["status"] == "running":
                step["status"] = "interrupted_or_error"
    finally:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {report_path}", flush=True)
    return 0 if report["status"] == "regression_passed_engine_decision_pending" else 1


if __name__ == "__main__":
    raise SystemExit(main())
