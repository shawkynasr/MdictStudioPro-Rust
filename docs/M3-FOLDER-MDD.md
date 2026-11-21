# Build MDD directly from a resource folder

Version 126, 2026-11-12. Native qualification pending; M3 remains incomplete.

Build → MDD now defaults to a folder picker. Select a resource folder, choose a
new MDD output and build. Nested resource files become root-relative MDD keys,
for example images/photo.png becomes \images\photo.png. No user-authored JSONL
manifest is required. More options retains JSONL manifest input for advanced use.
MDX TXT/JSONL routes and automatic .mdx/.mdd output suffixes remain available.

The user previously confirmed UTF-8/UTF-16 TXT-built MDX and Block spool output
in MDict/GoldenDict, the five-record fixture, a larger CC-CEDICT MDX, destination
refusal, malformed TXT with no output, and cancellation with no output. Those
observations are retained as user attestations; they do not qualify this new
folder route or prove every native test ran.

## Merge and check

Keep .venv, vendor, node_modules, targets, real inputs and previous outputs. From
the project root run the new source-bound checks (use a new output name):

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v9
```

The existing txt-runtime test step now includes folder tests; native adapter,
frontend and desktop checks follow. No dependency reinstall is needed with the
previous caches. If it fails, send m3-shell-out-v9/m3-shell-report.json and its
failing step log. Existing M1/M2 qualification batches need not be repeated.

Launch after checks pass:

```sh
cd m3/desktop
npm run tauri dev
```

1. In Jobs, use Dismiss finished jobs if prior test history has reached the
   eight-job retention ceiling. This discards those job records/receipts, while
   keeping published files. The app now directs retention_full errors to Jobs.
2. Close both readers in Dictionary Tools. In Build choose MDD and select the
   folder m3-shell-out-preview-fixture/assets from the earlier preview fixture.
   Select the assets folder itself, which contains css and images; do not select
   resources.jsonl or the entire fixture directory containing MDX/index files.
3. Choose a NEW destination outside that folder, such as folder-test.mdd, and
   build. Expect one job, source_format resource_folder, two files in its receipt.
   The manifest is generated privately. File count excludes macOS metadata.
4. Put the output beside a COPY of the existing matching preview.mdx; give both
   the same basename (folder-test.mdx / folder-test.mdd). Open in MDict and
   GoldenDict, then query resources. Expect the blue card, image and background.
   This fixture proves CSS/image packaging; font/audio require real matching assets.
5. Optionally index folder-test.mdd in Dictionary Tools and attach it beside the
   preview MDX using its own matching index. Query resources and compare rendering.
   Build indexes before opening readers, as in the previous preview tests.
6. Retry the same output: destination_exists, existing output unchanged. Try an
   empty folder: typed failure, no output. For cancellation use a larger folder
   WITHIN the profile limits, choose a fresh destination and cancel while running;
   no output should appear before commit. Completed success wins over late cancel.

## Included files, names and limits

All ordinary files are included recursively, including extensionless files,
fonts, CSS, images, audio and other binary content. File bytes are not decoded or
rewritten. Empty files are retained, while empty directories create no MDD keys.
Only .DS_Store, .localized and names starting ._ are excluded as macOS metadata;
other dotfiles are included. Choose a folder containing the intended resources.
Audio/SVG can be archived; the current static preview still does not render them.

Observed symlinks, special files, non-UTF-8 filenames, ambiguous separators and
nonportable names fail the build rather than being silently included or renamed.
Path validation reuses the accepted core policy: <=32 components, <=255 bytes
per component, no traversal/control characters/reserved device names, no trailing
space/dot. Generated keys are <=4 KiB. Case aliases are refused using the pinned
Unicode16 lowercase policy, including directory aliases. This is the existing
policy, not a claim of equivalence to every filesystem's normalization rules.

Current folder profile: at most 100,000 scanned filesystem entries (including
folders/ignored names); 32 MiB cumulative scan-plan charge; 16 MiB generated
manifest; 1 MiB per file; 32 MiB combined decoded resource keys and payloads.
The existing MDD packer's descriptor, record-count and 128 MiB output limits also
apply. Do not infer multi-gigabyte audio archive support from folder selection.
Limit errors leave no newly committed MDD. No limits are widened automatically.

## One coordinated job

A folder_packing request/receipt is added to the existing M3 desktop coordinator.
It holds the conservative exclusive block-packing reservation (384 MiB logical
memory and 3 GiB temporary space) across both enumeration and packing. One native
queue entry, job ID, cancellation token and receipt cover the operation. No new
worker pool or detached frontend preparation work is introduced. The reservation
is application accounting, not an OS hard memory limit.

Enumeration sorts each directory for deterministic manifest output, caps collected
names before sorting, checks cancellation between directory entries, validates
paths and writes key/file rows into one private temporary manifest. Resource
payloads are NOT read by enumeration. Scan metadata gives an early size estimate;
resources can still change on disk before packing. This is not an atomic folder
snapshot, and the scanned byte count is not a content digest.

The unchanged accepted MDD packer snapshots the manifest, opens resources relative
to its root directory descriptor with no-follow checks, enforces actual byte
limits, writes and verifies staged output and commits without overwriting. Scan
checks are not a substitute for those payload-open checks. The manifest remains
alive until packing finishes and is removed on success, error or cancellation.
The nested packing receipt's source_sha256 describes that manifest; it is not a
hash of the directory's resource contents. The outer receipt reports included
files, visited directories, skipped metadata and estimated scanned file bytes.
There is no new fallible validation or cancellation check after a successful commit.
Windows folder packing remains outside the qualified Unix resource backend.

## Verification scope

Authored Rust tests exercise deterministic nested Unicode keys, exact binary and
empty-file extraction roundtrip, metadata preservation, overwrite refusal,
symlink/ambiguous-name refusal, empty input and lowered scan budgets; case aliases
where the host filesystem can represent them; scan/precommit cancellation and
late cancellation; and reader/exclusive-job admission with one-transfer receipts.
The coordinator's existing lifecycle/budget implementation and every accepted
M2 source identity remain unchanged. Core is now a direct local dependency, with
no new registry package version. Existing TXT/coordinator/adapter regressions run
in the same native check script.

Local Python/Node checks are separate from Rust/Svelte/native evidence. No native
execution, WebKit visual check or Rust compilation is claimed in the authoring
runtime, where Rust is absent and npm registry access was blocked.
