# Saved Python plugin presets

This frontend-only slice stores up to eight named configurations locally in the
app's existing WebView storage. Each preset contains exactly name, Python path,
plugin path, class and scalar-map-v1 options. Input/output paths, result-folder
names and trust consent are never persisted. Nothing runs when a preset loads.
Loading always clears consent, and editing interpreter, plugin, class or options
also clears consent. No Python import or native command is used for presets.

Save new refuses duplicate names. Update selected is explicit and permits a
rename unless it collides with another preset. Delete affects only the selected
preset; all operations validate and build a new list before writing. The in-memory
list changes only after localStorage.setItem succeeds. Malformed, oversized or
unsupported stored data is kept; saving is disabled until the user explicitly
resets that preset store. This reset does not affect dictionaries or UI preferences.
Storage write errors are reported. Presets use plain-text app storage; the UI
explains this so users can choose whether to save sensitive option values.

Storage is versioned, limited to 64 KiB total, and rejects extra fields. Names
are trimmed, unique and <=64 Unicode characters / 256 UTF-8 bytes. Paths are
nonempty, valid Unicode, <=4096 UTF-8 bytes, with no NUL/newlines; class/options
use the existing validated limits. Absolute path existence/executable permission
is still checked by the existing native job when a plugin runs. Presets are
local to the current app/WebView profile, with no sync/export promise.

Local Node tests cover restart serialization, Unicode, immutable updates,
name collisions, explicit replacement, deletion, malicious trust/source fields,
corrupt/unsupported storage and count/byte limits. Rust sources, dependencies,
native permissions, accepted source identities and runtime caps are unchanged.
The completed Database snapshot and native plugin-options evidence remain valid.
Svelte/TypeScript build and manual restart behavior require the Mac check.

Close the app, merge this update, and run from the project root:

```sh
.venv/bin/python scripts/m3_plugin_presets.py --output m3-shell-out-plugin-presets
```

Send m3-shell-out-plugin-presets/report.json. This runs only npm test and the
frontend build, checks source stability and verifies all 324 protected backend
identities. It does not rerun Rust or the completed Database checkpoint.

After the build passes, launch npm run tauri dev from m3/desktop. In Python
converter reuse the working OptionsPlugin configuration and save it as Options
demo. Quit/relaunch, select the preset, click Load, and confirm that Python,
plugin, class and options return while trust remains unchecked. Choose an input
and new output folder manually, confirm trust and run. Update/delete can be
checked with a separate temporary preset. The resulting fixture output should
match the already accepted six-record OptionsPlugin example.

## Mac frontend result

The package-172 Mac report passes all 34 Node tests, Svelte checking with zero
errors/warnings, and Vite build. See evidence/m3-plugin-presets-qualified/report.json.
No code fixes or repeat build are required. The manual save/quit/reopen/load
check above remains pending. This result supersedes earlier build-pending text.

## Preset restart check accepted

The user reports quitting, reopening and loading Options demo. Reviewed captures
show the correct Python executable, noisy_plugin.py and saved NoisyPlugin class
restored while source and parent are empty. The user additionally confirmed
that options return and trust remains unchecked in response to an explicit
question; those controls are outside the supplied crop. See the separate
restart-confirmation.json. The earlier mismatched old-layout screenshot is
excluded from this evidence. No code fix or further build is required.
This accepts the scoped save/restart/load check, not manual update/delete
coverage, a fresh conversion after loading, or completion of full M3.
