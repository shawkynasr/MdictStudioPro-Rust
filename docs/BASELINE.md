# M0 baseline: observed behavior

Source: uploaded MdictStudioPro-main.zip, archive commit
`6e181e22193472518d7966b66bac4dc2f2b32f83`.
`baseline/source-manifest.json` records the ZIP SHA-256, exact hashes of the
selected unmodified source files, and an inventory with hashes of all assets.
The legacy source retains its original AGPL-3.0 license.

## Feature inventory

| Feature | Actual Python path | Status / contract |
|---|---|---|
| MDX pack | `PythonPackWorker`, `pack_mdx_txt`, custom writer | In-process library; CLI function fallback when custom writer imports fail |
| MDD pack | Recursive file scan, custom writer | Keys start with backslash; output defaults to resource directory + `.mdd` |
| Metadata | Pack title and description-file controls | MDX description read with selected encoding, MDD description with UTF-8 |
| Sorting | `MDictWriterCustomSort` | Two fold modes; locale.strxfrm; MDX strips ASCII punctuation/spaces, MDD does not |
| Extraction | `run_unpack` → mdict `-x` | Destination input filename + `_unpacked`; optional encoding override |
| Converters | Six classes inheriting BaseConverterPlugin | Actual original converter code executed in M0 |
| Plugin discovery | Documents/Mdict Studio Pro/plugins | Copies defaults only if user directory is empty; executes imports in process |
| Plugin IDs | `id or name` | All bundled IDs are None; duplicate IDs overwrite in dictionary |
| Plugin options | Base declaration only | options_schema not rendered or passed to convert |
| Database | `--txt-db` button | Only a single action wired; no local schema implementation |
| Morphology | Two file selectors | No execution; addflex.py and wordforms.txt absent |
| Query | mdict `-q` | Output to log; no rendered view |
| Metadata inspect | mdict `-m` | Captured textual CLI output |
| Style export | Parse metadata output | Synchronous UI operation; writes `<stem>_style.txt` |
| Workers | Three QThread implementations | Tabs disabled while processing; no cancellation |
| Logs | Signals or captured stdout | mdict runner temporarily modifies process-global sys.argv/stdout |
| Persistence | No settings store found | Output path rules in GUI methods |
| Packaging | PyInstaller + CI | Windows x64, Linux x64, macOS arm64; Intel Mac described as local build |
| Localization | README translations | No GUI localization framework |

## Converter behavior captured

| Converter | Synthetic output records |
|---|---:|
| CC-CEDICT | 7: repeated 和 retained; simplified and traditional copies |
| MOE Revised | 4: two main entries, two distinct aliases |
| WFG Revised | 2 |
| MOE Concise | 2 |
| MOE Idioms | 2 |
| MOE Mini | 2 |

The shared synthetic workbook deliberately exercises image markers, blank
headwords, polyphonic rows, aliases, pronunciation and definitions. It is not
a substitute for official complete datasets. The idiom builder uses the first
row of a grouped headword, unlike converters that iterate all rows.

Nine expected artifacts contain six exact output texts, plugin/error metadata,
Excel normalization, and four sorting orders. Progress final value is captured;
elapsed-time messages and temporary paths are excluded from golden comparison.

## Reproducibility and limitations

- `run.py` starts a child with PYTHONHASHSEED=0. Legacy sets otherwise make some
  alias/synonym order unstable. This is not proof of cross-seed determinism.
- Sort capture sets LC_COLLATE=C. It executes the original class AST and stubs
  writer transport types. It does not exercise binary packing or prove ordering
  on a user's locale. The class constructor is intentionally bypassed.
- Normalization captures None, booleans, integral and fractional floats,
  whitespace, leading-zero strings, and an actual generated workbook.
- Raw Python codec round trips cover UTF-8, UTF-16LE, Big5, GBK, GB18030 for a
  small Chinese sample. They do not prove Rust codec or engine support.
- Empty, missing and invalid input checks cover representative failures.
- GUI startup, actual mdict-utils writing, extraction, DB and query execution
  were not run: PyQt6 and mdict-utils are absent.

## Preserve versus fix

| Finding | Baseline policy | Migration action |
|---|---|---|
| Mini clean_text discards image replacement | Captured by regression assertion | Fix explicitly in Rust and document output change |
| Set iteration affects output order | Fixed seed for oracle | Define stable order in Rust |
| All plugin IDs fall back to names | Recorded | Assign stable IDs and reject collisions |
| CSS/JS resources are external | Asset manifest recorded | Build explicit bundles, resolve missing jybcb.js |
| Locale affects sorting | C-locale fixture only | Decide/document cross-platform policy; reader tests required |
| Writer depends on mdict-utils private APIs | Snapshot only | Engine adapter must avoid relying on GUI or private legacy internals |

The baseline is a migration oracle, not an endorsement of every legacy defect.
