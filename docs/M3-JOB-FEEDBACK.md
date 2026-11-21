# Job feedback and interpreter-selection guidance

This frontend-only slice fixes the unconditional success color previously used
for every job status. Queued/running jobs use the accent color, success uses
green, failures use a light/dark error color, cancellation uses muted text,
and a cancellation request uses a warning color until the final state arrives.
State labels remain explicit, translated in English/Chinese/Arabic, and exposed
as status text; color is not the only signal. Unknown states have an explicit
fallback with the original state in the title. Forced-colors mode uses system text.
A late cancellation request cannot change a succeeded job's label.

Publication uncertainty takes priority over other hints and remains a warning,
even for a contradictory cancelled/succeeded snapshot. Full native error data,
including limit/detail/publication_uncertain, remains under Error details.
Readable summaries remove only repeated leading code prefixes, avoiding messages
such as cancelled: cancelled: ...; they never mutate native snapshots. Normal
cancellation details use muted text instead of the failure color. Existing
receipt collection, cancellation, dismissal and shared admission are unchanged.

Typed destination_exists and limit_exceeded failures receive actionable hints.
Permission-denied IO errors provide interpreter/access guidance for Python
converters and input/output permissions guidance for other operations. These
are suggestions, not diagnoses of a particular path; the raw error is retained.
No arbitrary engine error is reclassified as a permission error.

When Python executable and plugin file are exactly the same path, submission is
refused with a translated explanation to choose the interpreter. This detects
the earlier screenshot error without guessing from a .py extension: executable
custom launchers with different paths are still permitted. It is not a general
filesystem/executable permission probe.

Local Node tests cover all states, late cancellation, uncertainty precedence,
code-prefix display, untouched errors, hint selection, interpreter equality and
all three locale dictionaries. No Rust source, lock, native permission, dependency
or cap changed. Earlier Database and plugin-native qualification stays separate.

## Mac frontend check

Close the app, update the project, then run from its root:

```sh
.venv/bin/python scripts/m3_job_feedback.py --output m3-shell-out-job-feedback
```

Send m3-shell-out-job-feedback/report.json. This runs frontend Node tests and
Svelte/TypeScript/Vite build and verifies source stability and all 324 protected
M2 identities. No repeated Rust or Database closeout gate is required.

After it passes, launch npm run tauri dev from m3/desktop. Check existing job
cards if present; otherwise use NoisyPlugin for success, FailingPlugin for a
controlled failure and SlowPlugin followed by Cancel for cancellation, each
with a new result folder. Success should be green, failure red and cancelled
muted, with Error details available on failure/cancellation. Plugin fixture names
are classes in m3/fixtures/noisy_plugin.py. Cancellation and failure must retain
their existing no-publication semantics. For the preflight check, deliberately
select that same plugin file in both Python/plugin fields: the app should show
the interpreter-selection explanation without creating a job. Restore the
working .venv interpreter afterward. Backend behavior is not requalified by
these presentation checks.

## Mac frontend result

The package-175 report passes all 40 Node tests, Svelte checking with zero
errors/warnings and Vite build. Sources match; see evidence/m3-job-feedback-qualified.
No correction or repeat build is required. Manual job-state presentation and
interpreter-preflight checks remain pending.

## Scoped GUI checks accepted

The user supplied the expected FailingPlugin engine error and open Error details,
then the SlowPlugin cancelled error with publication_uncertain false, and finally
the exact translated invalid_input explanation for identical Python/plugin paths.
See evidence/m3-job-feedback-qualified/GUI-confirmation.json. These verify
diagnostics, cancellation text and interpreter preflight. Color screenshots,
filesystem inspection and job-count evidence were not supplied; no independent
visual color acceptance is claimed. No code correction or repeat build is needed.
