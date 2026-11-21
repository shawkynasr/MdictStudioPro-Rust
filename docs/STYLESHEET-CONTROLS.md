# Isolated stylesheet rendering control

The user reports successful entry lookup in all six v5 minimal controls in
MDict for macOS 2.2.6 (build 200) and GoldenDict 26.6.1-7548db1682. This is
manual user-reported native evidence, separate from the offline report. It does
not demonstrate every historical crash cause, every Unicode shaping behavior,
or completion of M1. Restart results were not separately recorded for every
file. The original crashing pairs remain archived and excluded from testing.

## Generate offline first

Keep the existing .venv and vendor folders when updating this package. From
the project root, outside native reader scan folders, run:

```sh
.venv/bin/python scripts/stylesheet_controls.py --output style-out
```

Return **style-out/stylesheet-controls-report.json** and any referenced failure
log. The script generates two MDX-only files, UTF-8 and UTF-16, each containing
five entries. The v5 engine, HeaderLiteralC sorting and lockfiles are unchanged.
The existing fixture wrapper is extended only to supply an embedded stylesheet
and Compact=Yes for the new 04-stylesheet case. The original minimal cases keep
their existing metadata. No MDD, CSS file, font, image, redirect or script is
added. The supplied real CC-CEDICT dictionary is not modified or bundled.

The script compares exact raw definitions and physical order through Rust and
Python, exercises all five lookups and one missing key, checks all structural
checksums/offsets/terminators, and independently checks Python's marker expansion
against the inline controls. Header StyleSheet literal line breaks are retained
and checked exactly. Standard XML's newline normalization is explicitly reported
as a separate observation; no storage comparison is weakened to make it pass.
The ten previous metadata failures remain unresolved in their original reports.

The writer is unchanged from v5. The new wrapper branch has not been compiled
in the authoring environment; runtime verification occurs on the user's Mac.

## Native visual comparison after offline report review

Test only 04-stylesheet-utf8.mdx first, by itself, in each reader. Its five keys
are deliberately ordinary ASCII words so this step isolates rendering:

| Search | Expected |
|---|---|
| inline-red | Dark red bold STYLE_ONE_OK with a red border |
| marker-red | Exactly the same styling as inline-red; no visible `1` |
| inline-blue | Blue underlined STYLE_TWO_OK |
| marker-blue | Exactly the same styling as inline-blue; no visible `2` |
| plain | PLAIN_CONTROL_OK with no inherited marker formatting |

Also search missing (no exact entry) and restart each reader. Record visual
results per reader rather than treating successful lookup as successful styling.
If UTF-8 passes, repeat with 04-stylesheet-utf16.mdx alone. Stop that reader's
sequence on a crash and remove the new control from its scan folder before
reopening. Keep the old crashing pairs excluded.

The generated reader-results.csv starts NOT_RUN. Neither script nor successful
Python substitution establishes native rendering. CSS, images and fonts through
MDD are the next separate stage after stylesheet rendering is verified.
