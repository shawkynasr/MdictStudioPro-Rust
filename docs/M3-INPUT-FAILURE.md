# Standalone unavailable-input and subsequent success check

Use existing preview v6; no rebuild, download, Python plugin or native benchmark is needed. This checks a failed native input-open followed by a successful job in the same app session. Native failure/refusal tests do not substitute for this explicit standalone UI observation. No original file is renamed, removed or permission-modified.

1. Dismiss finished Jobs if retained slots are full. Open Converters → CC-CEDICT.
2. Expand More options. In the editable input path field enter `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/does-not-exist-v6.txt`. This path must not exist; do not create it.
3. Set Save to `/Users/shawky/Downloads/missing-input-v6-1.txt`, a NEW file. Click Convert. Expect an unavailable-file error (either submission refusal or failed job), no app crash, and no output file. Send the exact error. Do not require a guessed error code or translated phrasing.
4. Without quitting, return to CC-CEDICT. Use Choose to select `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/cedict.txt`. Keep the SAME unused output path `missing-input-v6-1.txt` and convert again. If a file unexpectedly exists after the failed attempt, stop and report it instead of overwriting or choosing a different name.
5. Collect the successful receipt and send it with the initial error. Expected success: 3 entries, 885 bytes, source SHA-256 463a04e1ad8ff8c3142e1456dc0fb529de2fa62affbe3dd70d4f70afd8e42dec. This repeat establishes worker/UI recovery after failure; earlier CC-CEDICT compatibility/scale checks remain accepted.

A pass establishes only this missing-input failure/recovery path. It does not establish permission-denied, disk-full, read-only-volume, clean-machine installation, every locale/error combination, broader crash phases or other-platform behavior. All remain separate where applicable.

## Scoped observed result

The user supplied the expected io/not-found error followed by a successful three-entry/885-byte receipt with matching fixture source hash. Missing-input handling and subsequent valid-input success are accepted. The user did not explicitly confirm that both attempts used the same output filename, so absence of partial output is not independently established by that receipt. See evidence/m3-input-failure-qualified/GUI-confirmation.json. No routine repeat is requested.
