# Qualify MDD CSS, image and font resources

The corrected synthetic stylesheet fixtures have user-reported visual and
restart success in MDict and GoldenDict for UTF-8 and UTF-16. This is a bounded
fixture result, not M1 completion. The new wrapper revision 7 keeps the v5
engine and stylesheet correction; it adds a separate resource-only case.

## Generate and check offline

Update sources while keeping .venv and vendor. From the project root, outside
all reader scan folders, run:

```sh
.venv/bin/python scripts/resource_controls.py --output resource-out
```

The command must exit zero and print
**offline_MDD_controls_passed_native_untested** before native testing. If any
step fails, return resource-out/resource-controls-report.json and the referenced
log without importing the new pair.

The script verifies the v5 engine, runs the wrapper Rust test, then builds two
MDX/MDD pairs (MDX UTF-8 and UTF-16; MDD keys UTF-16). It checks exact physical
records, all resource bytes, exact and missing lookups, multi-block boundaries,
metadata/framing, checksums, offsets, termination of MDX text, and resource
inventory hashes through Rust, Python and the independent structural auditor.
It checks that CSS's relative font URL resolves to an actual MDD resource.

There are four MDD resources: styles/probe.css, images/green.png,
fonts/studio-probe.ttf and data/sentinel.bin. The last contains binary zero,
0xff and non-ASCII bytes, testing exact binary preservation. No loose CSS,
image or font files are generated in the dictionaries folder. The five MDX
entries have no numeric style markers and an empty embedded StyleSheet, which
isolates resource behavior from the prior compact-style issue.

The original diagnostic TTF maps ASCII A, B, C to filled triangle, plus and
diamond shapes. It uses an original family name, no local() font source and
unrestricted embedding flags. Its license and optional fontTools generator are
included; fontTools is not needed to run the user checks. Never install this
font on your system: it must load from the MDD for the test to be meaningful.

## Native test after offline success

Copy **both** files of the UTF-8 pair to an isolated reader test directory:

- resource-out/dictionaries/06-mdd-resources-utf8.mdx
- resource-out/dictionaries/06-mdd-resources-utf8.mdd

Keep their filenames matched and put them in the same directory. Load only
that pair in GoldenDict, then MDict. Do not put CSS or font sidecars beside it.

| Search | Required visual result |
|---|---|
| css | MDD_CSS_OK on a green background with a black border |
| image | A green 24x24 square; no broken-image icon |
| font | Embedded ABC becomes triangle, plus, diamond; fallback control stays ABC |
| combined | Green box, green image and the three font shapes together |
| plain | PLAIN_CONTROL_OK without inherited resource styling |
| missing | No exact entry (similar-word suggestions are allowed) |

Check CSS before judging the font: if the stylesheet itself fails to load,
font-family rules have not been exercised. Seeing ordinary ABC in both font
rows does not prove a working embedded font. The shape test avoids relying
on a system font that might mask an MDD failure. The image entry has no CSS
dependency, so it independently tests direct image discovery.

Quit and reopen each reader and check the resources again. If the first pair
passes, repeat with the UTF-16 pair alone. If a reader crashes, stop its sequence
and remove the new pair before reopening. The generated results CSV starts
NOT_RUN; no script opens a native reader or claims visual success.

Return resource-out/resource-controls-report.json with results for each reader,
especially whether the font row shows shapes or letters. No separate approval
round is needed after a successful offline run to perform these limited tests.

## Coverage limits

The first test uses exact lowercase resource paths and a relative CSS font URL.
It does not establish case-insensitive aliases, every separator/URL spelling,
multivolume archives, audio, large files or production limits. It tests embedded
font loading, not Arabic shaping with Amiri. The user's real fonts and dictionary
assets remain outside the distributed package. M1 remains open.

Rust/Cargo are unavailable in the authoring environment. The added Rust MDD
branch must compile and pass runtime checks on the user's Mac; local tests
cannot substitute for that execution or native visual tests.
