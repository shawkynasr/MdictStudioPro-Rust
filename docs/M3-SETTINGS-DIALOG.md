# Compact Settings dialog

Status: implemented; authoring checks run during packaging. Native Mac compilation and WebKit interaction checks pending. No native/runtime behavior or dependency changes.

## Behavior

Settings is a modal dialog over the current workspace. It contains Language, Appearance and Done. It is not a separate page and does not insert a panel above Build. Opening it never assigns a different workspace view, and the underlying form stays mounted so unsent values and converter selection remain intact. The native `dialog.showModal()` provides background inertness, a dimmed backdrop and keyboard focus containment. The native cancel behavior closes it with Esc; Done calls `close()`. The close event clears dialog state and explicitly restores focus to the Settings button.

The Settings trigger is identified as a dialog action with expanded state; it does not create a second selected sidebar page. The original workspace remains selected behind the dimmed backdrop. Language and theme continue using the existing bindings and preference persistence. The dialog inherits Arabic RTL and the current theme. Native plugin file drops are ignored while Settings is open, matching the modal background behavior.

No new preferences are added just to fill a settings page. Background jobs and open readers retain their existing lifecycle. The prior full-page implementation was never delivered; the latest shipped v4 preview still has the reported inline-panel behavior.

## Build and focused verification

Quit the preview and stop any development server before applying the updated ZIP. Use a fresh output directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_mac_preview.py --output m3-shell-out-mac-preview-v5
```

Send `m3-shell-out-mac-preview-v5/report.json`. After a passing build, launch that folder's `Mdict Studio Pro Preview.app` from Finder and check:

1. Enter a temporary dictionary name in Build, then open Settings. The controls appear in a centered dialog with a dimmed, non-interactive background.
2. Tab and Shift+Tab stay within the dialog. Done closes it and focus returns to Settings; the Build name remains unchanged.
3. Reopen and close with Esc. The same form remains. Repeat from Extract to ensure opening Settings does not switch to Build.
4. Switch English/Chinese/Arabic and Light/Dark inside the dialog; labels/theme update, Arabic is RTL. Close and reopen the app to verify the existing preferences persist.

No conversion jobs are needed for this regression check. Native `dialog`/WebKit keyboard behavior is explicitly a Mac GUI check, not established by the existing frontend logic tests.

The v4 report is retained at `docs/evidence/m3-mac-preview-v4-built/report.json`. Its eight stages pass and Svelte reports zero errors/warnings, but the supplied screenshot documents the Settings inline-panel navigation defect; v4's Settings GUI behavior is not accepted. No historical report is relabelled. Full M3 and production release remain open.

## Observed Mac acceptance

The v5 source-bound build passed all eight stages, 51 frontend tests, Svelte zero errors/warnings and bundle identity/copy checks. Screenshots show the compact modal in English/Light and Arabic/Dark, with dimmed background and focus on a selector. The user explicitly confirms Esc closes only the dialog and Tab navigates inside it; the full app was deliberately restarted to check preferences. Only these observed checks are accepted. Done/focus restoration, full forward/reverse focus loops and a nonempty draft-preservation check are not independently confirmed. See `docs/evidence/m3-settings-dialog-qualified/`. The next separate gap is standalone Python converter execution; no new build is requested.
