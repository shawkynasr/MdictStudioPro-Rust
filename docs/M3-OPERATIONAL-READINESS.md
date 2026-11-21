# Standalone operational readiness: normal Quit

## Source review

Reviewed the unchanged preview v5 implementation, without executing Rust here:

- m3/desktop/src-tauri/src/main.rs intercepts CloseRequested and ExitRequested, prevents immediate exit, starts adapter shutdown off the UI thread, and exits after shutdown succeeds. Shutdown failure emits an error and leaves the app available for inspection.
- m3/native-adapter/src/lib.rs stops new runtime admission, cancels reader tasks, and joins accepted workers.
- m3/txt-runtime/src/python_plugin.rs checks cancellation while communicating with the child, kills/waits the owned child/process group via its guard, and keeps unpublished work under an owned temporary directory. Final publication occurs only after validation and a cancellation check.

This supports a focused normal-Quit check. It does not establish crash/force-quit/power-loss cleanup. Rust destructors cannot be assumed to run after forced process termination. There is no claim of persistent job resumption or automatic safe stale-directory recovery; those remain open release work. Trusted Python may create external side effects outside its result directory. Logical limits remain distinct from OS enforcement.

## User check in existing preview v5

1. In Jobs dismiss finished jobs if needed to free retained slots. Already verified output files are kept.
2. Open Converters → Convert with a plugin. Keep the configured external Python interpreter. Choose `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/noisy_plugin.py`, confirm import trust and click Import plugin.
3. In the discovered converter selector choose `SlowPlugin` (not NoisyPlugin or FailingPlugin). It intentionally waits indefinitely until cancelled or the existing deadline expires. No option fields need filling.
4. Input: `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/build-source.txt`. Choose a fresh output FOLDER name `/Users/shawky/Downloads/quit-check-v5-1`; do not create it first. Confirm conversion trust and start.
5. Wait until Jobs shows Running or the Waiting for cancellation callback. Press ⌘Q without clicking Cancel. Note whether the app exits normally and approximately how long it takes. Do not force quit just to make the test pass. If it stays open, report that behavior.
6. Check Downloads in Finder: quit-check-v5-1 should not exist. Reopen the same v5 app and confirm it opens normally. Jobs are process-local; this check does not expect the interrupted job to resume. Report the quit result, output-folder absence/presence and reopen result. No terminal command or new build is required.

This check does not qualify invisible temporary residue or orphan process absence from Finder alone; dedicated native observation would be needed for those claims. It also does not test crash recovery. Signing/notarization, clean-machine installation, remaining locale/keyboard coverage and other platforms remain open.

## Normal Quit result — 21 November 2026

Accepted from the user's scoped reports: app closed via ⌘Q during the requested test, no output folder appeared, reopening/no job resumption was confirmed. Timing was not supplied. This does not verify hidden staging cleanup or absence of child processes; see evidence/m3-normal-quit-qualified/GUI-confirmation.json.

## Force-quit diagnostic (current)

Source review identifies a concrete gap: ChildGuard and temporary directory destructors depend on the parent remaining alive to unwind. The wrapper has no independent parent-death watcher for an idle SlowPlugin. A hard termination may therefore leave the bridge process and unpublished staging behind; neither automatic recovery nor its success is claimed. Force Quit tests one abrupt-termination path, not a genuine application crash, power loss or every publication phase.

The new script scripts/m3_force_quit_check.py observes the existing v5 app. No application/native code changed and no rebuild is required. It binds one running bundle PID and executable hash, its direct fixture bridge PID/start time/command, snapshotted fixture hashes and staging directory. It uses ps on macOS, requires exactly one matching app and fixture child, and fails closed on ambiguity. It never kills the app. The arm/check actions only read state and create new diagnostic files under a fresh project-local m3-shell-out-* directory. No unrestricted system-process inventory is retained in the report.

