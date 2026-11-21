# Numeric stylesheet editing in a database copy

The existing metadata-copy editor now accepts an explicitly selected **Numeric stylesheet** replacement. Title and description edits remain optional. Unselected fields retain their original values. The original database is read-only; output remains a new verified, non-overwriting copy bound to the opened snapshot hash.

A stylesheet is limited to 16 KiB UTF-8. Nonempty values must contain LF-separated ID/opening HTML/closing HTML triplets and a final LF. IDs must be unique ASCII decimal strings of 1–32 bytes. CR/CRLF and tabs in the opening/closing fragments are refused, matching the accepted native MDX writer's profile. Nonempty replacements require existing `Format=Html` and `Compact=Yes` (or `1`); structural flags are never silently rewritten.

Every backtick-delimited ASCII decimal marker in every stored definition must have a rule in the replacement stylesheet. Clearing the field is permitted only if no definition contains such a marker. Bodies are not expanded or rewritten: raw markers, HTML, line endings, empty definitions and duplicate rows remain byte-for-byte equal as decoded text. A missing rule, malformed stylesheet, invalid XML character, stale source, cancellation or destination race must not publish a partial output. Unchanged title/description-only requests retain the accepted behavior and do not newly validate unchanged stylesheets.

The 64 KiB complete JSON-command boundary and aggregate metadata budget remain. The existing row, file, reply, deadline and shared-admission budgets are unchanged. Static preview filtering remains in force. This editor changes numeric HTML wrappers, not standalone CSS files or MDD resources. The existing MDX rebuild profile continues to enforce its encoding, lookup flags and serialized-header limits.

Close the app and update the project, then run from the project root:

```sh
.venv/bin/python scripts/m4_database_stylesheet_copy.py --output m4-database-out-stylesheet-copy
```

Use a fresh output directory. This command runs the complete metadata/desktop gate, verifies that the new stylesheet tests ran, then uses the actual adapter publication jobs to build UTF-8/UTF-16 MDX fixtures, import SQLite, open and close snapshots, replace only the stylesheet, rebuild MDX and reimport it. Independent Python checks compare the original, copy and rebuilt artifacts with all seven fixture records and exact metadata. No M2 source, dependency version or cap changes are required. Native compilation and reader rendering remain pending until the Mac gate and manual checks pass.

The green stylesheet fixture is `m3/fixtures/database-stylesheet-green.txt`:

```text
1
<strong>
</strong>
2
<span style="color:#008000">
</span>
```

Include a final newline. The expected visual comparison for both `native/utf8/rebuilt.mdx` and `native/utf16/rebuilt.mdx` is:

| Entry | Expected display |
| --- | --- |
| `marker` | MARKER_BLUE_OK is green despite its unchanged label |
| `inline` | INLINE_BLUE_OK remains blue |
| `combined` | inline-blue stays blue, marker-blue becomes green, marker-bold stays bold |
| `duplicate` | DUPLICATE_ONE_BLUE becomes green; DUPLICATE_TWO_BOLD stays bold |
| `multilingual` | English/Chinese/Arabic remain; MULTILINGUAL_BLUE_OK becomes green |
| `empty` | Empty definition remains empty |

For a GUI save check, browse `m4-database-out-stylesheet-copy/native/utf8/dictionary.db`, expand **Save database metadata copy**, select only Numeric stylesheet, paste the green fixture, and save to a new `stylesheet-gui-edited.db`. Browse that copy; Split should show green marker text beside unchanged raw markers. Then run from the project root:

```sh
.venv/bin/python scripts/verify_database_metadata.py --source m4-database-out-stylesheet-copy/native/utf8/dictionary.db --copy /Users/shawky/Downloads/stylesheet-gui-edited.db --stylesheet-file m3/fixtures/database-stylesheet-green.txt
```

Open the generated rebuilt MDX fixtures in MDict and GoldenDict to confirm reader rendering, using one copy at a time. The automated gate does not claim those visual checks. Title/description remain unchanged throughout the style-only round trip. This step does not qualify arbitrary stylesheet syntax, entry editing, extra rebuild lookup policies or full M4 completion.


## GUI paste correction

The first GUI save attempt omitted the final newline after `</span>`, so the strict native API correctly refused publication. The editor now converts CRLF/bare CR to LF and adds a missing final LF before building the command. It validates complete triplets and unique numeric IDs before displaying the save dialog or closing the snapshot. Existing canonical LF text, HTML whitespace and intentional empty suffixes remain intact; extra blank lines are not trimmed. The normalized value is subject to the same 16 KiB and command-size limits. Direct native requests remain strict and unchanged. The database editor now uses the existing full-width metadata textarea and checkbox styling.

User reports both generated UTF-8/UTF-16 rebuilt MDX files display without issues; supplied reader screenshots show green marker text alongside blue inline text and bold text. The GUI-created database save remains pending a retry with this correction.
