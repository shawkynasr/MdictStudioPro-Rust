# Dictionary Tools: static rendered preview

Version 122, 2026-11-09. Authored for native qualification. The preceding shell
compiled and launched on the user's Mac; that success does not validate this new
Rust command, Svelte template, CSP or resource loader. M3 is still incomplete.

## Included

- Rendered / Split / HTML modes, independent Original / Paper / Dark preview
  appearance, and a Details inspector. HTML mode preserves the original record
  and clips its display at 65,536 characters; it never substitutes expanded HTML
  for the source. Preview appearance does not change app appearance or files.
- Source-verified title, description, numeric StyleSheet and other header
  attributes. Numeric marker expansion happens before passive HTML filtering.
  Unknown markers remain visible. Malformed stylesheets show a preview error.
- One optional MDD volume via the existing admitted indexed MDD reader. PNG,
  JPEG, GIF, WebP, AVIF, ICO, TTF, OTF, WOFF and WOFF2 resources are supported;
  linked UTF-8 CSS and its relative url() assets are embedded in the preview.
  No resource folder permissions or HTTP/filesystem plugin is added.
- English, Chinese and Arabic controls, RTL, and actionable resource warnings.

This is a static inspection view, not full MDict reader compatibility. JavaScript,
SVG, audio/video, CSS @import, remote resources, data URLs supplied by dictionary
markup, entry:// navigation, redirect resolution and multi-volume MDD discovery
are outside this slice. Small ordinary HTML links to same-document anchors remain.
Missing or oversized resources leave the entry readable with warnings. A native
serialized MDD reply can hit its 2 MiB cap before the preview's binary size cap.

## Merge and check

Merge into the existing project, preserving `.venv`, `vendor`, `node_modules`,
Cargo targets, real inputs and prior outputs. No dependency reinstall is needed:
the direct quick-xml dependency is already in the accepted registry graph.

From the project root:

```sh
python3 scripts/m3_shell.py --output m3-shell-out-v7
```

Use a fresh `m3-shell-out-*` name if that directory exists. This runner now also
runs the pure Node preview tests. If anything fails, send the new report and its
step logs. Existing successful M1/M2 reader batches do not need repeating.

Generate original fixtures, both dictionaries and both raw-exact indexes:

```sh
cargo run --offline --locked --manifest-path m3/native-adapter/Cargo.toml --example preview_fixture -- m3-shell-out-preview-fixture
```

The output directory must be new. All packing/indexing uses the real native
adapter and no-clobber publication. No downloads or proprietary dictionary data
are needed. If the example fails, retain its terminal output; the partial fixture
directory is not a qualified result. Use a new output directory for a retry.

Launch:

```sh
cd m3/desktop
npm run tauri dev
```

In **Dictionary Tools**:

1. Select `m3-shell-out-preview-fixture/preview.mdx` and
   `preview-mdx.idx`, policy **Raw exact**, then open. Both indexes already exist.
2. Expand **MDD resources**, select `preview.mdd` and `preview-mdd.idx`, then
   **Attach MDD**. One MDX plus one MDD reserves the existing two reader slots.
3. Look up `plain`, `styles`, `resources`, `missing`, `isolation` individually.
   `plain` shows all three scripts; `styles` shows inline-blue and marker-blue
   in blue; `resources` has a blue bordered card and blue image/background;
   `missing` remains readable and reports the missing asset in Details.
   `isolation` shows “Static content survives”; SCRIPT_RAN/HANDLER_RAN must never
   replace it. No example.invalid request should occur.
4. Switch Rendered / Split / HTML. HTML must show the literal original markup,
   including numeric markers; Split shows source beside the preview at wider
   sizes and stacked at narrower sizes. Open Details to check metadata, source
   SHA-256, selected ordinal and resource counts. Paper/Dark affect preview only.
5. Try Chinese/Arabic UI, app Light/Dark/System and keyboard focus. Switch entries
   or modes quickly while resources load; no stale previous preview should appear.
6. Close/detach readers during loading and reopen exact pairs. Active operations
   should return to zero after both readers finish cleanup. Quit while metadata
   or preview work is active and confirm a normal exit.

For a real font test, attach a previously qualified matching MDX/MDD containing
its CSS and font resource. A font installed on macOS alone does not prove MDD
font loading; inspect loaded resources and use a dictionary with a distinct font.
No claim of that visual qualification is made by this package.

