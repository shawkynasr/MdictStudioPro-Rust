"""Verify supplied snapshots; --record-from explicitly creates their manifest."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/safari-source-manifest.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def record(archives):
    items = []
    for archive, prefix, target in zip(archives, ["mdx-main/", "mdx_util-main/"], ["reference/safari-mdx", "reference/safari-mdx-util"]):
        hashes = {}
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                if member.is_dir():
                    continue
                if not member.filename.startswith(prefix):
                    raise AssertionError("Unexpected archive prefix")
                name = member.filename[len(prefix):]
                if ".." in Path(name).parts:
                    raise AssertionError("Traversal in snapshot")
                original = source.read(member)
                if (ROOT / target / name).read_bytes() != original:
                    raise AssertionError(f"Snapshot differs: {name}")
                hashes[name] = digest(original)
            commit = source.comment.decode("ascii").strip()
        items.append({"archive":Path(archive).name,"archive_sha256":digest(Path(archive).read_bytes()),"commit":commit,"root":target,"files":hashes})
    MANIFEST.write_text(json.dumps({"snapshots":items},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def check():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for snapshot in manifest["snapshots"]:
        for name, expected in snapshot["files"].items():
            if digest((ROOT / snapshot["root"] / name).read_bytes()) != expected:
                raise AssertionError(f"Changed fork source: {snapshot['root']}/{name}")
        print(f"PASS unchanged {snapshot['root']} at {snapshot['commit']}: {len(snapshot['files'])} files")
    core = tomllib.loads((ROOT / "reference/safari-mdx/Cargo.toml").read_text())
    cli = tomllib.loads((ROOT / "reference/safari-mdx-util/Cargo.toml").read_text())
    if core["package"]["version"] != "0.5.4" or cli["package"]["version"] != "0.6.1":
        raise AssertionError("Unexpected inspected fork versions")
    print("PASS manifests and snapshot integrity; Rust runtime checks NOT performed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-from", nargs=2, metavar=("MDX_ZIP", "UTIL_ZIP"))
    args = parser.parse_args()
    if args.record_from:
        record(args.record_from)
    check()