1. Quit the app normally before merging the updated ZIP. Preserve the existing v5 app/caches. Reopen the same v5 standalone app.
2. Import m3/fixtures/noisy_plugin.py with the configured external interpreter and trust. Select SlowPlugin. Use m3/fixtures/build-source.txt as input and choose a NEW output folder `/Users/shawky/Downloads/force-quit-check-v5-1` (do not create it). Start and wait for Running/1% so that SlowPlugin is active. No other jobs should be active.
3. In Terminal run from the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_force_quit_check.py arm --destination /Users/shawky/Downloads/force-quit-check-v5-1
```

If arming fails, do not force quit: send the error. No diagnostic folder is created until the exact process/fixture checks pass. If a previous m3-shell-out-force-quit-1 exists, use a NEW --output m3-shell-out-force-quit-2 consistently for every action; do not overwrite an existing report.

4. Only after Armed appears, press ⌘⌥Esc, select Mdict Studio Pro Preview and click Force Quit. Do not select Python or Terminal and do not use ⌘Q. Before reopening, run:

```sh
.venv/bin/python scripts/m3_force_quit_check.py check
```

5. Preserve that observation, then stop the recorded fixture child if it survived:

```sh
.venv/bin/python scripts/m3_force_quit_check.py stop-recorded-child
```

This explicit diagnostic cleanup matches the saved PID/start-time/command before signalling that one fixture process, refuses while the original app is alive, and retains temporary files for review. It is not automatic app cleanup. It does not promise termination of arbitrary trusted-plugin descendants. Never use a blanket killall Python command.

6. Reopen the same preview v5 and report whether it opens normally, whether the interrupted job resumes, and whether the named output folder exists. Send m3-shell-out-force-quit-1/report.json and diagnostic-cleanup.json. A successful reopen alone does not establish cleanup. Do not delete or scan unrelated .tmp folders; the diagnostic retains only its identified path for review.

Local validation: Python syntax, process-output parsing and PID-reuse identity guards self-test. macOS ps matching, real forced termination and native behavior remain pending the user run. No Rust execution in the authoring environment is claimed. A genuine crash and forced termination near publication require separate qualification; automatic stale-directory recovery must be designed before it can be claimed.

## First force-quit diagnostic attempt

The user ran arm twice; both attempts stopped before arming with Expected exactly one running selected preview app. No force-quit result is claimed, and no cleanup was attempted. The initial detector required an exact command string and omitted ps wide output. The revised script requests untruncated ps -axww output, accepts trailing launch arguments, and recognizes relocated/copied app paths only when the executable and Info.plist bytes match the selected app. Bundle resources are not compared by this diagnostic. Multiple matching app instances still refuse arming. Failure now prints the selected path, match count and same-executable-name candidates rather than requiring guesswork. Local fixture tests cover long paths, launch arguments, copied-app matching, changed executable/metadata rejection and PID reuse. The actual cause of the first Mac mismatch is not yet established; the revised diagnostic remains Mac-run pending.

## Date/path parser correction

The second user arm attempt reported PID 95428 with the truncated executable path Studio Pro Preview.app/Contents/MacOS/mdict-studio-desktop. This establishes that the combined date/command parser consumed part of the path; the precise macOS date rendering was not supplied. The diagnostic now obtains pid/ppid/command in one wide ps query, splitting only the two numeric fields, and queries each selected PID's start time separately as an opaque string with LC_ALL=C. The supplied full executable path is covered by a regression test, including an arbitrary multiword date returned separately. Start-time checks remain mandatory before explicit recorded-child cleanup. Source application code remains unchanged. The corrected script can be replaced independently while the app is running; no force quit is permitted until arming succeeds. No native app failure or successful forced-termination check is claimed from either failed arm attempt.

## Force-quit v5 result and active-job fix

The user supplied the completed observation and explicit child-cleanup result, and confirmed normal reopening. The original app was gone, but the bridge and stage survived. No output was published and source/plugin stayed unchanged. The diagnostic then stopped the orphan, leaving temporary files. See evidence/m3-force-quit-v5-observed. This is a confirmed automatic cleanup gap. The targeted fix and next native qualification are documented in M3-PARENT-DEATH.md. Preview v5 remains the historical failed cleanup implementation; it cannot establish the fix. No automatic cleanup of older abandoned folders is introduced.

## Current active-job result

Preview v6 passes the scoped SlowPlugin force-quit cleanup and reopen check: its bridge and identified temporary directory disappeared without manual diagnostic cleanup, no output was published and source/plugin hashes were unchanged. User confirmed normal reopening. See M3-PARENT-DEATH.md for native/build/GUI evidence and the remaining broader crash boundaries. No repeat of this successful fixture is requested.