For new indexes, close **both** readers, choose new index destinations, build
both indexes, then reopen. Indexing uses the full existing shared memory budget;
opening readers first would prevent index admission. MDD lookup is raw-exact;
resource keys try bounded leading-backslash, slash and bare variants. Escaping
the resource root and remote/special URL schemes are rejected.

## Browser isolation checks

While the Vite development server is running, open
`http://localhost:1420/preview-check.html` in a browser. The developer test page
uses the same renderer, checks resource rewriting and sanitization, tests opaque
frame access and deliberately bypasses sanitization to test the sandbox/CSP
script boundary. All checks should PASS and CSS_OK / MARKER_OK should be blue.
Keep the network panel open: no example.invalid request should occur. This page
has no native command access and does not replace the actual Tauri/WebKit checks.
It is a separate development entry, not included in the production Vite bundle.

## Boundaries and lifecycle

The app never attaches dictionary nodes to its document or uses Svelte {@html}.
A detached template parses inert markup. Filtering strips active elements,
non-HTML namespaces, event handlers, forms and navigation; only approved MDD
assets are converted to data URLs. The iframe has `sandbox=""`: neither
allow-scripts nor allow-same-origin. Its first metadata policy denies scripts,
connections, child frames, objects, base changes and forms; only inline CSS and
embedded image/font data are allowed. Parent CSP permits about: frames for srcdoc,
with unchanged app script/native connection origins. Capabilities remain local
main-window only, with no remote scope or additional plugin permission. Browser
sanitization checks and native frame behavior remain pending until executed.

The preview profile is 128 KiB of source **UTF-8 bytes**, 256 KiB of expanded
marker text, 4,000 elements, 32 resource attempts, 512 KiB per resource and 4 MiB
of raw resource bytes per preview. Repeated encoded assets have an additional
8 MiB expansion cap. These are application bounds, not hard OS memory limits.
Only one preview generation is active in the UI; changing selection/mode/attached
reader cancels its owned native requests. The sole 400 ms poll consumer transfers
and forgets resource job results, including cancelled/stale requests. Native
reader reply and retained-job caps are unchanged. Each resource request times out
after 15 seconds, requests native cancellation and retains cleanup ownership.

The new read-only `reader_details` command requires a collected open manifest,
then hashes the same source stream whose bounded UTF-16 header it reads and
compares that digest to the admitted reader's manifest. Changed source files
are refused. It caches one bounded metadata result per reader. File reads use
64 KiB buffers and run outside the adapter mutex on Tauri's blocking executor.
At most one metadata task per reader runs; its reservation remains held until
cancellation/cleanup completes. Closing cancels metadata and defers native close
until it stops; quitting stops publication, cancels metadata, waits off the UI
thread, then closes/joins readers and the runtime. M2 sources/caps are unchanged.

## Authoring checks

- Four executable Node tests pass for paths, stylesheet expansion, CSS resources,
  CSP and cancellation. TypeScript syntax checks pass.
- Python boundary contracts and accepted M2 identity verification pass.
- Authored Rust tests cover digest-bound metadata, bounds/cancellation, task
  join behavior and integration with the actual reader-open manifest, alongside
  the previously successful four adapter tests. New Rust execution is pending.
- Rust/Svelte compilation, browser DOM/security checks and native WebKit visual
  checks could not run here: no Rust toolchain, blocked npm registry, and local
  Chromium launch fails in this environment. Do not treat static contracts as
  runtime evidence.

## Version 123: Paper appearance and frame tooltip

The user's version-122 report passes seven Rust adapter tests, four Node tests,
Svelte checking (zero errors/warnings), Vite build and desktop compilation.
Screenshots show multilingual and numeric-style rendering, the rendered/source
split, and a blue resource card after MDD attachment. These observations do not
establish font loading, all Details behavior or network isolation. The user also
reports Dark preview working.

Paper previously set a white canvas and looked nearly identical to Original for
an entry whose original background was already white. It now uses a warm ivory
canvas (#f7f2e7) and dark brown default text (#342f29). Dictionary-specific colors,
fonts, images and card backgrounds remain as authored. Original and Dark preview
rules are unchanged. The frame now has an empty title and a translated aria-label:
the frame remains named for accessibility without the native “Rendered” tooltip
that appeared over the content in the user's screenshots.

Only frontend presentation changes in this correction. Merge and let Vite reload,
or restart `npm run tauri dev` from `m3/desktop`. Reuse existing dictionaries and
indexes; no fixture regeneration, native engine tests or dependency installation
is needed. Check Paper on `plain` and `styles` (warm canvas, both blue style
samples remain blue), then switch Original and Dark. Native visual verification
of this correction is pending.
