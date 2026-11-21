# Standalone built-in converter checks

The six built-in routes have native qualification and compile in preview v5. This focused check records actual standalone UI execution separately. It changes no application code, dependencies, caps or locks. Use the current Finder-launched preview v5; no download or rebuild is required to run the check.

## First check: CC-CEDICT

1. Open Converters and select the CC-CEDICT tile (not Convert with a plugin).
2. Choose input `/Users/shawky/Downloads/mdict-studio-m0-m1/m3/fixtures/cedict.txt`.
3. Leave the converter as CC-CEDICT. Output is TXT / UTF-8; no worksheet or Python interpreter is needed.
4. Set Save to to a fresh file, for example `/Users/shawky/Downloads/cedict-standalone-v5-1.txt`. This is a file, not a folder; do not pre-create it. If it already exists, use another filename.
5. Run Convert, then open Jobs and Collect receipt. Send the receipt and the resulting TXT file for comparison.

Expected: three output entries, in source emission order 字, 书, 書. The two source lines produce two primary entries plus one traditional entry. Both book entries have the same definition; 字 contains character and word definitions. No external CSS rendering check is requested here.

Source SHA-256: `463a04e1ad8ff8c3142e1456dc0fb529de2fa62affbe3dd70d4f70afd8e42dec`. The expected count comes from the frozen CC-CEDICT converter's simplified-key emission and distinct-traditional-key rule; no Rust execution is claimed in the authoring environment. The user's three-entry/885-byte receipt and attached output passed exact byte comparison; see evidence/m3-builtins-standalone-qualified/cc-cedict.json. This CC-CEDICT standalone check is complete. This tiny fixture check is not another full CC-CEDICT scale benchmark.

## Remaining routes

MOE Mini, MOE Idioms and MOE Concise standalone exact outputs are accepted. MOE Revised and MOE Revised WFG standalone fixture checks are now accepted as recorded below. Prepare their precise workbook/worksheet handoffs from existing fixtures and source contracts before requesting those runs. Do not ask for unavailable morphology source files or repeat accepted dictionary reader benchmarks. Full M3, public release and other-platform qualification remain open.

## Completed check: MOE Mini

Use the same existing v5 standalone app. Select Converters → MOE Mini. Choose `/Users/shawky/Downloads/mdict-studio-m0-m1/baseline/xlsx-reader-kit/moe-rows.xlsx`. Set Worksheet to `Sheet` (capital S), the exact sole worksheet name in this existing workbook. Set Save to to a NEW file, for example `/Users/shawky/Downloads/moe-mini-standalone-v5-1.txt`. No Python setup is needed by this built-in native converter. Click Convert, then Jobs → Collect receipt. Send the receipt and resulting TXT file.

Expected: two output entries, 和 then 字, 2,785 bytes, primary_entries 2, no aliases/traditional entries. Expected source SHA-256 `4d16e493d7686aa4db03b2619e023f81bbd93d9940ff4369fed91192c4fd5f1a`. Expected output SHA-256 `0f99434d534f8949d922fffceb012620ef8a64cb783e38325525a71345f888b3`, matching baseline/expected/moe_mini.txt. The authoring check ran the captured original Python converter on this exact workbook and compared all records with that existing baseline; it does not claim fresh Rust or standalone GUI execution. No native benchmark or app rebuild is requested.

The user supplied the matching two-entry/2,785-byte receipt and TXT file; exact baseline bytes and hashes passed. The receipt records one skipped source row. See evidence/m3-builtins-standalone-qualified/moe-mini.json. No repeat is requested.

## Completed check: MOE Idioms

Use the same preview v5 app and the same input workbook `/Users/shawky/Downloads/mdict-studio-m0-m1/baseline/xlsx-reader-kit/moe-rows.xlsx`. Select Converters → MOE Idioms and set Worksheet to `Sheet` (capital S). Choose a NEW output file `/Users/shawky/Downloads/moe-idioms-standalone-v5-1.txt`. Click Convert, then Jobs → Collect receipt. Send the receipt and TXT file. No Python setup, source update or rebuild is required.

