"""Verify baseline and package deliverables, excluding generated caches/builds."""
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
completed = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "baseline", "-v"], cwd=ROOT, capture_output=True, text=True)
(ROOT / "docs" / "baseline-test-log.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
if completed.returncode:
    print(completed.stdout + completed.stderr)
    raise SystemExit(completed.returncode)
evidence = subprocess.run([sys.executable, "scripts/validate_evidence.py"], cwd=ROOT, capture_output=True, text=True)
(ROOT / "docs" / "evidence-validation-log.txt").write_text(evidence.stdout + evidence.stderr, encoding="utf-8")
if evidence.returncode:
    print(evidence.stdout + evidence.stderr)
    raise SystemExit(evidence.returncode)
snapshots = subprocess.run([sys.executable, "scripts/check_safari_sources.py"], cwd=ROOT, capture_output=True, text=True)
(ROOT / "docs" / "safari-snapshot-check-log.txt").write_text(snapshots.stdout + snapshots.stderr, encoding="utf-8")
if snapshots.returncode:
    print(snapshots.stdout + snapshots.stderr)
    raise SystemExit(snapshots.returncode)
contracts = subprocess.run([sys.executable, "scripts/run_contracts.py"], cwd=ROOT, capture_output=True, text=True)
(ROOT / "docs" / "interop-contract-test-log.txt").write_text(contracts.stdout + contracts.stderr, encoding="utf-8")
if contracts.returncode:
    print(contracts.stdout + contracts.stderr)
    raise SystemExit(contracts.returncode)
output = ROOT.parent / "MdictStudioPro-M0-M1.zip"
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if relative.parts[0].startswith(("m3-shell-out", "m4-database-out", "m4-stylesheet-out")) or any(p in {"node_modules", "dist", "gen"} for p in relative.parts):
            continue
        if relative.parts[0].startswith(("m2-application-out", "m2-jobs-out", "m2-dictionary-jobs-out", "m2-v2-import-out", "m2-import-jobs-out", "m2-metadata-out", "m2-metadata-jobs-out", "m2-sizing-out", "m2-index-out", "m2-sessions-out", "m2-stream-extract-out", "m2-extraction-jobs-out", "m2-large-io-out", "m2-publication-runtime-out", "m2-converter-runtime-out", "m2-real-readers-out", "m2-real-converters-out", "m2-official-converters-out", "m2-concise-full-out", "m2-cc-full-out", "m2-xlsx-spool-out", "m2-revised-render-out", "m2-full-converters-out", "m2-real-publication-out", "m2-cc-pack-out")):
            continue
        if path.is_file() and relative.parts[0] not in {"out", "out-next", "out-inputs", "sort-out", "safari-out", "interop-out", "interop-out-v2", "vendor", "corpus-local.json", "real-corpus-inputs", "real-converter-inputs", "real-converter-archives"} and not relative.parts[0].startswith(("codec-out", "interop-out-v3", "reader-out", "corpus-out", "wire-out", "minimal-out", "style-out", "reference-out", "style-wire-out", "resource-out", "rebuild-out", "stress-out", "checksum-out", "fresh-out", "header-out", "unicode-out", "casing-out", "integrated-out", "unicode-native-out", "m1-final-out", "m2-core-out", "m2-resources-out", "m2-text-out", "m2-xlsx-out", "m2-moe-out")) and not any(p in {"__pycache__", "target", ".venv", ".git"} for p in relative.parts):
            archive.write(path, Path(ROOT.name) / relative)
with zipfile.ZipFile(output) as archive:
    assert archive.testzip() is None
    print(f"{output}: {len(archive.infolist())} files, {output.stat().st_size} bytes")
