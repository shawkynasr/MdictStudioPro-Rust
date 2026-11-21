# Native stylesheet rendering and real dictionary qualification

## Exact binary inspection and offline v4 candidate

The received UTF-16 pair matches its fixture hashes. Structural checks pass,
but all 13 MDX definitions lack an encoded terminal NUL, both headers omit
Encrypted, and the MDD lacks legacy metadata. An isolated v4 source candidate
addresses these record/header gaps. It is uncompiled locally and not a confirmed
native crash fix. Sorting/strip consistency and stylesheet semantics remain
open. See docs/NATIVE-WIRE-FINDINGS.md. The next step is offline only:

```sh
.venv/bin/python scripts/check_native_wire.py --output wire-out
```

Keep both readers closed; use an output folder outside their dictionary search
paths. Return native-wire-report.json and relevant logs. Do not import outputs.

## Current blocker: native import crash

The subsequent user report identifies the UTF-16 mdxbuilder pair as crashing
MDict too. The uploaded crash log confirms MDict 2.2.6 (build 200), x86_64 on
macOS 15.8.1, with EXC_BAD_ACCESS/SIGSEGV at address 0x90. The main-thread stack
starts with strlen and vfprintf/vsnprintf during application initialization.
MDict frames are unsymbolicated: the log does not identify a dictionary field,
the failing binary, or whether this is an error-reporting path after another
parse failure. No result is attributed to GoldenDict.

Both reported pairs share the MDD hash. Their MDX encodings and sorting profiles
differ. Shared headers, resources, block conventions and native error handling
remain candidates; an encoding-only diagnosis is not established. Source
inspection shows the generated core header omits Encrypted, which the working
real files include. Treat that as a compatibility lead, not a proven crash
cause. The subsequent binary audit and source candidate are documented above.
No confirmed native fix is claimed.

On 2026-10-28 the user reported repeated application crashes after copying
`reader-utf8-mdict-utils.mdx` and its MDD, requiring their removal. The affected
reader is not yet identified. Preserve those generated files outside all reader
scan folders, and do not import the remaining generated variants while this is
investigated. All eight variants share the same MDD hash, so changing only the
MDX variant would not isolate the resource archive.

The attached fixture report passes all eight automated checks, but none is a
native app check. The imported pair has a user-reported native import failure;
this blocks native writer qualification and production selection. The MDX,
MDD, import/indexing path and rendering path have not yet been isolated. Do not
assign a cause to embedded styles, resources, sorting or either app without
diagnostic evidence. Prior corpus read-comparison passes remain valid within
their original read-only scope.

MDict, its crash log and the exact generated pair are now identified.
Confirm recovery after removing generated fixtures. Do not delete
reader preferences, existing dictionary libraries or caches as a speculative
repair. The visual-test steps below are paused; they describe the pending plan,
not instructions to reimport the crashing files now.

Evidence: `docs/evidence/native-import-crash/observation.json` and the unchanged
uploaded `reader-fixture-report.json`. No writer fix is claimed from this report.

## Latest user-run comparison and installed readers

The uploaded corpus report passes all four cases: 296,110 MDX records and
17 MDD resources agree between Rust and mdict-utils, preserving duplicate
counts. All metadata attributes match, all 36 sampled lookups pass, and input
hashes are unchanged. Evidence: `docs/evidence/real-corpus-user-run`.
No identical corpus rerun is needed. This does not prove write/export parity,
all lookup keys, other real encodings, production limits, or visual rendering.

The user reports these installed readers, recorded in `baseline/native-readers.json`:

| Worksheet label | Application | Version |
|---|---|---|
| Reader A | MDict for macOS | 2.2.6 (build 200) |
| Reader B | GoldenDict | 26.6.1-7548db1682 (master), built 2026-06-29T06:51:41Z |

Application versions are user-reported, not rendering passes. The real-reader
CSV is prefilled with them; apply the same mapping to the generated synthetic
reader worksheet. Results remain NOT_RUN until observed in the applications.

