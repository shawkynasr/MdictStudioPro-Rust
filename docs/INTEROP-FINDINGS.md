# Interoperability results and revision-2 corrections

The subsequent user-uploaded revision-2 report passes all fourteen checks.
It is retained unchanged in `docs/evidence/interop-v2-user-run`, with source
fingerprints and environment versions. This establishes the synthetic UTF-8
cross-engine subset on Intel macOS; metadata, other storage codecs, reader
apps and large dictionaries remain separate gates. The earlier failure report
below is retained to explain the corrections.

Original report is preserved unchanged under `docs/evidence/interop-v1-user-run`.
It contains fourteen checks: two passes and twelve failures. Do not overwrite
this historical evidence.

## Ten forward failures: header encoding detection

The failure is KeyError on GeneratedByEngineVersion, not a missing attribute in
the Rust source. The Python reader chooses UTF-16 only when the header payload
ends with two zero bytes. The upstream Rust writer encodes XML as UTF-16LE but
does not append that terminator. Python consequently treats it as byte-oriented
text and cannot recognize its attributes. All ten forward checks stop before
record comparison. This is independent of sorting and Python 3.14 is not shown
to be its cause.

Revision 2 appends the UTF-16LE terminator inside the writer, before the existing
header length and ADLER32 are calculated. No dictionary is repaired after the
fact and neither reader is monkey-patched. The Rust experiment and independent
Python header inspection now check the terminator, length and checksum.

The root upstream workspace remains a historical baseline; interop fixture
generation now runs the probe library through the patched experiment workspace
for both default-sort and explicit-sort files. Thus all files under test come
from the same revision-2 writer. The legacy ordering and reader flags remain
unchanged. No claim about universal reader compatibility follows from this fix.

## Two reverse MDX failures: incorrect harness source expectation

The legacy text loader preserves the line ending immediately before </> as
part of the stored body. The first harness compared that result with the raw
builder fixture body, which had no final LF. All eleven observed reverse
records differ by that single LF, with keys, duplicates and text retained.

This was an expectation error in the harness, not evidence of a broken binary
reader. Revision 2 independently derives exact body spans from the input TXT,
checks those spans against the fixture plus its explicit separator LF, and
requires both Python and Rust readers to return those same bodies. It does not
strip whitespace, normalize newlines or discard a failing comparison. Missing
or extra line endings still fail. Production TXT import semantics remain an
explicit migration policy; raw builder bodies must remain verbatim.

## Two reverse MDD passes

Both original Python sort profiles produced MDD files whose four resources
were read by Rust with exact bytes preserved. These passes remain valid for
the supplied fixture. No legacy-encoding or native-reader conclusion is drawn.

## Safe revision handling

The new preparation target is `vendor/mdictlib-0.2.8-studio-sort-v2`. The original
v1 vendor directory is left intact. The experiment manifest points at v2. Its
local dependency has the same name/version/dependencies, so the uploaded
experiment Cargo.lock is retained. The preparation marker identifies revision 2
and its exact generated source hashes. The harness refuses a v1 marker.

Read `docs/PATCHED-INTEROP.md` for reproduction commands. No Rust execution took
place in this environment. Runtime evidence is from the user's uploaded report.
Continue with `docs/METADATA-CODECS.md` for the next qualification gate.

Source references used to trace this issue:

- https://docs.rs/mdictlib/latest/src/mdictlib/write/mod.rs.html
- https://github.com/liuyug/mdict-utils/blob/master/mdict_utils/base/readmdict.py
- https://github.com/liuyug/mdict-utils/blob/master/mdict_utils/writer.py

The installed package was pinned to 1.3.14 by the user report; the published
reader/writer source is corroborating evidence. Future runs retain exact local
writer source hashes so changes do not silently become accepted baselines.
