# Dictionary Tools: indexed redirects

Select a stored `@@@LINK=` entry and choose **Follow redirect**. The reader
shows the terminal definition using the same Rendered/Split/HTML preview and
attached MDD resources. **Stored source** returns to the original link body.
The target selector keeps duplicate physical records separate and shows their
ordinals. The chain lists each source key, source ordinal and target key.
Labels are available in English, Chinese and Arabic.

Resolution uses the selected source key **and ordinal**, then follows target
queries under the open index's policy: raw exact or exact-first header-guided
fallback. It introduces no wildcards, trimming or Unicode normalization.
`@@@LINK=` must begin at the first character. Its target can have at most one
final LF/CRLF, and must be nonempty, NUL-free, single-line and <=4 KiB UTF-8.
Stored definition text is never changed. The original reader snapshot is used
even if the public MDX/index path changes after opening.

M3 adds `m3/indexed-sessions`, a derivative of the accepted M2 session actor.
Ordinary page behavior and its inherited tests remain. Resolve jobs enter the
same actor queue, share cancellation, retention, result serialization, Take,
Forget, close and shutdown. The M3 coordinator aliases this new crate; all
324 accepted M2 source identities and admission caps remain unchanged.
There is no second dictionary open or thread per redirect hop.

Fixed resolver limits are 16 hops per branch, 4,096 physical visits, 256
matches per query, 256 terminal results, 8 MiB cumulative decoded lookup data
and 2 MiB raw terminal/chain data. The existing session serializer separately
enforces 2 MiB serialized reply and 8 MiB pool-retained replies. Duplicate
targets are fetched over all required 32-row pages. A missing target, invalid
target, cycle, limit or cancellation discards the entire resolution; no
successful-looking partial target list is returned. Cycles use physical
ordinals on the current branch, so two independent paths to the same terminal
record remain two results. MDD readers reject resolve requests.

The UI owns resolve jobs until their terminal results are collected/forgotten.
Changing selection or starting another lookup cancels the active resolve job;
stale success/error replies cannot replace the current selection. Cancelling
keeps the stored link visible. Preview security policy remains unchanged.

## Native check and fixture

The new session tests cover the actual index and actor, snapshot ownership,
duplicates/chains, single-transfer results, malformed/missing/cyclic links,
selected ordinal mismatch, running/pre-result cancellation, pagination,
branching and limit refusal. The inherited M2 session lifecycle tests also run.
Rust/Svelte execution is unavailable in the authoring environment; run on Mac:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1
python3 scripts/m3_shell.py --output m3-shell-out-v13
cargo run --manifest-path m3/native-adapter/Cargo.toml --example redirect_fixture -- m3-shell-out-redirect-fixture
```

The fixture command requires a new output directory and makes a nine-record
MDX with raw and header-guided indexes. It needs no Python environment or MDD.
Launch:

```sh
cd /Users/shawky/Downloads/mdict-studio-m0-m1/m3/desktop
npm run tauri dev
```

In Dictionary Tools select the generated `redirects.mdx`, `redirects-raw.idx`
and Raw exact, then Open indexed dictionary. Do not build another index over
the generated one.

| Lookup | Follow redirect should show |
| --- | --- |
| alias | Two target records; one hop to target |
| chain | Two target records; chain → alias → target |
| missing | redirect_missing; no resolved definition |
| cycle-a | redirect_cycle; no resolved definition |
| bad | redirect_target; no resolved definition |
| case-alias | redirect_missing under Raw exact |

Close the reader, select `redirects-header.idx` and Header-guided lookup, then
open again. `case-alias` should now reach the two lowercase target records.
Switching Stored source/Resolved definition must leave stored link text intact.

## Redirect panel layout correction

The first native screenshots showed the redirect panel shrinking to its padding
while the preview retained its minimum height, hiding Follow redirect inside a
tiny scroll area. The panel now uses `flex: 0 0 auto`, retains its existing
260px scroll limit for long chains, and removes the extra top button margin.
This is a CSS-only correction; no dictionary, index or Rust changes are needed.
Native visual confirmation of the corrected layout remains pending.
