# Python plugin options — scalar-map-v1

The Python converter screen now has an optional JSON editor with English, Chinese
and Arabic labels. It accepts an object with at most 64 fields, ASCII identifier
keys up to 64 bytes, strings up to 2048 UTF-8 bytes, booleans and finite numbers
within ±9007199254740991. The complete options object is bounded to 8 KiB of
compact UTF-8 JSON; the GUI also bounds the entered text. Nested objects, arrays
and null values are refused. Blank input means an empty object.

Nonempty options are assigned to the selected converter instance as self.options
before its existing five-argument convert method runs. Empty options leave the
instance untouched, preserving legacy plugin defaults and signatures. Plugins
choose which keys they support; this first profile does not import plugins for
discovery, interpret options_schema, generate forms, or change their algorithms.
The default receipt remains trusted-python-converter-v1 and adds option_fields
and options_sha256, using Rust's compact key-sorted JSON representation. Options
are included in aggregate native request accounting. No dependencies were added.

GUI, Rust and Python wrapper validation are independent. Invalid wrapper options
fail before importing the selected plugin. Existing explicit code trust, copied
input/plugin sources, dedicated socket protocol, shared worker admission, output
validation, no-clobber publication, cancellation and process limits remain in
place. Python code still executes with the user's account permissions.

Morphology remains deferred: the original app only supplied file selectors and
neither addflex.py nor a wordforms data contract is available. No external
morphology format or language rules are invented by this change.

## Validation and Mac check

Local executable checks cover real Python subprocess option delivery, legacy
CC-CEDICT compatibility, structured refusals before import, multilingual values,
and pure Node parser tests. Rust integration tests for options are authored;
Rust/Tauri/Svelte execution must be checked on the Mac. No local native success
is claimed. Close the app, merge this update, then run from the project root:

```sh
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-plugin-options
```

Send m3-shell-out-plugin-options/m3-shell-report.json. On success launch from
m3/desktop with npm run tauri dev. In Python converter select the .venv Python
executable, m3/fixtures/noisy_plugin.py, class OptionsPlugin, and
m3/fixtures/build-source.txt. Choose a fresh result folder and enter:

```json
{"prefix":"字 مرحبا","uppercase":true}
```

The output.txt begins with the plugin-options entry whose definition is 字 مرحبا;
existing source text follows uppercased (including APPLE). Clear options or use
{} with NoisyPlugin to keep the existing copy behavior. Invalid JSON, nested
values and oversized fields must fail before a job is submitted.

The completed Database decision stays valid for its retained production snapshot
under docs/evidence/m4-database-final-qualified/production. Regression tests verify
all 104 frozen identities there; new plugin changes are qualified separately.
The historical Database runner still compares live production with that older
checkpoint and is not a gate for unrelated subsequent features. No repeat of
the completed Database closeout is requested.

## Mac native result

The package-169 user report passes all 15 shell commands, including both new
Rust options tests, five Python wrapper tests, 30 Node tests, frontend build
and Tauri cargo check. All 187 delivered source identities and 324 protected
M2 identities match; see evidence/m3-plugin-options-qualified. No code fix or
repeat native build is needed. Manual launch and the OptionsPlugin GUI example
above remain pending. This later receipt supersedes the earlier native-pending
text, while keeping the authoring-environment limitation explicit.

## GUI fixture output verified

The user supplied output.txt and bridge stdout after correcting the Python
executable selection. Output bytes exactly match the six-record expected fixture:
plugin-options with 字 مرحبا, followed by uppercased source rows including APPLE,
both 字 definitions, Arabic and the empty definition. Stdout contains only the
expected ordinary import prints. See evidence/m3-plugin-options-qualified/
gui-output-review.json for hashes and scope. This completes the GUI fixture smoke
check; it does not claim all plugin behavior, schema forms or full M3 completion.
