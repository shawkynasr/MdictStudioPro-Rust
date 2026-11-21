# Early MDX size preflight

This read-only Python check screens candidates before another full sizing run. It does not change dictionaries, native limits or production code. Close the app before updating the project, then run from its root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
.venv/bin/python scripts/m4_database_preflight.py
```

Choose an MDX in the macOS file picker. Alternatively pass `--mdx '/absolute/path/to/dictionary.mdx'`. Outside macOS a path is required. The standalone check prints JSON and creates no database, export or sizing directory. It needs the same independent mdict-utils reader as previous verification scripts; no Rust build or desktop gate runs.

The JSON identifies the **first observed violation** as one of:

| Name | Existing ceiling |
| --- | --- |
| `file_bytes` | 134,217,728 bytes (128 MiB) |
| `record_count` | 100,000 records |
| `headword_bytes` | 4,096 UTF-8 bytes per headword |
| `definition_bytes` | 1,048,576 UTF-8 bytes per definition |
| `decoded_text_bytes` | 33,554,432 UTF-8 bytes across headwords and definitions |

`first_issue.observed`, `maximum` and `record_ordinal` show where a decoded limit was crossed. Byte lengths refer to UTF-8 decoded text, regardless of the original MDX encoding or compressed file size. Invalid/empty headwords and an empty dictionary are reported separately as invalid input. The scanner checks the bounded MDX header extent/checksum and tracks the source SHA-256 before and after scanning.

When a limit is crossed, it stops and sets `scan_complete=false` and `counts_scope=observed_prefix_only`. These are exact measurements of the prefix it examined, **not final totals for the whole dictionary**. The offending row is included in observed counts and bytes. If multiple bounds cross together, only the first checked violation is reported. File-size refusal uses `counts_scope=not_decoded`. No rejected prefix is exported or used as a substitute dictionary. The check may still need time to read/decompress data up to the first violation; it does not promise instant checks or an OS-enforced memory bound on the independent reader.

If all rows pass, `status=fits_size_profile`, `scan_complete=true` and the counts cover the whole dictionary. This is size/headword-shape screening, not native format compatibility, conversion success or completion of checkpoint 2. Native jobs still verify those properties.

The full sizing runner now performs this same preflight first:

```sh
.venv/bin/python scripts/m4_database_sizing.py --output m4-database-out-sizing-v3
```

A rejected candidate writes its preflight details to that directory's `report.json`, returns exit code 1 and runs **no** desktop gate, Rust build or synthetic/native test. A size-fitting candidate proceeds with the existing native tests and real import/lookups/export. The report schema is `studio-m4-database-sizing-v2`. Use a fresh directory each time.

Local tests verify UTF-8 byte accounting, first-violation stopping, partial/whole counts, duplicate and whitespace preservation, header/hash checks and early sizing rejection before any native lookup. Real MDX preflight execution remains pending the Mac run. Earlier sizing evidence is retained in `evidence/m4-database-sizing-boundaries-qualified`; it qualifies synthetic boundaries and native refusals, not a successful real dictionary or this new preflight.
