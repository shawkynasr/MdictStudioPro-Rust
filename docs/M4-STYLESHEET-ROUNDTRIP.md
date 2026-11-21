# Numeric stylesheet round-trip qualification

The user confirmed the five-record SQLite rebuild in MDict and GoldenDict,
including both 字 definitions, Arabic, title `dict22` and description
`hi new world`. That database has an empty numeric stylesheet. This next
qualification exercises a nonempty stylesheet, without changing production
conversion code or expanding the supported input profile.

From the updated project root on the Rust-enabled Mac:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_stylesheet_roundtrip.py --output m4-stylesheet-out
```

Use a new output name if that directory already exists. The existing verified
vendor tree, cached Rust dependencies and Python mdict-utils environment are
required. This runner does not install packages or touch existing dictionaries.

The Rust adapter example submits six ordinary shared publication jobs, taking
and forgetting each result: JSONL → MDX → SQLite → MDX for UTF-8, then UTF-16.
Receipts and dictionaries are placed below the new output directory. The
independent Python reader disables numeric style expansion, comparing raw
definitions, duplicate order, empty entries and all decoded header attributes.
Source fingerprints and the approved dependency graph are checked as well.
Only the isolated M3 adapter seed lock may be normalized, as in m3_shell.py.

After `automated_roundtrip_passed_reader_checks_pending`, test
`native/utf8/rebuilt.mdx` and `native/utf16/rebuilt.mdx` in both readers.
Disable other test copies to avoid combined dictionary results. Each rebuilt
dictionary contains seven records and two definitions under `duplicate`.

| Headword | Expected |
| --- | --- |
| inline | Blue `INLINE_BLUE_OK`, an inline CSS control |
| marker | Blue `MARKER_BLUE_OK`, with no literal numeric marker |
| combined | Both blue strings; `marker-bold` in bold |
| duplicate | First definition blue; second definition bold |
| multilingual | English, Chinese, Arabic, and blue marker text |
| empty | Entry with an empty definition |

If anything differs, compare with `original.mdx` from the same encoding folder,
loaded separately. No MDD is needed. Automated byte/header checks do not claim
visual reader qualification. The new example requires compilation on the Mac;
Rust is unavailable in the preparation environment.

## Recheck files from the first runner

The first Mac run compiled and completed all native jobs, then the Python
verifier failed its stylesheet comparison. ElementTree normalized literal
attribute line feeds to spaces. The corrected verifier protects attribute
whitespace before entity decoding, matching the MDX header interpretation.
It still validates XML syntax and compares every decoded attribute exactly.
No native conversion changes are involved in this correction.

Recheck the existing files without rebuilding or modifying them:

```sh
.venv/bin/python scripts/m4_stylesheet_roundtrip.py --output m4-stylesheet-out-check --verify-existing m4-stylesheet-out/native
```

The new report records read-only verification mode and does not claim a new
native run. Reader dictionaries remain in the original output directory.
