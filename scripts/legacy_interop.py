"""Historical upstream-only check. Active gate: scripts/patched_interop.py.

Upstream's missing header terminator is a known compatibility failure. This
script is retained as a negative comparison, not the active patched gate.
Requires Cargo and mdict-utils==1.3.14.

Each CLI engine runs in its own process. No GUI import or global stdout changes.
Successful checks complement, not replace, external reader validation.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True, capture_output=True, text=True).stdout


def records(path):
    # Only for generated fixtures, whose body lines never equal the delimiter.
    lines = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").splitlines()
    entries, block = [], []
    for line in lines:
        if line == "</>":
            if len(block) < 2:
                raise AssertionError(f"Unexpected source grammar in {path}")
            entries.append((block[0], "\n".join(block[1:])))
            block = []
        else:
            block.append(line)
    if block:
        raise AssertionError("Unterminated source")
    return sorted(entries)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    import importlib.metadata
    if importlib.metadata.version("mdict-utils") != "1.3.14":
        raise RuntimeError("Install the baseline engine: mdict-utils==1.3.14")
    fixture = json.loads((ROOT / "baseline/cases.json").read_text(encoding="utf-8"))
    expected = sorted((e["key"], e["text"]) for e in fixture["engine_entries"])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        generated = tmp / "rust"
        run("cargo", "run", "--locked", "--package", "studio-engine-probe", "--", "prove", ROOT / "baseline/cases.json", generated)
        extracted = tmp / "legacy-extracted"
        run(sys.executable, "-m", "mdict_utils", "-x", generated / "qualification.mdx", "-d", extracted)
        candidates = list(extracted.rglob("*.txt"))
        if len(candidates) != 1 or records(candidates[0]) != expected:
            raise AssertionError("Legacy extractor did not recover identical key/body multiset from Rust MDX")
        # The original default packer may have ordering limitations: failures are evidence.
        legacy_mdx = tmp / "legacy.mdx"
        run(sys.executable, "-m", "mdict_utils", "-a", generated / "qualification.txt", legacy_mdx, "--encoding", "utf-8")
        recovered = tmp / "rust-extracted"
        run("cargo", "run", "--locked", "--package", "studio-engine-probe", "--", "unpack", legacy_mdx, recovered)
        if records(recovered / "dictionary.txt") != expected:
            raise AssertionError("Rust reader did not recover identical legacy key/body multiset")
        resource_dir = tmp / "legacy-resources"
        run(sys.executable, "-m", "mdict_utils", "-x", generated / "qualification.mdd", "-d", resource_dir)
        for resource in fixture["engine_resources"]:
            relative = resource["key"].replace("\\", "/").lstrip("/")
            matches = [path for path in resource_dir.rglob("*") if path.is_file() and path.as_posix().endswith("/" + relative)]
            if len(matches) != 1 or matches[0].read_bytes() != bytes(resource["bytes"]):
                raise AssertionError(f"MDD cross-reader mismatch: {relative}")
    report = {"status": "passed", "checks": ["rust_mdx_to_legacy_reader", "legacy_mdx_to_rust_reader", "rust_mdd_to_legacy_reader"], "not_proven": ["legacy_custom_sort_writer", "legacy_mdd_to_rust", "reader_apps", "legacy_encodings"]}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
