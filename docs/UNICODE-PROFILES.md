# Unicode sorting and lookup qualification

The canonical literal-header candidate is now supported by the user's native
acceptance for both UTF-8/UTF-16 in MDict and GoldenDict: no missing definitions
or crashes. The finalized offline report, candidate hashes and separate manual
observation are retained under docs/evidence/header-lookup-finalized-user-run.
Restart behavior was not separately stated in the final user reply.

This next batch tests previously unproven Unicode cases. It leaves every existing
export profile and engine dependency unchanged. It neither repairs the official
MdxBuilder comparator nor assumes Unicode lowercase, casefold and UTF-16 ordering
are interchangeable.

## Run

After updating in place, retaining .venv, vendor, dictionaries and old reports:

```sh
.venv/bin/python scripts/unicode_profiles.py --output unicode-out
```

Upload unicode-out/unicode-profile-report.json and any log named by a failure.
No real corpus, font, GUI or stress rerun is needed. Use a new output folder;
existing directories are refused. New Rust code remains uncompiled in the
authoring environment. The driver compiles and tests the existing real-rebuild
workspace on the user's Mac without changing its dependency graph.

## Exhaustive mappings and bounded word tests

The Rust probe enumerates all 1,112,064 Unicode scalar values, excluding surrogate
code points. It reports every non-identity char lowercase mapping and the Rust
Unicode version. Python compares all scalars, reports its Unicode database version,
and retains any differences. A difference stops the batch rather than silently
changing a compatibility profile. This is an exhaustive single-character test,
not a proof over all possible strings or official historical casing tables.

Selected strings compare whole-string and per-character lowercase independently.
Greek final sigma can depend on surrounding letters; for example Python lowers
ΟΣ to ος but independent character lowercase produces οσ. This distinction must
stay visible between whole-string writer ordering and the tested reader's
scalar-lower fallback. Exact-first lookups retain every raw spelling first.

The fixtures include dotted I, combining marks, sharp S, long S, sigma variants,
micro/Greek mu, multiplication/division signs, Arabic, Chinese, fullwidth letters,
private-use and supplementary characters, ASCII backslash/punctuation, NBSP and
ideographic space. Composed and decomposed accents remain separate raw keys;
no NFC/NFKC, accent removal or full casefold is introduced.

Four new small MDX cases use existing policy-build: literal UTF-8 and UTF-16,
plus the two unchanged app legacy modes in UTF-8. Independent Python physical
rows must match exact payload/order expectations. All stored keys are queried;
literal cases additionally check non-exact scalar-lower fallback against a
separate oracle. Independent block/checksum/terminator audits remain required.
The legacy modes qualify their app comparator and exact lookups only, and remain
unqualified for native export. The mdxbuilder app mode is not the official wide
or narrow comparator. Existing legacy header overlays stay diagnostic-only.

The report includes the different scalar/UTF-16-unit order for fullwidth Ａ and
supplementary 𐐀. Comparing UTF-16 after modern lowercase is only an illustration;
it does not implement the official builder's custom mapping. Offline reader
success also cannot establish a native reader's binary-search compatibility.

## After offline review

Complete offline success prepares only two literal files in native-candidates:
08-unicode-utf8.mdx and 08-unicode-utf16.mdx. Wait for report review before
importing either. Native-checklist.json maps raw query spellings to distinguishable
UNICODE_nn payload markers. Reader case grouping may differ from the studio API;
the important next native check is that stored definitions remain accessible,
especially across supplementary/BMP ordering and Greek casing boundaries.

The success status is unicode_lowercase_and_profile_subset_passed_native_pending_M1_open.
All-string Unicode conformance, native Unicode behavior, exact official builder
mapping, broader metadata policy and M1 completion remain open.
