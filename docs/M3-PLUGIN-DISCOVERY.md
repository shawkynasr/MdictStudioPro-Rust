# Selected-file plugin discovery and scalar forms

This additive slice inspects a selected .py file, lists up to 16 concrete local
BaseConverterPlugin classes, and renders supported class-level options_schema
fields. It does not scan arbitrary folders on startup, instantiate classes,
execute convert during inspection, or promise arbitrary legacy schema support.
The original base declared options_schema as an empty future extension; no
nonempty schema contract was present to reproduce. Manual class/JSON entry and
existing presets remain supported.

Inspection imports trusted code, including its imports and class bodies. It is
not a security sandbox. The existing authenticated socket, separate raw logs,
cancellation, process-group cleanup, polling limits and serial publication lane
are reused. Choose a fresh inspection result folder. On success it contains
catalog.json and bridge logs. Collecting the job receipt loads the catalog into
the plugin page only if the interpreter/file selection still matches. No
dictionary input or conversion result folder is needed for inspection.

## Supported schema: scalar-fields-v1

options_schema is a list of at most 16 dictionaries. Each requires key, type,
default and optionally label. Keys are unique ASCII identifiers up to 64 bytes.
Types are string, boolean, number and choice. Choice additionally requires 1..16
unique string choices and a default among them. Unknown fields or incompatible
defaults cause a per-class fallback to manual JSON; they are not silently
discarded to generate an incomplete form. Metadata comes from the class, not
from a constructed instance. Imported and abstract classes are excluded.

```python
options_schema = [
    {"key": "prefix", "type": "string", "label": "Prefix", "default": "Custom"},
    {"key": "uppercase", "type": "boolean", "default": False},
    {"key": "count", "type": "number", "default": 2},
    {"key": "mode", "type": "choice", "default": "a", "choices": ["a", "b"]},
]
```

Labels <=256 UTF-8 bytes, descriptions <=512, default strings <=2048, finite
numbers within +/-9007199254740991. Catalog <=32 KiB; defaults and submitted
options retain the existing <=64 scalar fields and 8 KiB compact JSON limits.
No dependency is added. Rust and frontend validate the returned catalog, in
addition to child validation. Unsupported schemas do not prevent manual use.

Selecting a discovered class explicitly replaces current JSON options with its
defaults. Form edits update that same JSON, preserving unrelated scalar keys.
Invalid/mismatched JSON stays visible and requires correction or an explicit
defaults reset before the form is usable. Trust clears on inspection, class,
options or path changes; conversion still requires confirmation. Catalogs and
their hashes are not persisted with presets. A new inspection is needed after
loading a preset to regain generated forms.

The native snapshot hash is attached to inspected conversions. If the selected
.py bytes changed, conversion refuses before importing it. This binds only the
selected file, not the external interpreter or sibling dependencies. Python
plugins still have the user's account permissions and external dependencies.

## Native gate

Close the preview/development app, merge this update and keep existing caches.
From the project root:

```sh
.venv/bin/python scripts/m3_plugin_discovery.py --output m3-shell-out-plugin-discovery
```

Send m3-shell-out-plugin-discovery/report.json first. This focused gate runs
wrapper, runtime, adapter, frontend tests/build and desktop compilation offline
with exact reviewed locks. It does not repeat the completed M4 closeout or all
independent reader runs, install dependencies or launch an app. Native checks
are pending the user's Mac; local Python/Node tests are not a Rust/Svelte claim.

After report review, launch the updated development app (the already-built
standalone preview contains the previous code). In Python converter:

1. Python executable: project .venv/bin/python. Plugin: m3/fixtures/noisy_plugin.py.
2. Confirm trust and click Inspect plugin. Choose a NEW folder, e.g.
   Downloads/plugin-inspection-demo. In Jobs, collect the successful receipt.
3. Select OptionsPlugin from discovered classes. Prefix and Uppercase source
   controls appear. Set prefix to 字 مرحبا and Uppercase source on.
4. Input: m3/fixtures/build-source.txt. Choose an output parent and NEW result
   folder. Confirm trust again and run. output.txt should have six records,
   including plugin-options with the exact prefix and uppercase APPLE.

Do not rebuild the standalone app before native validation. The prior local
Mac preview checkpoint stays accepted for its original source/binary identity.
Full M3, folder-wide discovery, arbitrary options schemas and production release
remain separate qualification decisions.

## First native attempt

The Mac runtime/adapter and all 43 frontend logic tests passed. Svelte check
stopped on one TypeScript choice-default narrowing error, with zero warnings.
An explicit string guard now precedes choices.includes. Desktop compilation and
GUI validation were not reached; original failed report is retained under
evidence/m3-plugin-discovery-first-attempt. Retry with a fresh output directory
m3-shell-out-plugin-discovery-v2 after merging the corrected update.

## Corrected native gate accepted

The package-184 Mac report passes all eleven stages: 86 runtime, 27 adapter,
9 Python wrapper and 43 frontend tests, Svelte check/Vite build and locked offline
desktop compilation. All delivered source identities, 324 protected identities
and seven reviewed lock hashes match. The two extra Mac files match their exact
previously reviewed platform bindings. See evidence/m3-plugin-discovery-qualified.
GUI class selection, generated forms and conversion still require user checks.
No new project update or standalone app rebuild is needed for those checks;
launch the updated development app from the current project.

## GUI checkpoint accepted

The user supplied the discovered OptionsPlugin selector and generated Prefix /
Uppercase source controls. This screenshot shows defaults, not the earlier run
values. The separately uploaded output is exactly the expected six-record
conversion with prefix 字 مرحبا and uppercase source; all four input/plugin/options/
output hashes agree with the pasted native receipt. Both duplicate definitions
and the empty record are preserved. See the scoped GUI-confirmation.json under
evidence/m3-plugin-discovery-qualified. Numeric/choice controls and schema fallback
have automated coverage only. This selected-file slice is complete; folder-wide
discovery, arbitrary schema compatibility and full M3 remain separate.
