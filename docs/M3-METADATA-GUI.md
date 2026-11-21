# Dictionary Tools: metadata-only copies

Dictionary Tools now has a collapsible **Edit dictionary metadata** panel in
English, Chinese and Arabic. Choose an MDX/MDD, select its file type, enable
Replace on the fields to change, then Save edited copy. A checked empty field
clears its value; an unchecked field remains unchanged. MDX exposes title,
description and numeric stylesheet. MDD exposes title and description.

Use opened dictionary copies the current MDX path and full header values into
the form. It does not enable replacements. Close the MDX and any attached MDD
before saving; the form remains populated after readers close. For a file
selected directly, preserved fields do not need to be loaded or entered.

This is the existing M2 metadata engine, with its existing limits: 1,000
physical entries/resources, 8 MiB decoded keys plus bodies/payloads, 16 MiB
archive, 64 KiB serialized UTF-16 header, 4 KiB key and 1 MiB individual body.
This route is intended for small supported unencrypted v2 dictionaries.
Larger streaming metadata rebuilds remain future work. The 250,000-record
export/packing profile does not apply here.

The background publication uses the M3 coordinator's existing exclusive
384 MiB logical / 3 GiB temporary reservation. Readers block admission. The
same job queue, cancellation token, progress, shutdown, Take and Forget apply.
No separate unmanaged worker or queue is introduced. No M2 files or caps change.

The backend snapshots the source, retains structural and unknown header
attributes, writes the changed header and checksum, and copies all remaining
data-section bytes verbatim. It reopens the staged copy and verifies header
and physical records before no-clobber publication. It never overwrites the
source or an existing destination. Opening an edited copy in Tools requires
a new index; the previous index belongs to the original source digest.

Numeric styles are MDX ID/opening-HTML/closing-HTML triplets, not CSS. The
qualified wire profile requires LF separators and a final LF. Duplicate IDs,
CRLF style triplets, unsupported XML controls and unresolved numeric markers
are rejected rather than repaired. Plain title/description edits still require
the existing stylesheet and every numeric marker to satisfy this profile.
Textarea input uses browser LF line endings; callers of the native API receive
the original backend validation, without implicit normalization.

## Checks

New native regression coverage exercises the actual command route, UTF-16
MDX with duplicate keys and numeric markers, multilingual title edits,
preserved descriptions, cleared MDD descriptions, byte-identical data
sections, source preservation, existing-destination refusal, dangling-marker
refusal, shared reader admission and cancellation during copy/precommit.
These tests are authored; Rust and Svelte execution is unavailable in the
authoring environment. Run the complete native check from the project root:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v12
```

Then launch from the desktop directory:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

For one visual check, use the previously built five-record MDX, change only
its title and description, and save a new copy. In MDict and GoldenDict,
confirm the changed metadata and all five records. To test stylesheet edits,
use a small dictionary with known numeric markers, preserve each referenced
ID and change its wrapper formatting. Cancellation before publication and
invalid edits must create no output; an existing destination must stay intact.
