# Local standalone Mac preview

The seven supplied lockfiles have been reviewed in
`evidence/m3-mac-lock-capture/review.json`. Desktop Rust/frontend locks exactly
match the hashes in the passing native report; their actual bytes are now
included at their ordinary project paths. SQLite is unchanged. Four M3 locks
are the distributed seeds restored by unzipping, not dependency upgrades; their
exact Cargo-normalized alternatives are already bound to the passing native
receipt. `m3/packaging/mac-lock-bindings.json` accepts only those known pairs.
The existing distributed seeds and protected M2 files remain unchanged.

## Build on the Mac

Close the running app and merge this project update, keeping vendor, .venv,
node_modules and target caches. From the project root:

```sh
.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview
```

The first release compilation may take several minutes. Stage names are printed
and per-stage logs are written into that folder. The runner requires existing
Cargo/npm dependencies; it never runs npm install, npm ci, cargo update or fetch.
Cargo runs offline. If a required cached archive is missing, the report records
the failure rather than relaxing a lock or installing a different version.

Send `m3-shell-out-mac-preview/report.json` first. If it reports
`Mac_preview_built_GUI_checks_pending`, the copied app is:

```text
m3-shell-out-mac-preview/Mdict Studio Pro Preview.app
```

No app binary needs uploading. The runner does not launch the app automatically.
A successful build is not yet standalone runtime acceptance.

## Build contract

- A separate `src-tauri/tauri.preview.conf.json` enables only the `.app` target,
  with preview product name and `com.mdictstudio.pro.preview` identity. The
  ordinary development config still has bundle.active false.
- The override does not replace app security or build settings. Release CSP,
  opaque dictionary iframe sandbox and native capabilities are inherited.
- Tauri build runs with `--no-sign`, `--ci`, a config override, and forwarded
  Cargo `--locked --offline`. Apple signing/notarization environment variables
  are removed from this build subprocess. No signing/notarization is requested;
  this is a local development artifact, not a distribution release.
- Before building, exact reviewed lock identities and protected M2 identities
  are checked. Existing direct node_modules package versions are compared with
  the reviewed frontend lock. Transitive installed file contents are not audited;
  no clean-install, bit-reproducible-build or supply-chain guarantee is claimed.
- Offline Cargo metadata may prune the four M3 seeds. Registry identities and
  checksums are checked, then all seven locks must match their exact recorded
  post-normalization hashes. Desktop metadata and the build are locked. A new
  hash causes a refusal rather than silent approval.
- Frontend tests run before Tauri's normal frontend check/build. Sources and all
  324 protected backend identities are checked afterward. Rust tests are not
  rerun solely for this packaging step; the report distinguishes compilation
  from test execution.
- Cargo uses the project's existing src-tauri/target tree for caching. Only after
  a successful build is the app copied into a fresh output directory. Info.plist
  identity, executable existence/permissions, file hashes and contained symlinks
  are checked; the source and copied inventories must agree.
- The original RGBA PNG remains. A minimal ICNS container embeds its exact 256px
  PNG bytes for the Mac bundle, without changing the icon pixels.

The authoring environment has no Rust/macOS toolchain, so local checks cover
lock policy, artifact inspection/refusals and configuration boundaries. Native
compilation and bundle creation subsequently passed on the user's Mac; the
scoped standalone GUI sequence is recorded below. The host build qualifies only its reported
architecture; an Intel-Mac run does not qualify Apple Silicon or a universal app.

## Standalone checks after build review

Quit `tauri dev` and its dev server before launching the copied preview. Open the
.app from Finder, then check startup without a terminal/server, a representative
native dictionary build/read or Database workflow, rendered preview under the
release CSP, appearance/language settings and clean quit/reopen. Development
presets may not appear under the separate preview app/WebView identity. Optional
Python converters still use a user-selected external interpreter and dependencies;
Python and the project fixtures are not silently bundled. No dictionary source
file, user preset or private log is copied into the app by this override.

Do not repeat the completed Database closeout or all reader benchmark batches.
Packaged launch and representative workflow checks are a new environment check,
not a reopening of accepted source-identical format qualification. Full M3,
original-app parity, wider resource behavior, signing/notarization, updater,
other platforms and production release remain separate.