The copied corpus input folder has both CSS files and the CC-CEDICT MDD. The
manifest's external fonts/amiri-regular.ttf path was not present there. This
does not disprove the user's original companion folder/archive availability;
keep that complete structure when checking Almaany in the native readers.

Next, enable only the UTF-8 mdict-utils synthetic fixture and its matching MDD
in each reader. Compare marker-red against inline-red, marker-blue against
inline-blue, then test MDD CSS/image loading and repeat for UTF-16. Send the
generator report and per-reader observed results, not another identical corpus
scan. Instructions and expected appearances follow below.

## What was actually verified here

The attached originals were read without modification. An independent stdlib
auditor checked all v2 section lengths, key summaries, record offsets, strict
text decoding and all key/record block ADLER32 checksums. File SHA-256 values
before and after agree. The uploaded dictionaries are not included in this ZIP.

| Dictionary | MDX records | Duplicate headwords | MDX record blocks |
|---|---:|---:|---:|
| CC-CEDICT 092026 | 202,884 | 4,057 | 1,129 |
| Almaany English/Arabic | 82,812 | 10,569 | 328 |
| 新华成语词典（第2版） | 10,414 | 2 | 123 |

All three passed the structural audit. The CC-CEDICT MDD also passed: 17
resources over eight record blocks. This is useful structural evidence, not a
Rust/mdict-utils comparison or a native reader pass. Both runtimes are unavailable
here. The full report is `docs/evidence/real-corpus-local-audit/structural-audit.json`.

All three MDX files are unencrypted UTF-8 v2, with empty embedded StyleSheet
values and no numeric style markers. They exercise real HTML, external CSS,
duplicates, resources, Chinese and Arabic; they do not close the embedded-style
newline gate or prove other real-world storage encodings.

## Companion assets

CC-CEDICT links `cedict_ts.css`, which is inside its MDD along with fonts/images.
That CSS references `entry-bullet.png`, absent from the attached archive; it may
exist externally in the user's folder. Three lowercase `merriweather-italic-py`
font references match uppercase `Merriweather-Italic-py` archive names only
after case folding. Check native-reader behavior rather than assuming failure.

Almaany links the attached `almaanyEnAr-ArEn.css`. Its CSS references
`fonts/amiri-regular.ttf`. The user reports that this font is present in their
folder. It was not attached here, and is not in the attached CC-CEDICT MDD, so
font availability is reported as user-supplied information rather than a local
failure. Preserve the relative fonts folder beside the dictionary/CSS, or its
correctly named resource archive if that is how the dictionary is distributed.
Do not move Almaany resources into an unrelated CC-CEDICT archive.

The Chinese idiom dictionary links the attached `xhcycd.css`; preserve that
filename even though it differs from the MDX basename.

## Generate the embedded-style control fixtures on the Mac

Use the updated project and existing v3 vendor/venv:

```sh
python3 scripts/prepare_sort_experiment.py --revision 3 --reuse
.venv/bin/python scripts/reader_fixtures.py --output reader-out
```

This creates four base dictionary pairs (UTF-8/UTF-16, both sort profiles),
plus header-only CRLF variants. Each MDX has an MDD of the same basename.
The CRLF experiment is confined to freshly generated synthetic files: only
the stylesheet header/framing changes; key/record bytes remain identical.
No production writer patch or real input repair is performed.

The generator checks raw entries through Rust and Python, exact MDD bytes,
and Python's explicit stylesheet substitution. Rust fixture creation and the
new streaming CLI have not been compiled in this environment. A blocked or
failed generator report needs its build.log. Local tests check the harness,
not real dictionary application behavior.

## Check two independent dictionary applications

Use applications you already have, preferably different implementations.
GoldenDict-ng is one desktop option; official sources:
https://github.com/xiaoyifang/goldendict-ng and
https://xiaoyifang.github.io/goldendict-ng/ . No application is marked passed.

