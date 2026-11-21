# Exact crashing pair: findings and isolated revision-4 candidate

**Update:** the user's v4 report passes all 16 offline wire checks. Rust tests,
fixture build and interop returned success. The metadata counts remain
91/10/2/8. Native testing remains unrun. The next separate diagnostic is in
[MINIMAL-READER-CONTROLS.md](MINIMAL-READER-CONTROLS.md); the source-preparation
notes below describe the original v4 delivery.

The received ZIP matches the reported hashes for the UTF-16 mdxbuilder pair.
The originals are retained inside their ZIP, not as loose dictionary files in
the package. Never import those archived fixtures into a reader.

## Confirmed from the actual bytes

| Property | Crashing MDX | Crashing MDD |
|---|---|---|
| Records/resources | 13 | 2 |
| Key blocks / record blocks | 9 / 8 | 1 / 1 |
| Header and block checksums, lengths and offsets | Pass | Pass |
| Record text terminator | Missing in all 13 UTF-16 records | Not applicable to binary resources |
| Encrypted header attribute | Absent | Absent |
| Encoding header attribute | UTF-16 | Absent |
| Title/Description/Format | Present | Absent |
| Header ending | closing tag then UTF-16 NUL | closing tag then UTF-16 NUL |

In contrast, all 296,110 records in the attached working MDX dictionaries have
an encoded terminal NUL; the working files declare Encrypted=No and end their
header XML with CRLF before the UTF-16 terminator. The working MDD also has
explicit empty Encoding/Format and a Title/Description. These are measured
differences. A checksum pass is not a legacy-writer compatibility pass.

The upstream writer encodes body text directly, omitting the record terminator.
The Rust reader trims trailing decoded NULs if present, but also accepts records
without them. Python's reader also accepts the length-delimited unterminated
records. That explains why previous cross-reader round trips did not catch this
wire-contract omission. Reader code is not changed to hide a mismatch.

The supplied MDict crash log shows strlen called from vfprintf/vsnprintf during
startup. It does not identify the parsing field or prove which measured
difference triggered the crash. Missing header fields and unsafe native error
handling are hypotheses. The actual crash cause remains unconfirmed.

## Revision 4: source fix, not post-hoc binary repair

The isolated patch adds one encoded NUL to each MDX body before record offsets,
sizes, blocks, compressed data and checksums are calculated. UTF-8/Big5/GBK/
GB18030 use one zero byte; UTF-16LE uses two. MDD binary payloads are unchanged.

It also emits Encrypted=No, explicit empty Encoding for MDD, and CRLF before the
existing UTF-16 header terminator. The native test wrapper supplies MDD Title,
Description, Format, Compact, Compat, CreationDate, RegisterBy and StyleSheet.
The MDX wrapper supplies the remaining legacy metadata used by the fixture.
CreationDate is the fixed synthetic fixture date 2026-10-28, not a production
timestamp policy. Caller-supplied metadata continues to be compared exactly.

The patch creates a new v4 vendor directory; prior source/evidence is retained.
Root/experiment lockfiles and dependency versions remain unchanged. Source
verification reverses all exact revision-4 edits and the UTF-16 label edit,
then checks the passing revision-2 source hash. No reader code is patched.

The existing C-locale ordering and case/strip flags are deliberately unchanged
by this narrow record/header candidate. Their native consistency is not proven:
the fixture's physical punctuation tie order differs from raw lexical order
while the header declares StripKey=No. This remains a separate compatibility
question and is not waived by the new record/header checks. Generic XML still
normalizes multiline stylesheet attributes; its ten known failures stay visible.

## Offline checks only

Update the project sources while keeping the existing v2/v3 vendor directories
and Python environment. Quit both readers and use an output directory outside
all configured dictionary search/import folders:

```sh
.venv/bin/python scripts/check_native_wire.py --output wire-out
```

The driver prepares v4, runs Rust experiment tests, generates controls under v4,
compares them through Rust/Python, runs the 14-check interop suite, retains the
metadata suite's ten unresolved stylesheet failures, and audits the emitted
bytes independently. Every MDX record must have its encoded terminator; every
fixture header must meet the selected explicit-header profile. MDD resources
are compared as exact bytes. Complete metadata results are retained, including
unsupported reverse GB18030 and dependent blocked checks.

It never launches a dictionary app. Return wire-out/native-wire-report.json
and any referenced failure log. Even offline_checks_passed_native_untested is
not permission to import fixtures or claim that the crash is fixed. Keep all
generated dictionaries outside app scan folders pending review of that report
and resolution of remaining compatibility questions.

The revision-4 Rust source has not been compiled in this environment. Local
regressions exercise the actual crashing bytes, independently reject their
missing terminators/headers, and test patch reversibility. Existing evidence
continues to record the native crash as a release blocker. No M1 completion or
production engine selection is claimed.
