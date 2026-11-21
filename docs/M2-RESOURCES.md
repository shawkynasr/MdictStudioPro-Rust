# M2 resource APIs and staged extraction

This extends the Mac-qualified MDX foundation. The resource slice passed on
the user's Intel Mac (macOS 15.8.2) on 2026-10-29. All 13 gates passed: ten
commands returned zero and three controlled refusals returned one with the
required error code. All six resources matched independent Python reads, wire
audit, separate-process queries and extraction inventories. Source fingerprints
matched all 20 inputs; the unchanged report and exact snapshots are retained in
`docs/evidence/m2-resources-user-run`. Individual test logs were not supplied;
no test count or Linux runtime qualification is inferred. No rerun is requested.
M1 remains complete, and M2 remains partial. Earlier reports and exact qualified
source snapshots are retained unchanged.

## Public API

`Resource`, `ResourcePackRequest`, `pack_mdd`, `ResourceArchive`,
`resource_relative_path` and `ExtractionSummary` join the existing core API.
Resources are bytes, including zero, FF, empty payloads, fonts and UTF-8 content.
No text decoding, rewriting or implicit filesystem lookup occurs.

MDD output uses v2 framing, the qualified v6 writer, a stable sort with frozen
Unicode16 lowercase, and `StudioResourcePolicy=unicode16-resources-v1` plus the
pinned casing-data identity. Reopen requires those attributes, Verify checksums,
complete physical scan, budget compliance, monotonic order and a safe path plan.
Lookup uses the exact stored key; archive path aliases are not lookup aliases.
Foreign/unversioned MDD import is not implemented by this slice.

MDD packing validates before creating a sibling temporary file, writes bytes,
strictly reopens and compares every resource and metadata field, then persists
without replacing the destination. It uses the same progress and cancellation
contract as MDX. Existing core limits apply: 1,000 resources, 8 MiB decoded
key+payload, 1 MiB per payload and 16 MiB file size by default. These are work
budgets, not hard limits on engine decompression allocation or process RSS.
The previously locked libc 0.2.191 becomes a direct core dependency; no registry
package version or checksum changes, and no additional installation is needed.

## Extraction policy

Every resource key must form a portable relative file path. One leading slash
or backslash means the MDD archive root, never the operating-system root. Mixed
separators are accepted; UNC/repeated leading separators are rejected. Empty,
dot/traversal, control, colon/alternate-stream, reserved-device and ambiguous
trailing-dot/space components are refused. Components are at most 255 UTF-8 bytes,
paths at most 4,096 bytes and 32 components. This is intentionally conservative;
it does not claim to represent every legal archive filename.

Preflight checks every file and directory prefix for frozen-lowercase aliases,
separator aliases, duplicates and file/directory conflicts before writing. Other
filesystem-specific Unicode aliases are caught by exclusive creation inside the
private staging directory; an error discards the stage rather than merging names.

Extraction writes plain files inside a new private sibling directory. Directory
handles, mkdirat/openat and O_NOFOLLOW/O_EXCL anchor operations and refuse existing
nodes or links; resource content is never interpreted as a symlink, permission
record or executable command. Final directory publication uses renamex_np with
RENAME_EXCL on macOS, and renameat2 with RENAME_NOREPLACE on Linux. There is no
check-then-replacing-rename fallback. Unsupported platform/filesystem operations
return an error. Windows directory extraction is explicitly unsupported in this
slice, while portable filename preflight remains useful for future support.

Ordinary errors or pre-commit cancellation remove the stage and leave the final
destination absent. Existing files, directories and dangling symlinks are refused,
including a destination created during the job. A completed publication stays a
success if cancellation arrives afterward. SIGKILL/power-loss orphan cleanup,
directory fsync durability, hostile same-user interference with the output parent,
and arbitrary network-filesystem behavior are not qualified. Use a caller-owned
trusted parent. Individual engine calls and per-file writes remain synchronous;
cancellation runs at phase/resource checkpoints.

## Reproduce only when needed

Update in place, keeping .venv/vendor and existing output folders:

```sh
cd "$HOME/Downloads/mdict-studio-m0-m1"
.venv/bin/python scripts/m2_resources.py --output m2-resources-out
```

The runner checks pinned dependency/data reuse, runs the M2 workspace tests,
builds one small six-resource MDD and extracts it. It independently compares
Python resource bytes, v2 wire checks and exact extracted file inventories,
then reopens resources/extracts from separate processes. Controlled refusals for
an existing destination, traversal and case-alias packing must return the right
structured error, not a panic or unrelated parser failure. No M1, real-corpus,
stress or native-reader batch is requested. The MDX unit tests run as a small
regression within the changed M2 workspace.

New Rust tests exercise byte/empty/Unicode resources, exact lookup, unsafe paths,
device names, prefix/case collisions, budgets and strict corruption rejection;
also extraction cancellation, empty/nonempty destination races, dangling
destination links, staged symlinks, actual-filesystem Unicode aliases and late
cancellation. The user-run Rust workspace test command passed on macOS. Rust was
not executed in the authoring environment, where Rust/Cargo remain absent.

Return `m2-resources-out/m2-resources-report.json`, plus its named log on failure.
Do not import these automation fixtures into dictionary readers.

The CLI adds `mdd-pack REQUEST.json OUTPUT.mdd`, `resource FILE.mdd KEY`,
`extract FILE.mdd NEW_DIRECTORY` and `mdd-smoke NEW_DIRECTORY`. JSON resource
objects contain `key` and a byte-array `bytes` field. Title and description use
the current single-line metadata contract; there is no new stylesheet serializer.

## Platform references

- [Linux rename/renameat2 interface](https://man7.org/linux/man-pages/man2/rename.2.html)
- [Apple exclusive renaming capability](https://developer.apple.com/documentation/foundation/urlresourcevalues/volumesupportsexclusiverenaming)
- [libc bindings for the Apple target](https://docs.rs/libc/latest/x86_64-apple-darwin/libc/)
- [Rust Unix filesystem implementation and C vararg mode promotion](https://doc.rust-lang.org/src/std/sys/fs/unix.rs.html)
- [Microsoft portable filename and device-name rules](https://learn.microsoft.com/en-us/windows/desktop/fileio/naming-a-file)
