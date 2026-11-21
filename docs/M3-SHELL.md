Numeric stylesheet export is available from verified reader metadata; see `M3-STYLESHEET-EXPORT.md` for current v16 checks.

Current additive routes also include metadata edited copies, indexed redirects, and the optional trusted Python converter bridge. See `M3-METADATA-GUI.md`, `M3-REDIRECTS.md`, and `M3-PYTHON-PLUGINS.md` for current scope and checks.

# M3 shell and native command/job adapter

Version 127: Extract now has automatic TXT/JSONL suffixes, parent/new-folder
controls for MDD, and an explicit larger MDX export route using the existing
M3 export-only streaming profile (v128 routing correction). See
`M3-EXTRACT-GUI.md` for current native checks.

Version 126 continuation: MDD now accepts a resource folder directly. See
`M3-FOLDER-MDD.md` for the current check command and native test procedure.

Current continuation (2026-11-12): Build now accepts dictionary TXT directly.
See `M3-TXT-BUILD.md` for the current native check and fixture procedure.
The first-shell testing history below is retained as historical evidence.

Authored 2026-11-09. **The prior shell compiled and launched on the user’s Mac;
the version-122 preview changes need a fresh native check.** This is an
additive development slice, not a qualified desktop release or M3 completion.
The 324 accepted M2 source identities and all historical locks/evidence remain
unchanged. The approved Studio concept supplies the visual direction; the shell
uses real Rust calls rather than the browser mockup's simulated progress.

## Included

- `m3/native-adapter`: GUI-independent bounded JSON command boundary over the
  accepted `studio-cc-pack-runtime`. One runtime coordinates readers, conversion,
  publication, index creation and extraction under the existing reservations.
- `m3/desktop`: Svelte 5 / TypeScript / Vite front end and Tauri 2 native host.
  Sidebar navigation, native input/output dialogs, standard native Edit menu,
  macOS overlay titlebar with real traffic lights, English/Chinese/Arabic and RTL,
  system/light/dark preference, job cancellation, receipt collection and dismissal.
- Explicit packing profiles: bounded generic JSONL packing and the exclusive
  block-spooled MDX packing profile. No automatic cap widening or fallback.
- All six converter routes: CC → `cc`; Concise → `concise`; Mini/Idioms →
  `small_moe`; Revised/WFG → `grouped_moe`. Output is canonical TXT.
- MDX TXT/JSONL exports, MDD manifest packing and MDD directory extraction.
- Index jobs and persistent indexed MDX sessions, duplicate-preserving paged
  lookup (32 rows/page), escaped source display and an isolated static rendered
  preview with optional indexed MDD resources. See `M3-PREVIEW.md` for scope and
  the current native qualification procedure. No dictionary HTML enters the app DOM.
- Close/quit prevents immediate exit, requests cancellation, closes readers and
  joins native workers off the UI thread. A cleanup error stays visible rather
  than declaring success or silently forcing exit.

## Important input distinctions

MDX Build defaults to UTF-8 dictionary TXT, prepared and packed as one job.
More options exposes the newline profile and advanced JSONL input. In that
advanced format each line has `key` and `text` and ends with LF. MDD packing uses `key` and a relative `file` under the selected
resource folder. See `m3/fixtures/entries.jsonl` for a small synthetic MDX input.
Converter output is canonical TXT and can now be selected directly in Build
with the Standard newline profile. Select JSONL explicitly only for JSONL sources.

An indexed reader requires the exact original MDX plus its matching generated
index artifact and policy. Index creation is a separate background publication
job. It never replaces an existing index; choose a fresh destination.
All output publication retains native no-clobber behavior. For extraction choose
the *name of a new directory*, not a directory that already exists.

## Run on the Mac

Merge this update into the existing `mdict-studio-m0-m1` folder. Keep `.venv`,
`vendor`, real dictionaries, source workbooks and prior outputs.

Prerequisites: the existing Rust toolchain, Apple Command Line Tools, and
Node.js 22.12+ with npm. Tauri's documented macOS prerequisites apply:
https://v2.tauri.app/start/prerequisites/

If the verified revision-6 vendor tree is already present, leave it in place.
Only if absent, use the existing preparation flow:

```sh
cargo fetch --locked
python3 scripts/prepare_sort_experiment.py --revision 6 --reuse
```

From the workspace root:

```sh
python3 scripts/m3_shell.py --install --output m3-shell-out
```

The runner first inspects the adapter without fetching dependencies and checks
its isolated seed lock. With `--install` it then fetches missing Cargo archives,
allowing only that new adapter lock to resolve its seed edges, and refuses new
registry versions/checksums outside accepted M2 plus the qualified SQLite
additions before compilation (see `M4-DATABASE-GUI.md`).
Full offline metadata may normalize the isolated adapter seed lock (including
when merging an update restored that seed). The normalized graph is checked
again against accepted registry versions/checksums before the adapter Rust tests
use `--locked --offline`. Qualified M1/M2 locks are never normalized or rewritten.
Without `--install`, all adapter archives must already be cached.
It runs npm installation (`npm ci`
if a frontend lock exists), Svelte/TypeScript checking, Vite build, Tauri environment
inspection and desktop `cargo check`. Its report always distinguishes compilation
from launching a native window. Subsequent reproductions use the resulting locks.
New frontend/Tauri dependency locks must be returned with the first native receipt;
they cannot be fully generated in the authoring environment (npm HTTP 403, no Rust).
Existing qualified locks are never rewritten. Desktop dependencies are isolated;
the Tauri crate is pinned to 2.12.1, while its plugins/build tools and JS packages
are resolved and locked on the first native run. They are not yet qualified.

