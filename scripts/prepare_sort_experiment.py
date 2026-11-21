"""Vendor and mechanically patch the checksum-pinned published crate.

Only writes inside this project's new vendor directory. Never modifies Cargo's
cache, the original engine probe, its manifest, or its uploaded Cargo.lock.
Requires the .crate archive already downloaded on the user's Rust-enabled host.
"""
import argparse
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.8"
MARKER = "STUDIO_LEGACY_SORT_EXPERIMENT"

# Revision 4 changes only the writer. Invert these exact edits during source
# verification so a prepared candidate is still bound to the passing v2 hash.
NATIVE_WIRE_EDITS = [
    ('        let encoded_body = encoding.encode(body, "entry body")?;',
     '        let mut encoded_body = encoding.encode(body, "entry body")?;\n        encoded_body.extend(std::iter::repeat_n(0, encoding.unit_size()));'),
    ('    if declares_encoding {',
     '    xml.push_str(" Encrypted=\\"No\\"");\n    if declares_encoding {'),
    ('        xml.push_str(&format!(" Encoding=\\"{}\\"", encoding.label()));\n    }',
     '        xml.push_str(&format!(" Encoding=\\"{}\\"", encoding.label()));\n    } else {\n        xml.push_str(" Encoding=\\"\\"");\n    }'),
    ('    xml.push_str("/>");', '    xml.push_str("/>\\r\\n");'),
]


def native_wire_patch(source, reverse=False):
    edits=reversed(NATIVE_WIRE_EDITS) if reverse else NATIVE_WIRE_EDITS
    for before,after in edits:
        source=replace_once(source,after if reverse else before,before if reverse else after,"revision-4 native wire contract")
    return source


def literal_sort_patch(source, reverse=False):
    """Add a diagnostic profile; preserve both legacy profiles byte-for-byte."""
    edits = [
        ('pub enum LegacySort {', 'pub enum LegacySort {\n    /// Header StripKey=No: Unicode lowercase, retaining punctuation and spaces.\n    HeaderLiteralC,'),
        ('LegacySort::MdictUtilsC => word.to_lowercase(),',
         'LegacySort::MdictUtilsC | LegacySort::HeaderLiteralC => word.to_lowercase(),'),
        ('    if is_mdd {', '    if is_mdd || profile == LegacySort::HeaderLiteralC {'),
    ]
    for before, after in reversed(edits) if reverse else edits:
        source = replace_once(source, after if reverse else before,
                              before if reverse else after, "revision-5 literal sort")
    return source


def preserve_order_patch(source, reverse=False):
    """Qualification only: retain the already validated physical input order."""
    if not reverse and 'LegacySort::PreserveInput' in source:
        raise ValueError('Refusing repeated revision-6 source order patch')
    edits = [
        ('pub enum LegacySort {', 'pub enum LegacySort {\n    /// Rebuild qualification only: stable sort leaves original physical order intact.\n    PreserveInput,'),
        ('    let folded = match profile {', '    let folded = match profile {\n        LegacySort::PreserveInput => word.to_owned(),'),
        ('    // UTF-8 string order matches Unicode scalar order', '    if profile == LegacySort::PreserveInput { return Ordering::Equal; }\n    // UTF-8 string order matches Unicode scalar order'),
    ]
    for before,after in reversed(edits) if reverse else edits:
        source=replace_once(source,after if reverse else before,before if reverse else after,'revision-6 source order')
    return source


def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f"Refusing patch: {label} anchor must occur exactly once")
    return text.replace(before, after, 1)


