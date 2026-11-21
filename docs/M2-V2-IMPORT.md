# Ordinary v2 import and lookup: first qualification slice

Accepted 2026-11-01: Rust tests and the bounded process matrix passed on macOS.
This starts remaining M2 area 1. It does not complete M2 or add v1/v3 support.

The fifth report completes all 26 cases: 15 successful imports/comparisons and
11 expected import refusals. Fourteen MDX cases each check 19 lookups and 11
redirect requests: 328 exact results and 92 expected query errors (420 total).
The MDD case checks four resources, including a duplicate key and an empty
resource, and four exact queries. Both UTF-8/UTF-16 case/strip matrices, raw
metadata, physical rows, independent wire audits and checksum refusals passed.
All 11 source/lock hashes and 103 previously protected identities match, and
all 61 package identities and the returned lock bytes match the local snapshot.

The unchanged report and source snapshots are retained under
`docs/evidence/m2-v2-import-user-run`. Successful logs, generated dictionaries,
individual actual JSON and wire-audit output were not separately attached;
these results are assertions completed by the fingerprinted runner, not a new
independent execution here. No native rendering or real-corpus claim is added.
Application/background import routing subsequently passed; see
`M2-IMPORT-JOBS.md` and `docs/evidence/m2-import-jobs-user-run`. No rerun is
requested for this accepted batch. Earlier failures below remain historical.

First Mac result: compilation passed and five of six integration tests passed.
The remaining MDD test exposed an incorrect shared XML root guard: MDD headers
use `Library_Data`, while MDX uses `Dictionary`. The guard now selects the root
by file kind and retains rejection of wrong roots, nested content and duplicate
aliases. Regression coverage includes empty and paired root forms for both types.
The legacy-writer process matrix did not run in that failed attempt.

The original report and all eleven matching source/lock snapshots are retained
under `docs/evidence/m2-v2-import-first-user-run`. Cargo's returned lock was
recovered byte-for-byte; its change from the seed was generated comments/blank
framing, with all 61 package identities unchanged. Earlier qualified sources and
locks remain unchanged. The corrected Rust test command passed in later runs.

The second report fingerprints the corrected sources, but its log still reports
the obsolete Dictionary-only diagnostic and zero library tests, omitting the new
root regression test. Reused Cargo artifacts after timestamp-preserving ZIP
replacement are inferred from this mismatch. The runner now cleans only the
`studio-v2-import` package artifacts offline before compiling. Dependency caches,
other workspaces, `.venv`, `vendor` and prior output directories are retained.
The unchanged second report and eleven source snapshots are retained under
`docs/evidence/m2-v2-import-second-user-run`. The full process matrix remains
unreached in that attempt.

The third report confirms both the targeted refresh and corrected Rust test
command passed. Python then failed with `IndexError` during fixture generation,
before any CLI comparison. Its unchanged report and matching source snapshots
are retained under `docs/evidence/m2-v2-import-third-user-run`.
The likely cause is the legacy Python stylesheet parser: it splits literal
newlines into triplets but does not decode ET's numeric newline references.
The runner now reads physical rows from each original writer output, then
asserts that header-only mutations preserve all binary key/record section bytes.
Numeric stylesheet references still reach Rust and retain independent XML/raw
header checks. This does not qualify those mutated headers in the legacy Python
reader or establish rendered stylesheet behavior. Python exceptions now include
a traceback; fixture generation and individual CLI cases have stage labels.
The fourth report again passes the Rust test command, then fails the base-reader
payload comparison. It is retained with source snapshots under
`docs/evidence/m2-v2-import-fourth-user-run`. The legacy reader strips ASCII
whitespace from decoded key bytes, so `" spaced "` is returned as `"spaced"`.
That explains the likely mismatch; this report did not include the actual rows.
The harness now independently decodes the physical v2 key blocks with stdlib,
checks the Python keys against their explicit byte-trim projection, and keeps
the raw keys in the Rust oracle. Definitions are not trimmed, redirect targets
are not rewritten, and payload mismatches now show missing/extra rows.

