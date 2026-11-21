# Engine decision: proceed to application implementation

Date: 2026-10-29. Decision: M1 engine qualification is complete within the
boundary documented in M1-CLOSEOUT.md. Select **mdictlib =0.2.8 with the
maintained writer patches and Studio adapter** as the basis for M2. This selects
an implementation dependency, not a production-ready desktop release.

## Evidence supporting the decision

The final user-run report passed all eight consolidated gates on Intel macOS
15.8.2 / Python 3.14.7: evidence integrity, v2/v6 vendor verification, baseline,
Python contracts, and Rust root, legacy-sort and adapter test workspaces.
All eight returned zero. Reported integration source hashes and three lockfile
hashes match the retained qualified inputs. The report remains unchanged with
its original decision-pending fields; this document records the subsequent
review decision. Individual final-run logs were not supplied, so no new Rust
test counts are inferred from the process-level report.

Earlier evidence supplies the broader qualification: fresh pack comparisons,
independent Python interop, exact corpus scans and rebuilds, checksum rejection,
bounded stress and cleanup, and native lookup, corrected stylesheet, MDD resource
and focused Unicode/restart success in the two tested macOS readers. The first
closeout failure and historical format failures remain retained, not relabelled.

## Required architecture choices

- Pin the engine and carry the reproducible patch history. Use revision 6 for
  the versioned adapter; v2 remains legacy-sort qualification evidence.
- Use `unicode16-literal-v1` for the qualified Studio literal policy, frozen
  casing data, stable presort with PreserveInput, explicit header flags and
  raw-exact-first lookup. Unicode17 remains an explicit comparison profile.
- Keep the two legacy C-locale export sort profiles separate. They do not prove
  exact official MDXBuilder equivalence or equivalent native fallback lookup.
- Require explicit Verify and full validation on production import/publication
  paths. Keep policy mismatch refusal; never silently switch casing versions or
  delegate versioned fallback to the library's different built-in locator.
- Preserve duplicate order, payload bytes and resource identity. Keep filesystem
  extraction and dictionary HTML access behind application-owned boundaries.

## Conditions carried into M2

The current integrated adapter caps 1,000 records, 8 MiB decoded rows and 16 MiB
input files. These are probe limits, not product limits. Production indexing,
pre-allocation decompression controls, result budgets and cancellation need
implementation and measurement. Publication needs atomic no-replace semantics;
general resource extraction needs platform collision/link handling.

General XML/stylesheet metadata serialization remains unresolved outside the
qualified fixtures. Do not advertise protected/encrypted formats, v3, arbitrary
legacy encodings/LZO, non-C-locale equivalence or cross-platform reader
compatibility based on this evidence. Unsupported inputs need explicit errors.

M0 remains a partial behavior baseline; closing M1 does not imply full legacy
GUI parity. Rust XLSX/converter ports, Python plugin IPC, the Tauri shell,
Chinese/English/Arabic localization with RTL and isolated dictionary previews
remain application work rather than completed features.

## Next milestone

Build a reusable `studio-core` API around the selected adapter: explicit job and
format types, structured errors, resource budgets and index strategy, shared
import/export/lookup policy, cancellation and staged publication. Port converters
against the captured original outputs and normalize Excel cells deliberately.
Keep the engine behind this boundary before wiring the Tauri UI. Production
checks should be attached to the new paths as they are implemented; the
completed M1 native/corpus batches do not need to be routinely repeated.