def writer_patch(source, revision=2):
    if revision not in {2, 3, 4, 5, 6}:
        raise ValueError("Unsupported writer patch revision")
    source = replace_once(source, "mod collation;", "mod collation;\nmod studio_legacy_sort;\npub use studio_legacy_sort::LegacySort;", "module")
    source = replace_once(source, "    record_block_target_bytes: u32,", "    record_block_target_bytes: u32,\n    legacy_sort: Option<LegacySort>,", "options field")
    source = replace_once(source, "            record_block_target_bytes: Self::DEFAULT_RECORD_BLOCK_TARGET_BYTES,", "            record_block_target_bytes: Self::DEFAULT_RECORD_BLOCK_TARGET_BYTES,\n            legacy_sort: None,", "default")
    source = replace_once(source, "impl WriteOptions {", """impl WriteOptions {
    /// Selects experimental Python C-locale physical ordering.
    /// Does not change KeyCaseSensitive, StripKey, or reader lookup behavior.
    pub fn with_legacy_sort(mut self, profile: LegacySort) -> Self {
        self.legacy_sort = Some(profile);
        self
    }

    /// Returns the optional experimental physical ordering profile.
    pub const fn legacy_sort(&self) -> Option<LegacySort> {
        self.legacy_sort
    }
""", "options methods")
    source = replace_once(source,
        ".sort_by(|left, right| collation::compare(self.kind, &left.key, &right.key));",
        """.sort_by(|left, right| match self.options.legacy_sort {
                Some(profile) => studio_legacy_sort::compare(
                    profile, self.kind == Kind::Mdd, &left.key, &right.key,
                ),
                None => collation::compare(self.kind, &left.key, &right.key),
            });""", "stable sort")
    source = replace_once(source,
        "let xml_bytes: Vec<u8> = xml.encode_utf16().flat_map(u16::to_le_bytes).collect();",
        "let mut xml_bytes: Vec<u8> = xml.encode_utf16().flat_map(u16::to_le_bytes).collect();\n        xml_bytes.extend_from_slice(&[0, 0]);",
        "UTF-16LE XML terminator before header length and checksum")
    if revision >= 3:
        source = replace_once(source, 'Self::Utf16Le => "UTF-16LE",', 'Self::Utf16Le => "UTF-16",',
                              "MDict-compatible UTF-16 label; payload remains little endian")
    return native_wire_patch(source) if revision>=4 else source


def lib_patch(source):
    anchor = "    MddBuilder, MdxBuilder, WriteCompression, WriteEncoding, WriteOptions, WriteSummary,"
    return replace_once(source, anchor, anchor.replace("MddBuilder,", "LegacySort, MddBuilder,"), "public export")


def unpack_verified(data):
    """Read regular members only; refuse links, traversal and oversized archives."""
    members = {}
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] != f"mdictlib-{VERSION}" or any(p in {".", ".."} for p in parts):
                raise ValueError("Unsafe or unexpected crate member")
            if member.isdir():
                continue
            if not member.isfile() or len(parts) < 2:
                raise ValueError("Links and non-regular crate members are refused")
            total += member.size
            if total > 100 * 1024 * 1024 or len(members) >= 10000:
                raise ValueError("Crate exceeds experiment extraction limit")
            name = "/".join(parts[1:])
            if name in members:
                raise ValueError("Duplicate crate member")
            with archive.extractfile(member) as stream:
                members[name] = stream.read()
    for required in ["Cargo.toml", "src/lib.rs", "src/write/mod.rs", "src/write/collation.rs", "LICENSE"]:
        if required not in members:
            raise ValueError(f"Missing required crate file: {required}")
    return members


