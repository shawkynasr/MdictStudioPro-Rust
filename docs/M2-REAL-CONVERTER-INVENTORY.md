# Original converter source selection and size preflight

Authored 2026-11-06. This is a read-only inventory, not converter qualification.
The accepted synthetic converter gate and real dictionary reader gate remain
unchanged. No Rust source, runtime limit, dependency or accepted receipt changes.

The next real converter gate needs original CC-CEDICT text and MOE workbooks.
Place copies of your real `.u8`, `.txt` and `.xlsx` source files in the excluded
`real-converter-inputs/` folder, or select a directory outside this project.
Use uncompressed text sources; automatic archive extraction is not performed.
Then run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m2_real_converter_inventory.py --inputs real-converter-inputs --output m2-real-converters-out
```

Send `m2-real-converters-out/m2-real-converter-inventory.json`. There is no need
to attach the source files or edit the generated selection draft yet. Keep
`.venv`, `vendor`, your private dictionaries and all earlier outputs.

The command reads only the selected directory, with at most 16 supported source
files. Nested source files are permitted, but source symlinks escaping that
directory are refused. The output folder must be new, with a name beginning
`m2-real-converters-out`; this folder and `real-converter-inputs` are excluded
from distributable ZIPs. A missing/empty input directory produces an actionable
failure report; it is not mistaken for completed qualification.

## What the inventory measures

- Source filename, byte size, SHA-256 identity and content stability before/after
  read-only analysis. Files over the native 32 MiB input cap are identified but
  not parsed. Files above the separate 512 MiB inventory hashing cap are recorded
  as metadata-only with no invented content identity.
- CC-CEDICT UTF-8 validity, BOM, observed lines, comments, matching records,
  traditional/simplified extra records, skipped nonempty lines and estimated
  output record count. It detects the current 100,000-entry ceiling without
  generating HTML or running a plugin. Very long lines/line-count limits stop
  analysis explicitly; counters then describe only the observed lower bound.
- XLSX part count, advertised total expansion and maximum part bytes before
  worksheet parsing. Over-limit, duplicate or encrypted ZIP structures stop
  worksheet analysis rather than inflating them under a larger silent limit.
- Up to 16 worksheets, streamed with openpyxl read-only/data-only mode. Declared
  dimensions and observed row coordinates, real cell count and estimated scalar
  byte totals are recorded. The scan stops at the existing row/column/cell/value
  budget. Incomplete scans are explicitly marked; the rest of a workbook is not
  silently treated as converted or qualified.
- Recognized MOE schema columns and possible converter mappings. The inventory
  records only a fixed allowlist of column names, not arbitrary header values,
  definitions, headwords or raw cells. Unsupported scalar kinds are counted
  without storing their contents. Worksheet names and source filenames remain
  visible as selection metadata.

The existing profile is 32 MiB source, 32 MiB decoded conversion, 100,000 entries,
64 MiB TXT output, 32,000 workbook row coordinates, 64 columns, 512,000 cells,
32 MiB decoded scalar values, 128 MiB advertised ZIP expansion and 32 MiB per part.
Preflight estimates do not prove the output fits every limit. In particular,
HTML expansion, MOE aliases, duplicate header normalization, cached formulas and
the converter's full supported-cell validation still need the actual native run.

## Mapping and next decision

`converter-selection-draft.json` lists possible file/worksheet/converter mappings.
Every case starts with `selected: false`. A `字詞名` table can be compatible with
Revised, WFG and Concise layouts; header compatibility alone does not identify
the intended dataset. `成語` suggests Idioms, and `單字` suggests Mini. Original
sources may validly be used for more than one rendering layout after explicit
selection. The tool does not infer this intent from a filename or launch a job.

After reviewing the inventory, select actual sources and converter roles for
the real native/original-Python comparison. If a complete source exceeds the
current profile, define the required scale and implementation change first.
This inventory does not raise caps, sample rows, truncate a dictionary, convert
a compiled dictionary back into a source dataset, or mark an oversized file as
qualified. No conversion or resource reservation is started in this step.

All 214 previously qualified source identities and the 66-package dependency
graph are checked unchanged. Seven local tests cover counts, profile stops,
schema ambiguity, payload omission, ZIP preflight and directory containment.
M2 remains partial: actual real converter qualification, index-build admission,
full fresh-packing real workflows and final backend closeout remain open.
