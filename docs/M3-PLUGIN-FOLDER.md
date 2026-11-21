# Explicit plugin folder discovery

This adds a user-selected folder scan to the previously accepted selected-file
inspection. It never scans or imports plugins at startup. Choose Python and a
folder, confirm the separate folder trust checkbox for the entire folder/imports, click Inspect folder, and
choose a NEW result folder. Collect the job receipt in Jobs to populate the
folder converter selector and per-file errors.

## Contract

- At most 256 top-level directory entries and 16 candidate .py files. Scan is
  nonrecursive; names starting with __ and non-.py entries are ignored. These
  caps are checked before ANY candidate is imported. Symlinked selected folders
  are refused. Candidate symlinks/directories are reported as file errors,
  without executing them as selected roots. Importing trusted Python can still
  import other files/dependencies; this is not an import-security boundary.
- Candidate filenames require UTF-8, <=256 bytes, no slash/backslash. Each root
  plugin is snapshotted under the existing 1 MiB cap before any imports start.
  Each file then uses a fresh process, compatible base class, authenticated
  socket, separate raw logs and the existing catalog validation. No constructor
  or conversion runs during inspection. Python itself remains user-supplied.
- The original filename and sibling import directory are preserved. Only the
  selected root files are snapshotted; external dependencies/interpreter are
  not bound. Trusted imports can write files with the user's permissions.
  A later conversion binds the selected root hash and refuses changed bytes.
- A converter's stable identity is the JSON pair [filename, class_name], within
  this selected folder. Repeated class/display names in different files remain
  separate choices; no display-name or declared-id overwrite occurs. Arbitrary
  plugin-declared IDs are not used as global identities in this profile.
- Import or metadata failures are reported per file while other files continue.
  A completed discovery job can succeed with file errors or no converters;
  the receipt/UI lists those errors. Success means the inventory was published,
  not that every plugin loaded. No converter is run automatically.
- The folder catalog is capped at 128 KiB, in addition to each file's existing
  16-class/32 KiB catalog cap and the existing workspace/path/log limits. An
  aggregate overflow refuses the entire publication; results are not truncated.
- One cooperative 300-second budget spans snapshots and inspections; remaining
  time is passed into each subprocess poll loop. Cancellation stops the active
  child/process group and prevents outer publication. Existing outputs are never
  replaced. These are polled logical bounds, not OS-enforced resource limits.
- Result catalog.json contains per-file names, original paths, root hashes,
  validated catalogs or errors. Successful per-file logs are under file-NNN
  directories, where NNN is that file's zero-based position in entries. Failed
  child stages are removed; their bounded error text is retained in catalog.json.
- Selecting a converter fills the actual plugin path/class, loads supported
  option defaults and clears trust. Existing generated controls and JSON fallback
  are reused. Folder inventories and trust are not stored in presets.

## Verification

Rust tests cover namespaced duplicates, import errors, frozen root bytes even
when a trusted peer import changes an original file, fresh-process isolation,
preflight caps, symlinks, cancellation, no-clobber and a short subprocess deadline.
Adapter tests cover admission/trust, receipt transfer and partial inventory.
Node tests validate identities, path containment, error/catalog consistency and
per-field/aggregate limits. Local Python wrapper checks do not substitute for
executing the new Rust folder coordinator on the Mac.

Close the running app and merge the update while preserving existing caches:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_plugin_folder.py --output m3-shell-out-plugin-folder
```

Send m3-shell-out-plugin-folder/report.json first. The focused gate stays offline
and locked after exact known seed normalization; it runs runtime/adapter tests,
Python wrapper tests, frontend tests/build and desktop compilation. No dependency
upgrade, native run in the authoring environment or GUI acceptance is claimed.

After report review, launch the updated development app. The supplied folder
m3/fixtures/plugin-folder has four candidate files: two CopyPlugin classes with
the same display name, OptionsPlugin with prefix/uppercase controls, and broken.py
with an intentional import error. Expect all three usable converters to remain
selectable and the broken.py error to be visible. Select options.py/OptionsPlugin,
set prefix to 字 مرحبا and uppercase on, then use m3/fixtures/build-source.txt as
input and a NEW conversion destination. Confirm trust again. The expected output
is the same exact six-record options fixture shape as the selected-file check.
Do not treat the intentional broken.py message as an application failure.

Native and GUI qualification of this folder slice are pending. Earlier selected-
file and local Mac preview decisions remain accepted for their recorded sources.
The existing standalone preview does not contain these new folder controls.
This slice does not implement Morphology, arbitrary schema types, a sandbox,
recursive/package discovery, production release or other-platform qualification.

## Native gate accepted

The package-188 user Mac report passes all twelve stages: 93 runtime, 28 adapter,
11 Python wrapper/fixture and 47 frontend tests; Svelte has zero errors/warnings,
Vite builds and desktop compilation passes. Delivered source identities, 324
protected M2 identities and seven final lock hashes match. Exact additional Mac
files match previously reviewed platform bindings. See
evidence/m3-plugin-folder-qualified/report.json and review.json. No native code
changed while recording this result. Folder-selection/error-display GUI checks
remain pending. Use the current development app; no new download is needed for
that GUI check, and the old standalone preview still predates these controls.


## Current standalone GUI check (preview v5)

The current v5 standalone app contains the Advanced folder controls. The earlier wording about an outdated preview/development-only controls describes the original native gate stage. Native folder discovery is already qualified; do not rerun that gate.

Use the current Finder-launched app with the external Python interpreter already selected. Open Converters → Convert with a plugin → Advanced: presets, folders and manual settings → Discover plugins in a folder. Choose the actual folder:

`/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/plugin-folder`

Check the folder trust box and click Inspect folder. In the save dialog use a NEW destination name, such as `plugin-folder-inspection-standalone-1` in Downloads. Do not create that folder first and do not select a previous result folder. The existing destination is never replaced.

In Jobs, collect the folder-inspection receipt. The app should return to the plugin screen. The folder list should contain four candidate files and three usable converter choices: `copy_a.py · CopyPlugin`, `copy_b.py · CopyPlugin`, and `options.py · OptionsPlugin`. Both CopyPlugin entries must remain separate. `broken.py` has an intentional import error; its per-file message must be visible without hiding the usable entries. Ignored entries such as Python caches may vary.

Send a screenshot of the discovered converter list and the broken.py message, or the collected inspection receipt. No additional conversion is required: single-file options conversion is already accepted from the standalone app. This check specifically qualifies the exposed folder selector/error-display behavior.

## Standalone GUI accepted — 20 November 2026

The user supplied the folder results and the open dropdown from preview v5. Four candidate files and three usable choices are visible: copy_a.py/CopyPlugin, copy_b.py/CopyPlugin and options.py/OptionsPlugin. Repeated display names remain separate, the intentional broken.py failure is visible, and trust is unchecked after inspection. See evidence/m3-plugin-folder-qualified/GUI-confirmation.json. This closes the inventory/selection-list/error-display check; it does not claim a new conversion from the folder selector. The standalone selected-file options conversion has separate accepted exact-output evidence. No routine rebuild or native gate repeat is required. Earlier pending statements above describe historical stages.
