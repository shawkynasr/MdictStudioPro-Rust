# Active Python bridge parent-death cleanup

The user force-quit preview v5 while SlowPlugin was running. The observed app
process ended but the Python bridge and its staging directory survived. No output
was published; source/plugin hashes were unchanged. The diagnostic explicitly
stopped the orphan, and the user confirmed reopening the app worked. This is a
confirmed cleanup failure, not accepted automatic recovery. The old staging
folder is retained and is not swept by this change.

## Implementation and boundary

The existing native run_child coordinator now creates a private marker containing
the per-job protocol token, and supplies its own PID and canonical stage path in
the private child configuration. This applies to conversion and inspection calls
using this coordinator. The wrapper installs its watch before importing plugins.
A daemon checks whether its direct parent has changed every 100 ms. If so, it
checks the original stage directory's device/inode and marker, removes only that
entry using symlink-resistant descriptor-based rmtree, and kills its own process
group (only when group ID equals its own PID). A completed publication has been
moved out of this stage; the destination path is never supplied to cleanup.

No Downloads scan, age-based deletion, stale-folder registry, new dependency,
limit increase, protected M2 edit or persistent job resume was added. Reopening
must not delete old .tmp directories. If marker/identity checks fail or deletion
fails, the bridge still stops; the folder remains for diagnosis. Python bridge
cleanup is cooperative and is not a sandbox: a native extension holding the GIL,
malicious trusted code, detached descendants, pre-wrapper/pre-watch crashes,
post-child-exit crashes and power loss remain outside this tested boundary. An
unrelated directory replacing the original is never intentionally cleaned up.

## Verification and delivery

Local tests execute the actual wrapper under a disposable subprocess parent and
force-kill that parent. They verify socket closure/bridge exit, stage removal,
preservation of a published sibling and a symlink target, replacement-directory
refusal, bad-marker rejection, normal conversion and structured failure. These
are Python/Unix authoring tests; they do not substitute for macOS Rust execution.
Existing wrapper, inspection and frontend contracts also remain required.

First quit the running app normally. Merge the updated ZIP into the existing
project while retaining vendor/caches/build artifacts. Run in Terminal:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_parent_death.py --output m3-shell-out-parent-death
```

Send m3-shell-out-parent-death/report.json. This is a new native behavior, so v5
cannot qualify the fix. The focused gate runs the new real subprocess tests,
existing wrapper/inspection/folder tests, locked/offline runtime and adapter
tests, frontend validation and desktop compilation, with source/lock/protected
identity checks. No native execution in the authoring environment is claimed.

After that report passes review, build a fresh preview v6 using the existing
packaging command with --output m3-shell-out-mac-preview-v6. Review its report
before repeating the force-quit diagnostic. For that repeat use a NEW output
folder and a NEW diagnostic directory, and --app pointing explicitly to v6.
The old armed v5 report must never be overwritten or reused to claim v6 results.
Expected active-job result: app gone, recorded bridge gone, owned stage gone,
no published output and source/plugin unchanged, without diagnostic cleanup
being needed. A successful reopen alone is not cleanup evidence. All native,
new-bundle and macOS GUI qualification of this fix remain pending until supplied.

## Mac native gate accepted

The user report passes all 13 stages: 3 abrupt-parent/guard tests, 6 wrapper tests, inspection/folder fixtures, 98 runtime and 29 adapter tests, frontend validation/build and desktop compilation. All 249 delivered source identities match; two optional Mac files match their existing exact bindings, all 324 protected identities match, and all seven resolved/final locks match the accepted build hashes. See evidence/m3-parent-death-native-qualified/report.json and review.json. No native code changed while recording this acceptance.

Next, with the app closed, run `.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview-v6` from the project root and send that report. No new download is needed for this evidence-only update. The standalone force-quit repeat remains pending; do not reuse v5 as proof of the fix.

## Preview v6 build accepted

The user supplied the v6 build report. All eight stages passed, source identities and 324 protected identities match, all seven build locks are exact, and copied/original bundle inspections are equal. The executable SHA-256 is 2fdde5759b44256afcf8fddf9e52c2dad59f17c756742e588c478c3bda9b140d. The native wrapper/coordinator identities match the accepted parent-death gate. See evidence/m3-parent-death-v6-built. This establishes build identity, not launch or force-quit cleanup. No app code changed while retaining this report.

Repeat SlowPlugin in the Finder-launched m3-shell-out-mac-preview-v6 app, with NEW destination /Users/shawky/Downloads/force-quit-check-v6-1. Arm the diagnostic with --app '/Users/shawky/Downloads/mdict-studio-m0-m1/m3-shell-out-mac-preview-v6/Mdict Studio Pro Preview.app' and --output m3-shell-out-force-quit-v6-1. After Armed, Force Quit only that preview, wait two seconds, then check with the SAME --output before reopening. Do not run diagnostic stop-recorded-child before collecting the new report. Expect no original app, no bridge, no recorded stage, no destination and unchanged source/plugin. If the bridge survived, preserve the report and explicitly stop-recorded-child with the SAME --output; otherwise no diagnostic cleanup is needed. Reopen the SAME v6 app and report the result. Old v5 stages remain outside this check.

## Standalone v6 force-quit and reopen accepted

The user armed the explicit v6 bundle and supplied its post-force-quit observation: original app false, recorded bridge false, recorded stage false, destination false, source/plugin unchanged. The diagnostic signalled no process and deleted no files. The user then explicitly confirmed reopening v6 normally. See evidence/m3-parent-death-v6-built/force-quit-observation.json and GUI-confirmation.json. The scoped active bridge fix is accepted; no routine repeat is requested. This does not qualify other crash phases, detached/GIL-blocked trusted code, power loss, automatic cleanup of old stages or persistent job recovery.
