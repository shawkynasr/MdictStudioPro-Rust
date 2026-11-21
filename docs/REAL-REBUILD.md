# Rebuild the real corpus and reopen it independently

**Latest result:** the user's real rebuild report passes all four files,
296,110 MDX definitions, 17 MDD resources and 36 sampled lookups. All original
input hashes are unchanged. Publication was withheld only for the missing
declared Amiri font. Use the finalize-only command below for that completed run.

## Finish the existing run without rebuilding

The original dictionary's actual font has been located at
/Users/shawky/Documents/Dict/Ar/almaanyEnAr-ArEn/fonts/amiri-regular.ttf.
Use this dictionary asset rather than a similarly named application preview PNG.
From the project root, after updating sources while retaining rebuild-out:

```sh
.venv/bin/python scripts/finalize_real_rebuild.py \
  --output rebuild-out \
  --amiri-font "/Users/shawky/Documents/Dict/Ar/almaanyEnAr-ArEn/fonts/amiri-regular.ttf"
```

This requires the existing report to be waiting only for Amiri. It verifies
every original input hash, each staged dictionary/companion hash, prior scan
counts, metadata/order digests, sampled lookups and structural-audit identities.
It refuses changed inputs/outputs, extra files, links and existing verified
folders. It does not run Cargo or rescan dictionary records. The new font is
copied to the staged fonts folder and checked byte-for-byte, then the folder is
promoted to verified-dictionaries. The previous report is retained as
real-rebuild-report.before-finalize.json and the updated report records the
font source/hash and reuse of the earlier verified build.

If finalization passes, test the published corpus as described under Native
checks below. The original dictionaries and font remain read-only.

The prior real corpus gate only compared existing files through Rust and Python.
This gate actually rebuilds all four files (three MDX and one MDD), then compares
source and output through both readers. Native MDD CSS, image and diagnostic-font
fixtures have user-reported success for UTF-8/UTF-16 in both native readers.
Real rebuilt dictionaries and Amiri are not yet qualified by those fixtures.

## A constrained metadata/order-preserving rebuild

The app-produced real MDX files declare Stripkey=Yes, with a lowercase k. The
builder owns a different-cased StripKey field. Recreating attributes naively can
introduce contradictory settings, and choosing a new comparator would mix
ordering-policy changes into the rebuild test.

The isolated v6 engine experiment therefore adds only PreserveInput, a stable
ordering profile that retains source physical order. Existing v2-v5 source and
profiles remain untouched. The new real-rebuild workspace decodes each physical
entry/resource into the builder, which reconstructs the key/record sections and
compression. It then replaces the builder-created header prefix with the source
header bytes, including their original length and checksum. All block offsets
are relative within the rebuilt sections; the source header is not an absolute
offset table. The same-version/encoding/unencrypted restrictions are essential.

This explicitly tests existing-dictionary rebuilding. It is **not** proof of a
new general metadata serializer, correct normalization of header aliases, a new
native comparator or fresh TXT/XLSX packing parity. The report states this scope.
Definition text is not trimmed, normalized or style-expanded. MDD resources stay
binary. The prior stylesheet fix remains in the native fixture wrapper; the
real rebuild preserves the original header rather than changing its stylesheet.

Supported preset: unencrypted v2 UTF-8 MDX and v2 MDD, at most 32 MiB compressed
input per file, 500,000 entries/resources and 256 MiB cumulative decoded key and
payload bytes per rebuild. The builder retains entries in memory; these are
qualification budgets, not proven production memory limits. Encrypted input and
other MDX encodings are refused. The original uploaded four-file corpus fits
this preset. Root and prior workspace locks stay pinned; the new workspace lock
changes only its own package identity from the existing dependency graph.

## Run on the same Mac corpus

Update project sources, keeping .venv, vendor and real-corpus-inputs. Use the
same four-case manifest and original files from the earlier corpus run:

```sh
.venv/bin/python scripts/real_rebuild.py \
  --manifest baseline/real-corpus-manifest.json \
  --output rebuild-out
```

The expected input directory is real-corpus-inputs in the project root. If your
paths changed, edit a copy of the manifest and pass that copy. The script never
writes to source dictionaries or companion paths and refuses existing output
directories. It never opens a native reader.

The earlier corpus report did not find Amiri in the copied test directory, even
though the user has it in the original asset folder. Put a copy at
real-corpus-inputs/fonts/amiri-regular.ttf, or point to the existing original
file without changing the input directory:

```sh
.venv/bin/python scripts/real_rebuild.py \
  --manifest baseline/real-corpus-manifest.json \
  --amiri-font /path/to/fonts/amiri-regular.ttf \
  --output rebuild-out
```

Only use the second command instead of the first when the override is needed.
Use a new output name for repeated runs. The override is copied into output
fonts/amiri-regular.ttf; its source is read-only. No Amiri font or real dictionary
is redistributed in this project ZIP.

## What the driver verifies

It prepares v6 from the checksum-pinned published crate, verifies the exact
source delta, runs the Rust rebuild test and rebuilds each file to staging.
Four scans per file cover source Rust/Python and rebuilt Rust/Python. SQLite
stores exact UTF-8 keys, payload SHA-256 values and duplicate multiplicities;
ordered key/payload digests separately detect physical reordering. A complete
end marker is mandatory, so truncated subprocess output cannot pass.

It checks exact reader metadata and raw header-prefix equality. The independent
auditor checks all emitted block checksums, sizes, counts, key summaries, offsets
and MDX record terminators. Sampled exact lookups, including manifest-provided
keys, must match the full original Python inventory with duplicate counts.

Declared CSS/fonts are copied byte-for-byte to matching relative output paths.
The CC-CEDICT MDD companion must be the rebuilt MDD, not a copy of the original.
All source dictionaries and existing declared companions are hashed before and
after. Existing basenames are retained so embedded CSS links and pair discovery
continue to refer to the same names. Original titles and descriptions stay exact.

Only after every file and declared companion passes does the driver publish
**rebuild-out/verified-dictionaries/**. Missing Amiri or other declared assets
produces rebuild_records_passed_companions_pending and withholds that folder.
This checks declared companions, not every dependency anywhere in a real HTML
definition or CSS file; pre-existing missing assets remain a coverage limit.

The report is **rebuild-out/real-rebuild-report.json**. A successful status is
real_rebuild_offline_passed_native_untested. Other statuses are not native-ready.
Logs and SQLite inventories stay outside the deliverable package. The timeout
defaults to 1800 seconds per subprocess; failed or timed-out cases remain staged.
The new Rust workspace is uncompiled in the authoring environment.

## Native checks after offline success

Use only verified-dictionaries as a temporary reader directory; do not load the
original corpus alongside it because titles/headwords are intentionally equal.
Start with the Almaany MDX, its CSS and fonts folder. Compare the original and
rebuilt Arabic definitions in separate sessions in GoldenDict and MDict; check
letter joining, direction and visible font appearance, then restart both apps.
Asset byte equality is not itself proof that a native renderer selected Amiri.

Then test the rebuilt CC-CEDICT matched MDX/MDD pair and Chinese idiom MDX with
xhcycd.css. Compare known entries, redirects, duplicate entries, styling and
images with the originals. Do not export, replace or remove original dictionaries.
On a crash, stop that reader's sequence and remove only the new test directory
from its scan configuration before reopening.

Return the report and native results. No native automation or success is claimed
by the script. Larger files, production resource limits, fresh-source packing,
non-C-locale sorting and remaining metadata contracts keep M1 open.