## Official command references

The Tauri v2 CLI documents config merging, the app bundle target and the no-sign
option; these were checked when preparing this runner:

- https://v2.tauri.app/reference/cli/
- https://v2.tauri.app/develop/configuration-files/
- https://v2.tauri.app/distribute/

## First build preflight correction

The package-179 Mac attempt passed every source/lock check, then stopped before
compilation: full desktop cargo metadata requested an uncached Android crate.
The desktop preflight now uses --no-deps to inspect the root manifest without
requiring dependency source archives for unrelated platforms. All seven exact
lock identities and the real build's --locked --offline flags remain enforced.
See evidence/m3-mac-preview-first-attempt. Use a fresh output folder on retry:

```sh
.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview-v2
```

Cargo documents --no-deps here:
https://doc.rust-lang.org/stable/cargo/commands/cargo-metadata.html

## First standalone app build accepted

The package-180 Mac retry passes all eight stages, 40 Node tests, frontend
checking/build and the locked offline release .app build. The copied app and
original bundle hashes agree; locks and protected/source identities remain
qualified. See evidence/m3-mac-preview-build-qualified/report.json.

Open m3-shell-out-mac-preview-v2/Mdict Studio Pro Preview.app from Finder after
quitting the development app and stopping its dev server. No new build or project
update is needed for this launch check. The subsequent standalone GUI sequence passes Database loading, combined/marker
static styling, and Arabic/Light persistence after quit/reopen. See
evidence/m3-mac-preview-build-qualified/GUI-confirmation.json. This completes the
bounded local Intel Mac preview checkpoint; no rebuild is needed. Terminal
closure was not independently verified. The original build report retains its
historical GUI-checks-pending status; full M3 and production release remain open.


## Current refresh: plugin import and compatibility updates

The first accepted standalone binary predates simplified one-file plugin import, MDX v2 Encrypted=2 exports and the narrow v1.2 ASCII export path. Its earlier acceptance remains historical. The new refresh reuses the existing source-bound, locked offline Mac build workflow; no application code, dependency, bundle identity, CSP or signing setting is changed for this handoff.

Fully quit both the development app and any older preview, and stop the development server before applying the updated ZIP. Run from the project root using a fresh output folder:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview-v3
```

The build script runs frontend tests and the release build, verifies all seven reviewed locks, binds the current sources, and verifies that the copied .app matches its build bundle. Existing native tests were accepted with the compatibility gates; this packaging step does not claim to rerun them. Send `m3-shell-out-mac-preview-v3/report.json` first.

On a passing build, the new app will be at:

`m3-shell-out-mac-preview-v3/Mdict Studio Pro Preview.app`

Use this new path when launching from Finder; the older v2 app remains a separate historical build. A subsequent focused standalone check should verify Finder launch with the development terminal/server closed, the simplified plugin screen/import, a previously created SQLite dictionary with its stylesheet preview, and Python setup/trust behavior after quit/reopen. Development-app preferences need not transfer to the standalone app; choose the interpreter once if needed. Settings should persist within the same standalone app; plugin trust must reset.

This is still an unsigned local Intel Mac preview. Signing/notarization, other platforms, general legacy encodings, MDX v3, full parity and full M3 completion remain outside this checkpoint.

## Preview v3 accepted; wording refresh v4 pending

The v3 source-bound report passed all eight stages and produced executable SHA-256 `32eab5285ccec57decb42fc3ee9a8043a36c4592018b9b3ac324476693fda002`. The user confirmed the Finder/Terminal-close sequence and restart settings; screenshots show 310 records, the blue Legal Latin definition and the simplified plugin page in Arabic. Python was unconfigured in this standalone instance; standalone plugin execution is not claimed. See `docs/evidence/m3-mac-preview-v3-qualified/`. The v3 local preview checkpoint is complete.

The next targeted interface wording pass is described in [M3-UI-COPY.md](M3-UI-COPY.md); its new build uses `m3-shell-out-mac-preview-v4`. It changes translations/help only, without native/dependency changes.
