# Reference-matching stylesheet serialization candidate

The user reports all five official-builder entries, including both inline and
numeric marker formatting, work in MDict and GoldenDict. The exact synthetic
official output is archived in docs/evidence/official-stylesheet-reference/.
Its stylesheet header value is 147 characters: LF-separated triplets followed
by a final LF. The failed Rust control's value is the same 146 characters
without that final LF. Cause attribution remains unproven until a Rust output
passes native testing; the official file also has other header/block differences.

## Scope

The isolated Rust fixture-wrapper revision 6 uses the existing v5 engine and
HeaderLiteralC ordering. For only the new 05-stylesheet-wire case, it converts
CRLF stylesheet lines to LF and appends a final LF if a nonempty stylesheet
lacks one. Empty stylesheets and existing trailing blank lines are preserved;
bare CR is rejected in this diagnostic. The old fixture cases keep their old
behavior, so previous evidence remains reproducible.

**All five definitions remain exactly as in the failed Rust control.** No CRLF,
trimming, XML processing or style expansion is applied to body text. This
deliberately isolates the stylesheet difference instead of copying the official
source body's trailing CRLF. The engine source, encryption, other metadata
values, compression and block targets stay unchanged. Fixture titles identify
the new case. This is a wrapper candidate, not a new engine revision or a
production-wide normalization policy.

The official output's actual StyleSheet value, extracted from a hash-pinned
reference archive, is the independent expected value. It is not computed by
duplicating the Rust normalization algorithm in Python. All raw definitions,
physical order, exact lookups, Python marker expansion, checksums and record
terminators are still checked. Standard XML newline normalization remains an
explicit separate observation; the older ten metadata failures are not waived.

## One command, then a direct native check on success

Update project sources while keeping .venv and vendor. From the project root,
outside reader scan folders:

```sh
.venv/bin/python scripts/stylesheet_controls.py --wire-candidate --output style-wire-out
```

This verifies the unchanged v5 engine, runs the new Rust wrapper unit test and
generates UTF-8/UTF-16 controls. The report is
style-wire-out/stylesheet-controls-report.json. The command must exit zero and
print **offline_stylesheet_controls_passed_native_untested** before native tests.
If it fails, send the report and referenced log without importing new files.
Use a new output directory for a repeat run.

On offline success, test only
**style-wire-out/dictionaries/05-stylesheet-wire-utf16.mdx** first, by itself,
in GoldenDict and then MDict. Keep the old failing Rust stylesheet controls out
of their scan folders. The known-good official reference can be compared in a
separate session to avoid ambiguous duplicate search results.

Check inline-blue and marker-blue: both blue and underlined STYLE_TWO_OK. Check
inline-red and marker-red: both dark red bold STYLE_ONE_OK with a red border.
Check plain: unstyled PLAIN_CONTROL_OK. Restart both apps. If the UTF-16 case
passes, repeat with 05-stylesheet-wire-utf8.mdx alone. If a reader crashes, stop
that reader's sequence and remove the new control before reopening.

Return the report and per-reader visual results. The generated results CSV
starts NOT_RUN because the script never launches an app. On success the report
marks native status NOT_RUN_READY_FOR_STAGED_MANUAL_TEST. This authorizes only
the limited manual check above; it does not report native execution or success.

Rust/Cargo are unavailable in the authoring environment. Local Python tests
validate the reference binding and reject unrequested body changes, but they
do not compile the new Rust branch. No confirmed native fix or M1 completion is
claimed before the user's runtime results.
