# Fresh-source packing after original converter outputs

The completed real-corpus rebuild preserves the source header and order. This
step instead builds new dictionaries from TXT, without borrowing an existing
MDX header. It checks the boundary between the original converters and the new
Rust packer. It does not port those converters or Excel reading to Rust yet.

## Run

Update the project in place, retaining .venv, vendor, your corpus and reports:

```sh
.venv/bin/python -m pip install mdict-utils==1.3.14 openpyxl==3.1.5
.venv/bin/python scripts/fresh_pack.py --output fresh-out
```

Return fresh-out/fresh-pack-report.json. If it fails, also return the log named
in its error. A failure records active_case if a case was underway. Use a fresh
output directory for any retry; existing folders are refused.

No native reader testing, original dictionaries or font paths are needed. All
new artifacts are offline qualification files. Do not import them into MDict or
GoldenDict at this stage. Old readers and the upstream dependency stay unchanged.

## Checks

The driver re-runs baseline/run.py check. That creates fresh synthetic CEDICT and
XLSX inputs, executes the six original converter classes, and compares all nine
golden artifacts byte for byte. The freshly reproduced outputs therefore match
the frozen TXT files used for packing. The reference converter is still Python
with openpyxl 3.1.5. Rust calamine normalization and plugin conversion are separate
open gates; this run cannot qualify them.

Each of the six converter TXT files is packed under mdict-utils and mdxbuilder
legacy C-locale sort profiles. A seventh input adds duplicate keys, case and
punctuation ties, blank body lines, redirects, Arabic, Chinese, non-BMP text and
accented case variants. That makes 14 MDX cases. The boundary cases additionally
build two MDD files containing binary zero/high bytes, case-variant paths,
multilingual text and an empty resource.

The Rust packer parses the TXT independently. Its bounded UTF-8/LF preset keeps
the final body LF immediately before the standalone delimiter, matching the
existing app's TXT packing contract. It refuses BOM, CR, NUL, empty input, empty
bodies and incomplete records. It adds no inferred record. It uses the two
existing optional legacy profiles; it does not claim official MdxBuilder wide
or narrow comparator equivalence, or settle general metadata/sort policy.

The original app's MDictWriterCustomSort class is extracted from its frozen AST
and executed with the real mdict-utils 1.3.14 writer. Worker results use files;
stdout and stderr are captured as logs, not used for a JSON IPC stream.

For each output, complete ordered key/payload lists must match the source
oracle, including duplicate association and exact body newlines. Rust reads its
own output with explicit Verify, Python independently reads both writers, and
Rust reads the Python output with explicit Verify. The independent v2 auditor
also checks every fresh Rust output. Title and Description must preserve supplied
Unicode text and XML-special characters in both writers. Full observed attribute
maps are retained; other fields are not silently declared equivalent.

Outputs are staged and fully checksum-validated before Rust publishes its case
directory. This does not prove production cancellation, hard memory limits or
all import paths. The new adapter is bounded and uses an in-memory writer. Rust
source is uncompiled in the authoring environment and must run on the user's Mac.

Success is fresh_source_pack_subset_passed_M1_open. It closes only this fresh
packing subset, leaving Rust converter/XLSX parity, broader source encodings,
general stylesheet/metadata serialization and the remaining M1 gates open.

## Received result

The user's Mac report passed all 14 MDX and two MDD cases. Ordered records,
duplicate association, body newlines and resource bytes matched exactly in both
reader directions, with independent audits and unchanged input hashes. Evidence
and hash-matched source snapshots are retained in docs/evidence/fresh-pack-user-run.

This is not full header parity. Every fresh Rust MDX reports StripKey="No";
the original writer reports Stripkey="Yes" and additionally emits Format="Html",
Compact, Compat, StyleSheet and other defaults. The batch intentionally compares
only Title and Description. Native lookup compatibility cannot be inferred from
these physical-row comparisons. General metadata and lookup/sort policy is the
next engine gate; Rust XLSX conversion remains separately open.
