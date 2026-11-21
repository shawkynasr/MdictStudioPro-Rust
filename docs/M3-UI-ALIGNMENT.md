# Studio 03 interface alignment

Current continuation: version 122 adds the real isolated Dictionary Tools preview.
See `M3-PREVIEW.md` for the updated feature scope and native test procedure.
The source-only statements below describe the earlier visual revision.

2026-11-09. The user's version-119 report passed all four Rust adapter tests,
Svelte/TypeScript and Vite build, Tauri information and desktop Cargo checking.
The user also confirmed successful `tauri dev` startup. That receipt, its exact
matching source snapshots and the separate launch attestation are retained in
`docs/evidence/m3-shell-first-success/`. This does not qualify every GUI job flow
or finish M3. Resolved frontend/desktop lock bytes still need preservation from
the native workspace before release dependency qualification.

## Correcting the visual mismatch

The first shell implementation simplified the approved mockup instead of porting
its layout. This revision uses the exact uploaded `preview-SOL V2.html` visual
tokens and base CSS, preserved as `m3/design/studio-03-approved.html`, then applies
native-window overrides. It restores:

- The 192 px grouped sidebar, blue book mark, consistent outline icons, bottom
  Jobs/Settings area and local-workspace footer.
- The full-width heading with title, descriptive subtitle and format badge.
- The source card and the numbered Source / Dictionary section headings.
- Grouped form rows, understated selects, advanced options and primary action.
- The 252 px right output inspector with live destination name, format, encoding,
  selected packing profile and no-clobber/background behavior.
- The six-card converter selection gallery and consistent job/lookup surfaces.
- Chinese/English/Arabic translation, RTL and independent native platform styling.

The web mockup's desktop wallpaper, outer decorative frame, OS simulation
switcher, pretend traffic lights, sample filenames and simulated jobs are not
inserted into the native application. The real OS supplies window controls.
macOS reserves physical left space for those controls even with Arabic RTL.
Language and theme controls are available in the app header and Settings.
Database and Morphology are visible as planned workspaces, with clear unavailable
content rather than fake native functionality.

Real backend constraints remain visible: building requires a JSONL manifest,
conversion produces TXT, destinations must be new and the block-spooled packing
profile is selected deliberately in More options. Dictionary Tools still shows
escaped source only; the rendered-preview security slice has not been enabled.
The original 32-row page limit and source-display clipping remain unchanged.

## Scope and verification

No Rust adapter, Tauri host, permission, capability, dependency manifest, native
configuration or M2 source changed in this visual revision. All ten existing
async frontend command/lifecycle functions were compared byte-for-byte against
the successful package and remain unchanged. Presentation helpers, markup, CSS,
icons and translated labels changed; preference loading now waits before writing
defaults, so a saved language/theme is not overwritten during initialization.

Local verification covers TypeScript syntax, translated-label availability,
configuration/icon/Python contract checks, archive integrity and the 324 accepted
M2 source identities. No native runtime or browser-rendered visual comparison is
claimed for the new interface. This authoring environment has no Rust toolchain
and npm access is blocked; the new Svelte template still needs its native build
check. Earlier compilation success applies to its preserved source snapshot,
not automatically to this new UI.

Merge the update while keeping `node_modules`, native targets, `.venv`, `vendor`,
inputs and prior outputs. From the project root run:

```sh
python3 scripts/m3_shell.py --output m3-shell-out-v6
```

No `--install` is needed if the dependencies from the successful run are kept.
On success launch with:

```sh
cd m3/desktop
npm run tauri dev
```

Compare the build screen with the approved HTML at approximately the same
content width (the mockup's outer desktop padding is not app content). Check the
source card, grouped rows and right inspector; then check dark appearance and
Arabic RTL. Source/destination selections, converter jobs, receipts, cancellation
and reader disposal should retain the earlier native behavior. No old independent
dictionary-reader qualification batches need repeating for this frontend change.

## Native light/dark screenshots and select polish

The user subsequently supplied native Build-screen screenshots with Light
selected and a dark appearance while System was selected. The revised sidebar,
source card, grouped form, inspector and footer are visible in both. This is
visual evidence for this screen, not evidence for GUI job/reader workflows or
explicit Dark-selection behavior. The source image identities and scope are in
`docs/evidence/m3-ui-light-dark-user-confirmation/confirmation.json`; the screenshots
themselves are not copied into the distributable package.

Version 121 changes only select-control presentation: remove the WebKit native
gradient, make grouped-row selects compact and trailing-aligned, add a small
chevron and retain native HTML select behavior. The main titlebar remains LTR
for native window controls; form/settings chevrons follow Arabic RTL. Keyboard
focus outlines remain visible, and forced-colors mode restores system control
appearance. Rust, command bindings, profiles and dependencies are unchanged.
No repeat native qualification batch is needed for this CSS change. After
merging, the existing Vite dev server can hot-reload the stylesheet; otherwise
restart `npm run tauri dev`. A visual check of the new select styling is pending.
