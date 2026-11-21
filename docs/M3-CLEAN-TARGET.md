# Clean-target test kit preparation

Same-Mac relocation of preview v6 is accepted from the copied-bundle verification, exact three-entry/885-byte output and user confirmation of the Finder-launched copied path. This does not establish clean-machine behavior. Current next work needs an available target: another Intel Mac without the development setup is preferred for clean-machine evidence; an existing fresh macOS account on the same Mac provides narrower fresh-user evidence because global tools/libraries are shared. Neither an account nor another machine is assumed available, and no account is created automatically. Apple Silicon/Rosetta is a separate architecture/runtime target, not an Intel clean-machine substitute.

The new scripts/m3_preview_testkit.py prepares a small, source-bound test ZIP on the user's Mac from the already reviewed v6 app. It changes no app code or build settings. It copies the app and tiny CC-CEDICT fixture into a fresh output directory with a plain README and bundle identity, archives with ditto, extracts into another new directory and compares the full bundle and fixture/README again. It launches nothing, changes no user/system settings, installs no dependencies, removes no quarantine, and overwrites no existing output directory. Only syntax/help validation ran in the authoring environment; macOS copy/archive and target launch remain pending.

With app/dev server closed, put the helper into the existing project's scripts folder and run:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_preview_testkit.py --output m3-shell-out-clean-test-kit-1
```

Send m3-shell-out-clean-test-kit-1/report.json before target handoff. The script produces Mdict-preview-v6-Intel-test.zip in that output folder. Only this test ZIP needs to go to the chosen target; do not transfer the source project, development caches, user settings or real dictionaries. No Python/helper script is needed by the recipient for the built-in app test: return the app receipt and output TXT for reviewer comparison.

The README requests OS/hardware/transfer-route notes, Finder launch, CC-CEDICT conversion with the included fixture into a new user-writable file, and normal Quit/reopen. Expected output is three entries/885 bytes. If macOS blocks launch, record the exact message and stop; a blocked unsigned app is not fixed by suppressing Gatekeeper in this test. This kit is unsigned and local; signing/notarization, distribution policy, clean-target execution and other-platform support remain open. If neither target is available, retain the kit and mark the external test blocked rather than substituting more same-user repeats.

## Prepared kit report and community-testing direction

The attached Mac report matches the reviewed v6/fixture identities and reports a successful archive round-trip. The 6,046,901-byte kit checksum is retained in evidence/m3-clean-target-kit-built. No archive bytes or independent target result were attached. The user indicated no other Intel Mac was available and chose to proceed toward GitHub community testing. Clean-machine testing remains pending, and a fresh account has not been silently substituted. Experimental prerelease materials are prepared in releases/PUBLISHING-CHECKLIST.md; no publication has occurred.