def prepare(crate, revision=2, reuse=False):
    vendor = ROOT / f"vendor/mdictlib-0.2.8-studio-sort-v{revision}"
    lock = tomllib.loads((ROOT / "Cargo.lock").read_text(encoding="utf-8"))
    packages = [p for p in lock["package"] if p["name"] == "mdictlib" and p["version"] == VERSION]
    if len(packages) != 1 or "checksum" not in packages[0]:
        raise ValueError("Expected one checksum-pinned mdictlib 0.2.8")
    data = crate.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    if checksum != packages[0]["checksum"]:
        raise ValueError("Crate SHA-256 does not match uploaded Cargo.lock")
    original = unpack_verified(data)
    cargo = tomllib.loads(original["Cargo.toml"].decode("utf-8"))
    if cargo["package"]["name"] != "mdictlib" or cargo["package"]["version"] != VERSION:
        raise ValueError("Unexpected crate identity")
    modified = dict(original)
    for name, transform in [("src/write/mod.rs", lambda s: writer_patch(s, revision)), ("src/lib.rs", lib_patch)]:
        modified[name] = transform(original[name].decode("utf-8")).encode("utf-8")
    new_module = "src/write/studio_legacy_sort.rs"
    if new_module in original:
        raise ValueError("Unexpected pre-existing patch module")
    modified[new_module] = (ROOT / "patches/studio_legacy_sort.rs").read_bytes()
    if revision >= 5:
        modified[new_module] = literal_sort_patch(modified[new_module].decode("utf-8")).encode("utf-8")
    if revision == 6:
        modified[new_module] = preserve_order_patch(modified[new_module].decode('utf-8')).encode('utf-8')
    diff = "".join("".join(difflib.unified_diff(
        original.get(name, b"").decode("utf-8").splitlines(keepends=True),
        modified[name].decode("utf-8").splitlines(keepends=True),
        fromfile="a/" + name, tofile="b/" + name,
    )) for name in ["src/write/mod.rs", "src/lib.rs", new_module])
    # The published crate is MIT. Preserve its LICENSE and all package notices.
    modified["STUDIO-SORT-PATCH.diff"] = diff.encode("utf-8")
    modified[MARKER + ".json"] = (json.dumps({
        "upstream_crate": "mdictlib", "version": VERSION, "archive_sha256": checksum,
        "rust_version": cargo["package"].get("rust-version"),
        "patch_revision": revision,
        "upstream_files": {n: hashlib.sha256(b).hexdigest() for n, b in original.items()},
        "modified_files": {n: hashlib.sha256(modified[n]).hexdigest() for n in ["src/write/mod.rs", "src/lib.rs", new_module]},
        "changes": ["optional stable physical sort", "new compatibility profiles", "UTF-16LE header terminator included in length and checksum", "no header-flag or reader changes"] + (["UTF-16 header label; unchanged little-endian key/body bytes"] if revision==3 else ["UTF-16 header label"] if revision>=4 else []) + (["encoded NUL after every MDX body before offset/block calculation", "Encrypted=No in both headers", "explicit empty MDD Encoding", "CRLF before header terminator"] if revision>=4 else []) + (["optional HeaderLiteralC profile; both legacy profiles unchanged"] if revision>=5 else []) + (["qualification-only PreserveInput stable physical order"] if revision==6 else []),
        "validation": "UNRUN: execute experiment tests",
    }, indent=2) + "\n").encode("utf-8")
    if vendor.exists():
        if not reuse:
            raise FileExistsError(f"Vendor directory already exists: {vendor}; use --reuse to verify without overwriting")
        for name, content in modified.items():
            path = vendor / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise ValueError(f"Existing vendor differs from reproducible revision {revision}: {name}")
        print(f"Verified unchanged existing revision-{revision} source: {vendor}")
        return
    vendor.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".prepare-sort-", dir=vendor.parent) as tmp:
        stage = Path(tmp) / "crate"
        stage.mkdir()
        for name, content in modified.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        if vendor.exists():
            raise FileExistsError("Vendor destination appeared during preparation")
        stage.rename(vendor)
    print(f"Prepared checksum-verified experiment: {vendor}")
    print("Review STUDIO-SORT-PATCH.diff before building.")
    print("Then: cargo test --manifest-path experiments/legacy-sort/Cargo.toml")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crate", type=Path, help="Exact mdictlib-0.2.8.crate archive; otherwise discover in Cargo cache")
    parser.add_argument("--revision", type=int, choices=[2,3,4,5,6], default=2)
    parser.add_argument("--reuse", action="store_true", help="Verify every generated member before reusing an existing tree")
    args = parser.parse_args()
    crate = args.crate
    if crate is None:
        cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
        candidates = sorted((cargo_home / "registry/cache").glob("*/mdictlib-0.2.8.crate"))
        if not candidates:
            parser.error("No cached archive. Run cargo fetch --locked at the project root or supply --crate PATH")
        # Each candidate must still match the checksum. Alternate registry caches
        # with the same exact package bytes are interchangeable for this probe.
        crate = candidates[0]
    prepare(crate, args.revision, args.reuse)


if __name__ == "__main__":
    main()
