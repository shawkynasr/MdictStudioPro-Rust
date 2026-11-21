# Rendered database definition previews

Browse database adds Rendered, Split and HTML views, plus Original, Paper and
Dark preview appearances. Selection, exact/prefix lookup and pagination retain
their existing behavior. This is presentation only: no database rows, header
attributes, source files, native operations or limits are changed.

The shared Dictionary Tools renderer prepares the document in detached DOM
and displays it in an empty-sandbox srcdoc iframe with its existing child CSP.
Untrusted markup never enters the application document. No MDD resource loader
is passed for database previews, and they cannot borrow a Dictionary Tools
reader. Preview warnings remain visible. MDD images, fonts and external CSS
require Dictionary Tools; there is no new filesystem/network access.

MDX-derived databases use stored Format and StyleSheet attributes. Format=Text
is escaped into a preformatted text block, without numeric-style expansion.
For HTML and plain TXT-derived databases, inline HTML is interpreted and any
stored numeric stylesheet is applied. The HTML tab always shows original source
using Svelte text binding, including content removed from a rendered preview.
It is not silently truncated. The renderer retains its 128 KiB entry and 4,000
element limits; an entry exceeding preview limits can still be read in HTML.

Each entry/page/appearance change aborts the previous preview request and
clears stale content. Leaving Database also aborts it. Empty definitions remain
valid blank previews. Source view and preview appearance choices stay selected
while navigating pages.

## Native and frontend gate

Merge the updated project, preserving vendor and caches, then run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_shell.py --output m3-shell-out-db-preview
```

The new Node tests cover stored stylesheet preparation and plain-text escaping.
The existing isolation contract now checks every iframe, including Database.
The shared renderer and its resource/CSP tests remain in use. A Mac frontend
build and native desktop check are required: preparation has neither Rust nor
installed Svelte dependencies and does not claim a compiled or visually tested
desktop result.

## GUI checks after the gate passes

Restart the updated app from `m3/desktop` with `npm run tauri dev`.
In Browse database, use the existing five-record `dictionary22.db`:

- Rendered: apple displays “A fruit.” without HTML tags.
- Split: the formatted definition and its unchanged source appear together.
- Both 字 entries retain their separate definitions when selected.
- Arabic remains readable; empty remains a valid blank entry.
- Switch Original/Paper/Dark; the source pane is unaffected by preview appearance.
- Change query or page while Split is selected; no previous definition lingers.

For numeric styles, select the database already created by the stylesheet
runner: `m4-stylesheet-out/native/utf8/dictionary.db` (or its utf16 counterpart).
Exact lookup `marker` should display blue MARKER_BLUE_OK while Split/HTML
retains the literal `2` marker in source. `combined` shows blue and bold text.
Neither fixture needs MDD resources.

## Previous prefix qualification

The matching Mac report passed 11 database, 67 runtime and 17 adapter tests,
frontend checks/build and Tauri compilation. User screenshots confirmed both
pages of app, distinct App, literal percent/underscore, Arabic and Chinese,
plus zero results for exact app. Text/source-bound evidence is retained in
`docs/evidence/m4-database-prefix-qualified/`. Those results predate the new
preview interface and are not presented as validation of this change.
