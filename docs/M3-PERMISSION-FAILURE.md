# Controlled output permission failure and retry

Use existing preview v6. Only the new diagnostic script is required; no native app code changes or rebuild. The helper creates a new project-local test directory and restricts only its own locked child to mode 0500. It probes actual write refusal under the running account and refuses to qualify preparation if permission bits are bypassed (for example by a privileged account). Existing files and their permissions are not changed.

1. Put scripts/m3_permission_check.py in the existing project's scripts folder. In Terminal:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m3_permission_check.py prepare
```

Use a fresh --output m3-shell-out-permission-2 consistently if the default directory already exists; do not overwrite it. Stop on any preparation error. The helper prints the exact input and destination.

2. In preview v6 open Converters → CC-CEDICT. Input `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/cedict.txt`. Set Save to `/Users/shawky/Downloads/mdict-studio-m0-m1/m3-shell-out-permission-1/locked/result.txt` (use the helper's printed destination if a different --output was used). Enter this path directly rather than trying to create a file in Finder's save dialog. Click Convert. Expect permission denied and no final output. Send the exact error.
3. Without restarting the app, run:

```sh
.venv/bin/python scripts/m3_permission_check.py unlock
```

It records the previously locked directory entries, checks source identity and restores 0700 ONLY on the original identity-checked test directory. If it reports unexpected output or residue, stop and send the observation. No deletion occurs.

4. In the SAME app session retry the same CC-CEDICT input and exact output path. Expect success: 3 entries, 885 bytes. Collect the receipt.
5. Run:

```sh
.venv/bin/python scripts/m3_permission_check.py verify
```

Send report.json from m3-shell-out-permission-1 and the GUI error/success receipt. Verification requires the pre-retry directory to have been empty, unchanged source, final 885-byte exact expected TXT hash, and no residual directory entries besides result.txt. It does not infer the GUI error wording or same-session behavior; those require the user's report. The helper's syntax/help checks pass locally; real macOS permission enforcement and app behavior remain pending. This check does not qualify disk-full, volume failures or every error path.

## Observed acceptance

The user supplied the expected io/permission-denied error with publication_uncertain false. Unlock recorded no destination or temporary entries and unchanged source. An initial verification ran before output existed and was not accepted as a recovery result; it was preserved before retry. The subsequent conversion receipt reports 3 entries/885 bytes, and final verification passed the exact expected output hash with unchanged source and no extra entries. See evidence/m3-permission-failure-qualified/GUI-confirmation.json. No restart was requested or reported during the checklist sequence; session continuity is not independently measured by the helper. No routine repeat is requested.