Expected: two entries, 和衷共濟 then 一字千金, 2,191 bytes. Source SHA-256 remains `4d16e493d7686aa4db03b2619e023f81bbd93d9940ff4369fed91192c4fd5f1a`. Expected output SHA-256 `f1e2fdb6ef77bed7aeee1ee66989fa00c3ac662e80a63712c2295916b157ac0c`, matching baseline/expected/moe_idioms.txt. The authoring check ran the captured original Python converter against this exact workbook and compared all records with that baseline. Rust/native acceptance is reused; standalone GUI execution of MOE Idioms remains pending.

The user supplied the two-entry/2,191-byte receipt and matching TXT file. Exact baseline bytes and hashes passed; the receipt records one skipped source row. See evidence/m3-builtins-standalone-qualified/moe-idioms.json. No repeat is requested.

## Completed check: MOE Concise

Use the same preview v5 app and input `/Users/shawky/Downloads/mdict-studio-m0-m1/baseline/xlsx-reader-kit/moe-rows.xlsx`. Select Converters → MOE Concise and set Worksheet to `Sheet` (capital S). Choose a NEW output file `/Users/shawky/Downloads/moe-concise-standalone-v5-1.txt`. Click Convert, then Jobs → Collect receipt. Send the receipt and TXT file. No Python setup, source update or rebuild is required.

Expected: two entries, 和 then 字, 1,074 bytes. The 和 definition combines both pronunciation rows. Source SHA-256 remains `4d16e493d7686aa4db03b2619e023f81bbd93d9940ff4369fed91192c4fd5f1a`. Expected output SHA-256 `d6bffa874e702914802c5e8a574e5d83930ab723f2e4655b739b1555b2e6468a`, matching baseline/expected/moe_concise.txt. The captured original Python converter was run on this exact workbook and its records matched the existing baseline. This fixture has single-valued reference fields, so no set-order normalization changes its expected bytes. Existing native qualification is reused; standalone MOE Concise GUI execution remains pending. This does not repeat the full official-dataset benchmark.

The user supplied the two-entry/1,074-byte receipt and exact matching TXT file. See evidence/m3-builtins-standalone-qualified/moe-concise.json. No repeat is requested.

## Completed checks: MOE Revised and MOE Revised WFG

User requested both remaining routes together. Use preview v5, input `/Users/shawky/Downloads/mdict-studio-m0-m1/baseline/xlsx-reader-kit/moe-rows.xlsx` and worksheet `Sheet` for each run. No source update, Python setup or rebuild is required.

| Converter tile | NEW output file in Downloads | Expected entries | Bytes |
| --- | --- | --- | --- |
| MOE Revised | moe-revised-standalone-v5-1.txt | 4: two primary entries 和 and 字, plus 和平 and 和諧 redirects to 和 | 1,925 |
| MOE Revised WFG | moe-revised-wfg-standalone-v5-1.txt | 2: 和 and 字, no aliases | 1,452 |

Run Convert for each; collect both receipts in Jobs and send them with both TXT files. Use another filename if the proposed destination already exists. Source SHA-256 for both remains `4d16e493d7686aa4db03b2619e023f81bbd93d9940ff4369fed91192c4fd5f1a`.

The authoring check ran the captured original Python converters on the exact workbook and compared all records with baseline/expected/moe_revised.txt and moe_revised_wfg.txt. Revised baseline SHA-256 is `32688acf6251bb8536d585a20e82ae668423184ff7017b7aeed96936bb864a4f`; WFG is `a955bbdeb60344e79f2127bb4ac19c65ff3c9a24b9162a2b85dbe8dc59bd7c04`. Revised aliases originated from Python set iteration, so comparison permits only the already documented alias ordering normalization while retaining their exact targets and all other content. Do not require raw Revised SHA equality if only those aliases change order. Existing native qualification is reused; both standalone GUI checks remain pending. These checks close only the six built-in converter fixture coverage, not full M3 or public release.

Both user receipts and TXT files passed. Revised content matches after only the documented alias-order normalization, and its attachment hash matches the receipt. WFG bytes exactly match the reference and receipt hash. All six standalone fixture checks are accepted; see evidence/m3-builtins-standalone-qualified/decision.json. No routine repeats are requested. Earlier pending wording describes the handoff before these results.