The independent decoder also checks every MDD payload, including empty records
at EOF which the legacy record loop can omit. Its comparison permits only those
empty trailing omissions; every nonempty payload, duplicate and remaining
ordinal must agree exactly with Python. This is a narrow fixture oracle for
unencrypted zlib/plain v2, not additional application format support.
The fifth run using this correction passed.

The accepted command was:

```sh
.venv/bin/python scripts/m2_v2_import.py --output m2-v2-import-out-v5
```

Keep `.venv`, prepared v6 `vendor`, real inputs and previous outputs. No pip
update, native-reader run or old batch rerun is requested.

## Deliberately separate import boundary

`m2/v2-import` is an isolated workspace exposing `studio_v2_import::Dictionary`
and `ResourceArchive`. The earlier Studio-only open/export verifiers, core,
application facade, background runner and their locks remain byte-for-byte
unchanged. Failed Studio verification is never retried silently as a foreign
dictionary import. Callers choose this import API explicitly.

The importer uses the existing mdictlib 0.2.8 and v6 patch, and the same pinned
registry identities. Its 61-package seed adds one local importer package to the
accepted 60-package application graph. Cargo may canonicalize path/development
dependency edges in this new workspace only. The first test command runs offline;
the runner verifies registry versions/checksums and returns the complete resulting
lock for review. Subsequent commands use `--locked --offline`. Earlier locks are
protected. Nothing is fetched or upgraded silently.

The frozen casing implementation is compiled from the unchanged qualified core
source, with its existing Unicode16 data. No compiler Unicode casing is substituted.
Public import jobs reuse the application's cancellation token, error-code enum
and serialized progress shape. Domain-specific error `detail` values distinguish
redirect failures and unsupported profiles. Import progress uses the shared
`converting` stage with `snapshot`, `header` and `indexing` phase counters.

This first facade is synchronous. General-import background queue/application
routing is a subsequent subgate of area 1 after this reader passes. Existing
background MDX/MDD operations still reopen only qualified Studio outputs.

## Supported declarations and metadata

- MDX and MDD declaring generated/required version 2.0 (or 2).
- Unencrypted inputs: `Encrypted` absent, empty, `No` or `0`.
- MDX declared UTF-8/UTF8 or UTF-16/UTF-16LE, with HTML/Text format.
- MDD empty, UTF-8/UTF8 or UTF-16/UTF-16LE encoding labels from common writers;
  the typed MDD engine path reads resource keys and payloads stay binary.
- Standard single `Dictionary` XML root for MDX or `Library_Data` root for MDD,
  with no DTD, nested content or ambiguous
  duplicate known header aliases. Known header-name aliases are canonicalized
  case-insensitively; raw XML and UTF-16LE bytes are retained unchanged.

v1, v3, encryption and other encodings are refused before engine decoding. The
engine's optional Rust LZO feature remains enabled, but this batch adds no LZO
compatibility claim; legacy v1/LZO/ISO8859-1 and v3 remain outside scope.

All attributes, descriptions and numeric stylesheet data are exposed without
requiring Studio tags. Definitions and numeric markers stay raw; no HTML/script
is executed or transformed. Preserving a raw header in memory is not general
metadata serialization/rebuild or rendered stylesheet qualification (area 2).

## Lookup is an explicit policy

`Dictionary::open_v2` requires a `LookupPolicy` argument:

| Policy | Behavior |
| --- | --- |
| `RawExact` (`raw-exact-v1`) | All raw-exact matches in physical order; no fallback |
| `HeaderAsciiV1` (`header-ascii-strip-unicode16-v1`) | Raw-exact matches win; otherwise explicit header flags control the versioned fallback |

Header-guided fallback requires explicit `KeyCaseSensitive` and `StripKey` flags;
missing flags are not guessed. Case-insensitive mode applies frozen whole-string
Unicode16 lowercase first. Strip mode then removes ASCII punctuation and ASCII
whitespace (including vertical tab). Full-width/Unicode punctuation is not stripped.
No casefold, NFC, accent folding, wildcard matching or official MDXBuilder collation
is implied. This named application policy is not a claim of universal native-reader
normalization equivalence. Raw-exact import/lookup remains available when flags
are absent. Unknown flag values are refused.