Start with only `reader-utf8-mdict-utils.mdx` and its MDD enabled. Use an isolated
dictionary group, disable custom style overrides, and record application version,
OS and the generated file hashes. Reindex when replacing or changing a fixture.
Overlapping fixture headwords must not produce results from another dictionary.

1. Look up `style-inline-red` and `style-marker-red`: both should show the same
   dark red bold text with a red border; the marker entry must not show `1`.
2. Compare `style-inline-blue` and `style-marker-blue`: both should be blue and
   underlined. This checks a second independent stylesheet triplet.
3. Look up `resource-control`: green CSS background and a green square image.
   Check these separately; successful inline styles do not prove MDD loading.
4. Check Chinese `字`, Arabic `مرحبا`, redirect `redirect`, both senses under
   `duplicate`, and distinct `a-b`, `ab`, `a b` definitions.
5. Repeat with the UTF-16 base fixture. If embedded styles differ from inline
   controls, test the matching CRLF variant separately and capture the result.
6. Repeat in a second independent app. Test the second sort profile once the
   first profile's controls are established.

Fill `reader-out/reader-results.csv` using PASS/FAIL/UNSUPPORTED/NOT_RUN, preserving
fixture hashes and describing the visible result. Record screenshots only when
needed to show a failure; reference the local filename in the CSV. Never mark an
entire dictionary passed merely because it opened or one word rendered.
For the real dictionaries, fill `docs/real-reader-results.csv` as well. Record
the corresponding input hashes from the corpus report and add a row for any
specific resource/duplicate problem rather than summarizing it as an open pass.

## Compare the three real dictionaries on the Mac

Create `real-corpus-inputs` in the project folder. Place the original three MDX
files, CC-CEDICT MDD, both CSS files and Almaany's fonts folder there, preserving
their exact names and relative structure. Add other companion MDD archives to
the manifest as separate cases if applicable. Then run:

```sh
.venv/bin/python scripts/real_corpus.py check --manifest baseline/real-corpus-manifest.json --output corpus-out
```

The supplied manifest selects the four attached dictionary binaries. It checks
known/sample lookups and reports companion-file presence separately. If your
files are already in a dedicated folder elsewhere, generate a manifest instead:

```sh
.venv/bin/python scripts/real_corpus.py init "/path/to/dictionary-folder" --manifest corpus-local.json
.venv/bin/python scripts/real_corpus.py check --manifest corpus-local.json --output corpus-out
```

Review tags and add known `lookup_keys` before checking. Outputs/manifests must
be new. Originals are never overwritten, packed, repaired or extracted.

The comparator scans every physical record from both engines and uses SQLite
on disk to compare exact UTF-8 keys and SHA-256 payload multisets, retaining
duplicate counts. MDX bodies are compared as each reader's decoded UTF-8;
MDD bodies are compared as binary bytes. No trimming or Unicode normalization
is applied by the harness. Hash-based comparisons rely on SHA-256 collision
resistance; this does not prove equivalence for every possible raw encoding.
Metadata differences are reported separately, and sampled Rust lookups are
checked against Python's full physical inventory.

Streaming avoids the former whole-dictionary JSON/Vec adapter. It does not
bound either library's internal index/block caches or establish production
resource limits. Per-engine elapsed time includes startup/build overhead and
is not a benchmark. A complete end marker and successful exit are required;
partial scans cannot pass. The timeout defaults to 30 minutes per subprocess.

The SQLite files contain keys and payload hashes; dictionaries and full bodies
are not copied into the report. Return `corpus-out/corpus-report.json`, relevant
worker logs for failures, `reader-out/reader-fixture-report.json`, and the filled
reader CSV. Native rendering stays NOT_RUN until real app observations arrive.

## Remaining evidence

The embedded stylesheet contract remains open; generic XML parsing and legacy
MDict raw attribute parsing differ. Do not normalize the original metadata to
make the existing ten failures disappear. Native rendering observations will
help choose and document the correct production policy. Real legacy encodings,
encryption/LZO, large files, cross-platform behavior and write/export parity
remain separate work. No engine selection or M1 completion is claimed here.
