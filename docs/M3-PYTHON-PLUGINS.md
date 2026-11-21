# Optional trusted Python converter bridge

Converters now offers **Python converter** beside the native built-in
converters. Select an existing interpreter executable, one `.py` file, an
explicit class defined in that file, an input file, and a parent/new folder
name. The class must inherit `BaseConverterPlugin` and implement the original
`convert(input_file, output_file, encoding, progress_callback, log_callback)`
signature. The original abstract base is embedded without Qt or other GUI
imports. The Run button requires an explicit trusted-code checkbox.

Python executes with the account's ordinary permissions. This is not a code,
filesystem or network sandbox. A malicious plugin can ignore the supplied
paths. It is intended for reviewed local plugins. No plugin is automatically
discovered, imported or run just by opening Converters. The selected interpreter
must already have required packages installed; this app installs none. Its
venv executable path is preserved rather than resolved to a system Python
symlink target. GUI labels are English, Chinese and Arabic.

## Protocol and lifecycle

The Rust parent embeds a Python entry point in a private temporary directory,
opens a local TCP listener on an OS-selected loopback port and supplies its
256-bit random authentication token through the child's private stdin. The
child connects and sends an authenticated versioned hello before importing
the selected plugin. Structured JSON messages travel only on this socket.
Ordinary stdout/stderr are separate OS files, so `print`, `os.write` and native
library output cannot corrupt the protocol. The protocol has 8 KiB frame and
4 MiB cumulative limits, bounded callback logs, and coalesced progress updates.

The job runs on the existing serial publication worker under the existing
exclusive 384 MiB logical / 3 GiB temporary reservation. Readers must close
first. Cancel, shutdown, Take, Forget, pending/retained job limits and late
cancellation semantics remain the same. No shell command strings are used.
The process is put in its own Unix process group; cleanup kills that group and
waits for the direct child. This is not containment of a plugin that deliberately
escapes its group, nor a guarantee of reaping every descendant. OS-level hard
memory/disk limits and production crash recovery remain outside this profile.

The input and plugin source are copied and hashed before execution. The plugin
receives the private input copy, which avoids normal legacy side effects on
the original input. Its compiled source keeps the original `__file__` value,
and its original directory is available for sibling imports. Imported helper
modules are not snapshotted or hashed. Only a single input file is copied;
plugins requiring neighboring input assets need a later profile.

## Output contract and limits

Success creates a **new result folder** containing:

- `output.txt`: validated UTF-8 canonical dictionary TXT.
- `bridge-stdout.log` and `bridge-stderr.log`: raw captured streams.
- `input-sidecars/`: regular top-level files the plugin wrote beside its
  private input, such as the original CC-CEDICT plugin's `input.txt_log.txt`.
- Other supported files the plugin created in the private result directory.

Only after the child reports completion and exits successfully does Rust
validate the TXT using the existing M3 streaming preparation code, inspect
the output tree, and publish with the macOS/Linux no-replace directory
primitive. Existing destinations are refused. Errors/cancellation remove the
stage rather than publishing a partial result. A collected receipt contains
input/plugin/output SHA-256 values, record count, path count, byte count,
callback messages, summary and short raw log tails. It does not embed full logs.
Failure messages include a bounded stderr tail, not a published failed bundle.

Initial limits: macOS/Linux, UTF-8 input/output, 64 MiB input and individual
workspace file, 1 MiB plugin source, 128 MiB workspace, 256 paths, nesting <=8,
16 MiB per raw output stream, 10-second protocol startup and a 300-second
subprocess deadline. Limits are checked cooperatively; a child can allocate
memory or write between checks. The shared reservation is accounting, not an
OS-enforced cap. The TXT verifier also retains its existing 250,000-record /
96 MiB decoded / 1 MiB body profile and bounded JSONL validation spool.

Private workspace/output names in this initial profile use portable ASCII
letters, digits, dot, underscore and hyphen, <=128 bytes per component. Source
and selected plugin paths may contain Unicode. Symlinks, special files,
case-aliasing names and non-regular adjacent-input sidecars are refused.
Custom option schemas, automatic class discovery, dependency installation,
multiple inputs and Windows process management remain future work.

## Verification

Local executable Python tests exercise actual sockets and subprocesses:
import-time print, conversion print, `os.write`, stderr, multilingual callbacks,
structured exceptions/wrong classes, and the original CC-CEDICT plugin. Native
Rust tests are authored for publication, no-clobber, input/sidecar preservation,
invalid TXT, failure cleanup, running/precommit cancellation, one-transfer
receipts, authenticated protocol errors and shared admission with readers.
Rust and Svelte execution is unavailable in the authoring environment.

Run on Mac:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v15
```

The check supplies its own `sys.executable` to native plugin tests. Then launch:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

Choose Converters → Python converter and enter:

| Field | First test value |
| --- | --- |
| Python executable | `/Users/shawky/Downloads/mdict-studio-m0-m1/.venv/bin/python` |
| Plugin | `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/noisy_plugin.py` |
| Class | `NoisyPlugin` |
| Input | `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/build-source.txt` |
| Parent folder | `/Users/shawky/Downloads` |
| New folder name | `studio-plugin-result` |

This fixture needs only Python's standard library. Check the trust box and Run.
In Jobs, collect the receipt: expect **5 records**, ordinary debug messages in
stdout, a stderr warning, and a multilingual structured callback. The result
folder should include `output.txt` identical to the original five-record input
and an `input-sidecars/input.txt_log.txt` file.

Repeat with the same destination to check refusal. For failure cleanup choose
`FailingPlugin` and a new folder name; for running cancellation choose
`SlowPlugin`, then Cancel in Jobs. Neither should publish a result folder.
All three classes are defined in the same original fixture file.

For a legacy compatibility check, select
`baseline/legacy/plugins/cccedict_plugin.py`, class `CCCEDICTPlugin`, input
`m3/fixtures/cedict.txt` and a new result folder. Spreadsheet plugins require
their Python packages (for example openpyxl) in the selected environment.
The built-in native converter routes remain available and do not invoke Python.

## First native run correction

The v14 receipt passed export I/O tests, then ran 15 indexed-session tests:
12 passed and 3 failed while importing their shared test fixture, before
redirect execution. That fixture omitted the required declared Format header.
The fixture now explicitly declares `Format="Html"`, matching the inherited
indexed-session fixture and the actual application packer. Importer validation
and test expectations remain unchanged. This run did not reach plugin Rust
tests or the frontend build; those remain pending in v15. Non-fatal
`dropping_copy_types` warnings did not cause the failure.