Physical records are fully enumerated without imposing Studio physical sort
order on a foreign file. Duplicate keys retain distinct rows and payload order.
Normalized query results are never used to choose a single duplicate. A query
that becomes empty under fallback returns an explicit error. Results are complete
or fail their count/byte budgets; no partial success is returned.

MDD resource lookup is always raw-exact and preserves duplicates and bytes. Raw
resource names are data, including potentially unsafe filesystem names. This API
does not extract files or turn those names into paths. Safe extraction of such
imports needs an explicit later application route with existing path/collision
controls; the Studio extraction verifier is not weakened.

## Redirect resolution

`lookup` returns unchanged source bodies. `resolve` is a separate opt-in call.
It recognizes a body beginning exactly `@@@LINK=`, with one nonempty target and
at most one terminal LF/CRLF. Target spaces are preserved, not trimmed. Multiline,
empty and NUL targets are refused. All targets use the selected lookup policy.

Resolution follows every duplicate target in physical order, returning source
ordinal, terminal ordinal, terminal entry and the hop chain. A cycle is detected
by physical ordinal on the current branch. A missing target, malformed redirect,
cycle, depth limit, visit limit or result budget fails the entire resolution call,
even if earlier branches found results. Raw lookup is still available for inspection.

Defaults allow 16 redirect hops, 4,096 visits, 256 output results and 2 MiB result
bytes including copied chain strings. At most 64 recursive hops and 65,536 visits
can be configured. Result and visit limits prevent exponential duplicate branching
from producing an unbounded result set.

## Snapshot, integrity and current size envelope

A regular source file is copied through a fixed buffer into a private capped
temporary snapshot, with cancellation checks between chunks. Header preflight
and engine decoding read that same private snapshot, removing a reopen race
between checking one pathname version and decoding another. Concurrent mutation
during the initial copy is not a source-authenticity guarantee; integrity checks
still apply. The input is never written. The snapshot is removed on return/error.

Header UTF-16 and little-endian ADLER32 are checked independently, with a 64 KiB
wire-header ceiling (or smaller configured metadata cap) and at most 256 attributes.
The engine uses explicit Verify; every physical key/body/resource is decoded and
checked before success, including records never queried later.

Current defaults retain 1,000 records, 16 MiB files, 8 MiB decoded rows, 4 KiB keys
and 1 MiB definitions/resources. Owned rows/indexes, raw headers and JSON dumps
add allocations beyond these counters. Engine decompression precedes adapter
byte checks. This is not the production preallocation/index/memory solution in
remaining area 3. Raising caps needs separate implementation and measurement.

## Authored qualification

Six Rust tests cover foreign-tagged fixtures, exact/fallback duplicate behavior,
case/strip flags, redirects, missing/cycle/depth/result errors, cancellation,
unsupported version/encryption/encoding, checksum refusal, raw stylesheet/header
retention, missing flags and binary resource lookup. Studio-only verification is
also checked to remain strict.

The process batch generates ordinary files with the captured original Python
writer, including small multi-block boundaries and both MDX encodings. It checks
all four case/strip combinations, raw-exact mode, missing flags, Unicode examples,
raw styles/scripts, duplicate redirects, result/depth/count budgets, v1/v3/encryption/
legacy-encoding refusals, conflicting header aliases, isolated header/key/record
checksum corruption and duplicate MDD resources. Independent Python physical
body/resource values (read before header mutation, with binary-section identity
asserted), stdlib-decoded raw keys and a separate v2 wire audit are compared with
the imported data. The legacy key-trim and trailing-empty-resource limitations
are checked explicitly as described above. Inputs must
remain unchanged. Expected lookup behavior follows the explicit policy above;
it is not inferred from another reader's fuzzy search behavior.

Seven Python contract tests pass locally, including fixture-oracle routing,
UTF-8/UTF-16 raw keys with surrounding spaces, rejection of unexpected Python
key/count changes, MDD trailing-empty handling, changed/missing resource
refusals, checksum refusal and binary-section preservation. Their writer/reader
inputs are synthetic test doubles, not an execution of the installed legacy
package. The Rust test command and generated legacy-writer matrix passed on
the Mac. This environment has no Rust toolchain or installed mdict-utils.
No real-corpus, GUI, queued-import or universal format
compatibility acceptance is claimed yet.
