# One-file plugin workflow

User feedback: the original plugin screen exposed too many paths, class names,
presets, inspection folders and manual receipt steps. The user asked to choose
or drag one file instead. This change makes that the main path; folder discovery
and manual controls remain under Advanced. It does not declare the earlier
folder GUI qualification complete: that check was interrupted by the usability
feedback, and the previous five-record NoisyPlugin output was not the requested
folder-options conversion.

## Main flow

1. Choose or drop one .py plugin file. This selects a path only; it never imports
   code automatically. Other single-file drops select dictionary input. Multiple
   drops are rejected. Native drag handling is active only on the plugin page;
   the file picker remains available if drag events cannot be registered.
2. On first use, choose Python under the setup disclosure. Only its bounded path
   is remembered in this app's local storage. Trust, data paths and output are
   never saved by this preference. No interpreter or dependency is installed.
3. Confirm trust and click Import plugin. The existing isolated, bounded Python
   inspection runs in app-owned temporary storage; no inspection result folder
   is requested. The current page collects the response automatically. One
   converter is selected automatically; multiple classes require an explicit
   choice. There is no implicit NoisyPlugin default.
4. Supported settings appear as controls. Choose/drop input, then choose a new
   result folder with one Save dialog. A timestamped name is suggested; manual
   parent/name fields are under Advanced. Native no-clobber behavior is unchanged.
5. Confirm conversion trust and run. Existing background Jobs and result files
   remain available. No folder scan, raw JSON or receipt collection is required
   for the normal import flow.

Choosing a new plugin clears the previous class, options, source binding and
output destination. Interpreter/plugin changes invalidate and cancel a pending
import. A generation counter is checked again after async receipt transfer, so
an older response cannot select a converter after A → B → A changes. Late/stale
successful jobs are drained and forgotten. Successful temporary import jobs are
also forgotten automatically; failed ones remain in Jobs for diagnostics.

The new python_probe request has no user destination. Its native implementation
reuses existing inspection with an app-owned temporary parent and returns only
the validated catalog/profile/root hash. Temporary results are removed when the
job returns. Trust, cancellation, process isolation, source caps and hash-bound
conversion remain enforced. This is trusted code execution, not a sandbox.

## Advanced and compatibility

Presets, selected-folder discovery, raw class/path editing, JSON options and
diagnostic inspection reports remain available under Advanced. Existing preset
format and trust clearing remain. Folder discovery is not removed or promoted
to an automatic startup import. Built-in native converters are unchanged.
The separate standalone preview remains older than these controls.

Native file-drop registration uses the existing Tauri API and capabilities;
no filesystem/shell/network permission is added:
https://v2.tauri.app/reference/javascript/api/namespacewebview/#ondragdropevent

## Verification

Node checks cover single/multiple drops, zero/one/multiple converter selection,
schema defaults, response bounds, stale-generation matching, output path mapping
and interpreter preference bounds. Native tests cover the transient no-output
request, source-bound catalog, trust refusal, cancellation and one-time receipt
transfer. Local Node/Python execution is not a Rust, Svelte or native-drag claim.

Close the running app, merge the update, preserve existing caches, then run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_plugin_simple.py --output m3-shell-out-plugin-simple
```

Send m3-shell-out-plugin-simple/report.json first. After review, test the file
picker and a single native file drop with m3/fixtures/plugin-folder/options.py.
It contains one converter and should select itself after Import plugin. Set
prefix 字 مرحبا, enable uppercase, select m3/fixtures/build-source.txt and a new
result folder, confirm conversion trust and run. Expect six records and two
options. Verify the remembered Python path after quit/reopen; trust must remain
unchecked. No old folder-inspection test needs repeating for this UI check.

Mac native compilation and GUI acceptance are pending. Full M3 and production
release remain open; this delivers the requested usability correction.

## Native gate accepted

The package-190 Mac report passes all twelve stages: 94 runtime, 29 adapter,
11 Python wrapper/fixture and 51 frontend tests, Svelte check with zero
errors/warnings, Vite build and desktop compilation. All delivered source
identities, 324 protected identities and seven final lock hashes match. Exact
additional Mac files match the previously reviewed platform bindings. See
evidence/m3-plugin-simple-qualified. GUI, native file drop and interpreter
preference restart checks remain pending; no new download is needed to try the
current development app. This evidence-only update changes no native code.

## GUI follow-up, 2026-11-20

Accepted scoped one-file GUI workflow: the supplied output matches the six-record oracle exactly; the user confirmed picker selection, Finder drag without execution followed by trusted import, and Python setup persistence after quit/reopen with trust reset. Evidence: `docs/evidence/m3-plugin-simple-qualified/GUI-confirmation.json`. No bundled Python or full M3 completion claim. Historical pending labels above describe the earlier implementation/native-gate stage.