On success launch:

```sh
cd m3/desktop
npm run tauri dev
```

On failure, send `m3-shell-out/m3-shell-report.json`; it includes step logs.
For a repeat use `m3-shell-out-v2` (existing reports are never overwritten).
There is no need to rerun old M1/M2 reader batches.

If a first-run report says an archive (for example `arbitrary v1.5.0`) could not
be downloaded because `--offline` was specified, use the updated runner with
`--install` and a new report output name. Version 115 attempted full offline
metadata before bootstrapping the crate cache; this is corrected in version 116.
An adapter-stage failure stops before npm installation, so `tauri: command not
found` afterward does not mean that Tauri must be installed globally. Run the
development launch only after the full runner succeeds.

The second Mac attempt compiled the adapter and passed the publication,
failed-reader cleanup and indexed duplicate/admission tests (3/4 tests). Its
boundary test correctly caught `poll` accepting an unknown top-level field.
Version 117 changes the no-payload `Poll` and `Capabilities` command variants
from unit variants to empty struct variants, so they participate in strict
unknown-field decoding. The JSON wire contract is unchanged. The test now
checks both commands with unexpected fields and confirms their valid forms
still work. Native rerun of this correction and frontend compilation remain
pending; the other three successes do not constitute complete M3 qualification.

The third Mac report passes all four adapter tests, npm installation,
Svelte/TypeScript checking, Vite build and Tauri environment inspection.
Desktop compilation then identified three host-layer errors. Version 118 adds
the required RGBA PNG context icon, emits shutdown errors as a cloneable JSON
payload instead of the non-Clone backend error, and passes `app.handle()` to
`Menu::default`. No adapter or qualified backend behavior changes in this fix.
Desktop compilation and launch are still pending. Existing Node modules and
Cargo build caches can be kept for the next run.

The fourth report stopped before compilation because the merged archive restored
the adapter seed lock and `--locked` prevented normalization during the cached
retry. Version 119 permits offline normalization of this new M3 lock, rechecks
registry identities afterward, and keeps the actual tests locked and offline.
Both fresh-install and cached-retry orchestration have regression coverage. No
dependency reinstall or old M1/M2 native test rerun is needed for this correction.

## New native checks

Four authored Rust tests cover invalid/oversized requests and unknown profiles,
real duplicate-aware MDX publication, one-transfer receipts, overwrite refusal,
late cancellation, failed-reader disposal, indexed duplicate pagination and
shared reader/exclusive-packer contention. They are **not claimed to have run**
in the authoring environment. Python structure checks are not substitutes.

After the native window opens:

1. Build `m3/fixtures/entries.jsonl` to a new MDX; watch Jobs, collect its receipt
   and dismiss it. Retry to the same path and verify typed overwrite refusal.
2. In Tools select the new MDX, choose a new index filename with `+`, build it,
   then open the exact pair. Query `字` and confirm both definitions are separate.
   Close the reader and confirm active operations return to zero.
3. Convert `m3/fixtures/cedict.txt` to a new TXT. Verify its path and receipt.
4. Check Arabic RTL, Chinese input composition, native Copy/Paste, theme changes,
   and window dragging. Test cancellation with a larger already-qualified input.
5. Close while work is active; ensure cleanup finishes and the app exits without
   leaving a visible partial destination. Do not force-quit to simulate success.

## Command contract and limits

One `studio_call` invocation accepts a JSON **string** with an `action` tag.
The Rust adapter checks a 64 KiB byte ceiling before nested decoding. This does
not prevent Tauri itself allocating the initial IPC string and is not an OS
memory limit. Native request validation and all original profile caps still apply.
No extra worker pool is created; command dispatch uses Tauri's blocking executor.
Only short enqueue/snapshot/transfer operations hold the adapter mutex.

`poll` returns bounded non-destructive snapshots (at most eight publication jobs
plus the backend-bounded session/job handles), with no dictionary payloads.
The GUI permits one poll in flight at 400 ms intervals. It neither pumps a
per-record event stream into IPC nor creates an unbounded log array. Session
results are collected once and forgotten by that one GUI consumer. Publication
receipts are collected explicitly. Dismissal can discard an uncollected receipt;
it never deletes or changes a committed output file. Reader leases remain held
until native cleanup, then `release_reader` disposes the handle. Source display
is clipped to 65,536 characters; pages remain bounded by native reply caps.

Custom command permission is main-local-webview only, with an AppManifest and
explicit capability. No remote origins, arbitrary shell/HTTP/filesystem plugin,
global Tauri object or remote preview permissions are enabled. The dictionary
frame is opaque and script-disabled; see `M3-PREVIEW.md`. The trusted app UI
can request the user's local input/output paths; this is not per-file sandboxing.
Do not add untrusted content to that main app DOM or broaden capabilities.

Metadata rebuilds and Python jobs share the coordinated publication worker; indexed redirects use the managed reader actor. Full original GUI parity, hard memory protection,
crash recovery and production packaging/signing remain open. macOS native tests
do not qualify Windows or Linux. MDX v3 remains on the later roadmap.
