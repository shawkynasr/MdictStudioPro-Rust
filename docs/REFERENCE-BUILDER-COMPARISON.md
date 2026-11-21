# Compare the same source through MdxBuilder 3.0 RC1 and Rust

The supplied MdxBuilder.zip contains a Windows executable with the dialog string
MdxBuilder Version 3.0 RC1. Its SHA-256 is
ab42b3c53b7f8c3f36ee00d338bef18778bd22f000348e90d9b54e14ca4903d4.
This identifies the inspected binary; it is not a claim of publisher signature
verification. Its manual documents three-line numbered style definitions. The
bundled example uses CRLF and has no final stylesheet newline. Source-file line
endings do not by themselves prove the emitted header representation.

The user supplied the distinction MdxBuilder 3.x -> MDX v2 and MdxBuilder 4.x ->
MDX v3. We use the former reference here and independently require the generated
header to declare version 2.0. The executable version is not the output-format
version. The original executable is not redistributed in this package.

## Ready-to-use source kit

Use **baseline/reference-builder-kit/**. It contains source.txt, style.txt,
rust-spec.json, reference-kit.json and BUILD-IN-WINDOWS.txt. Both builder input
text files are UTF-16LE with BOM and CRLF. The stylesheet has no final newline.
The Rust specification includes each body's trailing CRLF explicitly. Any
different treatment by the official parser remains a measured difference.

The five entries are inline-red, marker-red, inline-blue, marker-blue and plain.
They use the same HTML and markers as the preceding stylesheet test. Changing
its source line endings for this comparison is deliberate and is recorded; this
does not silently replace or repair the earlier LF fixture. No resource files,
fonts, images, MDD or real dictionary contents are included.

## Official build: Windows or an existing compatible environment

Run the MdxBuilder.exe from your supplied archive and choose:

| Field | Value |
|---|---|
| Source | baseline/reference-builder-kit/source.txt |
| Style | baseline/reference-builder-kit/style.txt |
| Original format | MDict(Compact HTML) |
| Encoding | UTF-16(Unicode) |
| Title | 04-stylesheet |
| Target | official-stylesheet.mdx |
| Data/resource path | Empty |
| Encrypt | Unchecked; no key/password |

The archive's executable UI strings were inspected to ground these option
names; the UI has not been run in the authoring environment. No Windows runtime,
Wine or Cargo is available here. Therefore no official output or new native
success is claimed. This step requires a machine or compatible environment that
can run that Windows builder. Do not install a new runtime solely for this kit
without deciding that the time is worthwhile. If no such environment is
available, the reference build remains blocked; the source kit is complete.

Return **official-stylesheet.mdx**. Do not import it into readers yet.

## Optional automatic comparison on the Mac

If the output is available locally, update the project while retaining .venv
and vendor, then run from the project root (adjust the reference path):

```sh
.venv/bin/python scripts/reference_builder.py compare \
  --kit baseline/reference-builder-kit \
  --reference /path/to/official-stylesheet.mdx \
  --output reference-out
```

This verifies the source kit, inspects the small supplied v2 fixture, verifies
the unchanged v5 engine source, builds the Rust controls from the same source
contract and compares the UTF-16 output. The source inputs and reference output
are read-only. Reports include full header attributes, precise LF/CRLF strings,
raw definitions and physical order, Python-expanded marker/inline comparisons,
structural checks, input hashes and exact differences. These synthetic strings
are deliberately small and are retained without normalization.

The original independent auditor cannot audit encrypted key indexes. If a
reference unexpectedly declares encryption, that limitation stays explicit in
its structural result; header/body observations do not override it. Selecting
unencrypted output avoids that additional variable. No body or stylesheet
newline difference is waived to obtain a passing qualification result.

Return **reference-out/reference-comparison-report.json** and any referenced
failure log. comparison_complete_native_untested means observations were
collected, not compatibility established. Native imports remain paused.

## Existing results and scope correction

The six minimal v5 controls have user-reported native entry-lookup success in
both readers. The stylesheet fixtures passed offline checks but failed native
compatibility: MDict crashes on the UTF-8 fixture; GoldenDict shows marker-blue
as black text for both encodings. The follow-up about inline-blue suggests the
same problem, but its exact searched key was not supplied with that final text
observation. Do not record GoldenDict stylesheet rendering as passed.

The new crash on 2026-10-28 at 12:37:19 +03:00 is in MDict 2.2.6 (200), macOS
15.8.2. It faults at 0x90 in strlen/vfprintf/vsnprintf. Its first four MDict
offsets match the earlier crash; UI frames now show row selection. The failing
field and cause remain unidentified. No conclusion about XML processing,
Compact=Yes, marker expansion or CRLF is established by that stack alone.

The forum reference https://forum.freemdict.com/t/topic/45183 describes official
Wide/Narrow comparators. The app's existing mdxbuilder mode is only its own
ASCII-folding Python comparator. Our MdxBuilderC experiment reproduces that app
behavior; it is not a proven replica of the official Wide/Narrow algorithms.
HeaderLiteralC is a separate diagnostic profile, also not official equivalence.
