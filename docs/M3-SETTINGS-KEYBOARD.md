# Remaining Settings keyboard and Chinese visual check

Use the existing Finder-launched preview v6. No download, rebuild, conversion or additional restart test is requested. English/Light, Arabic/Dark, Esc and basic Tab navigation were already observed in v5; earlier preference restart checks remain accepted. This focused handoff addresses remaining Done/focus-return, forward/reverse focus containment, nonempty draft, workspace preservation and Chinese visual evidence.

1. In Build enter temporary dictionary name `keyboard-check 字 مرحبا`. Do not submit a build.
2. Open Settings. Choose Chinese (中文) and Dark. Capture one screenshot of the dialog so label visibility, layout and focus can be reviewed.
3. Press Tab several times, then Shift+Tab several times. Focus should remain among dialog controls; the dimmed background should not receive focus. Report what actually receives focus, including skipped controls, instead of assuming a complete accessible cycle.
4. Click Done (the translated Done button). After the dialog closes, press Space without clicking elsewhere. It should reopen Settings because focus returned to its trigger. Press Esc to close it.
5. The Build name should still be `keyboard-check 字 مرحبا`. This is in-memory modal preservation, not draft persistence across quitting.
6. Switch to Extract, open Settings and close it with Done or Esc. Extract should remain the active workspace; Settings must not switch the app to Build.

Send the Chinese screenshot and confirm focus containment, Space reopening Settings, retained draft and Extract remaining active. If any step fails, report its actual behavior and stop that part. No exhaustive accessibility or all-locale acceptance is implied by this check.

## Scoped acceptance

User confirmed all steps completed and supplied two screenshots. The images show Chinese/Dark Build, the retained multilingual draft and Settings trigger focus; the Settings dialog itself and Extract are not pictured. Forward/reverse containment, Done/Space reopening and Extract preservation are accepted from the user's explicit completion confirmation, not independently inferred from those images. See evidence/m3-settings-dialog-qualified/v6-keyboard-confirmation.json. No exhaustive accessibility claim or routine repeat is requested.
