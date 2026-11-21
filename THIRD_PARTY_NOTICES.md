# Mdict Studio Pro Rust — authorship and third-party notices

Copyright (c) 2026 Shawky Nasr <shawkynasr@126.com> for the new project-authored Rust/Tauri implementation and accompanying project-authored material, except where another notice applies.

The new project-authored code is licensed under the GNU Affero General Public License, version 3 only (`AGPL-3.0-only`). See [LICENSE](LICENSE). This declaration does not replace another component's license or historical notices. Source repository: https://github.com/shawkynasr/MdictStudioPro-Rust

## Original application and preserved references

| Component | Role | Retained terms / provenance |
| --- | --- | --- |
| MdictStudioPro by Shawky Nasr | Original Python application and behavioral baseline | https://github.com/shawkynasr/MdictStudioPro; captured commit `6e181e22193472518d7966b66bac4dc2f2b32f83`. Its README declares AGPL-3.0, while its LICENSE text is GPL-3.0. Both are retained unchanged in `baseline/legacy`; the new root license does not resolve or rewrite that historical discrepancy. |
| Safari77 mdx and mdx_util snapshots | Separate reference/qualification workspaces | Their AGPL-3.0 texts remain under `reference/safari-mdx/LICENSE` and `reference/safari-mdx-util/LICENSE`. The desktop manifests do not include these reference crates as dependencies. |
| Synthetic font fixture | Qualification input | Its existing MIT notice is `baseline/resource-probe/FONT-LICENSE.txt`; it is not an installed system font or a license for user-provided fonts. |

## Desktop implementation dependencies

The application uses Tauri, its dialog plugin, Svelte, mdictlib 0.2.8 with the reproducible Studio writer patches, SQLite-related Rust bindings, compression/encoding/XML/JSON libraries and other Rust/JavaScript packages. Their original copyright, license and notice texts apply separately. The root AGPL does not relicense them.

The exact dependency versions are fixed by `m3/desktop/src-tauri/Cargo.lock` and `m3/desktop/package-lock.json`. CI collects installed dependency metadata and available upstream license/notice files into `m3-shell-out-ci-legal` before bundling. The resulting `DEPENDENCIES.json` distinguishes first-party crates, third-party packages, build/development tools and optional packages absent on that runner. It lists any missing license texts or declarations explicitly. This inventory is not a legal compatibility determination or an assertion that every listed build dependency is linked into the executable.

The mdictlib bootstrap verifies the original crate SHA-256 and preserves its upstream license, original files and patch provenance. Its generated source is reproducible using `scripts/ci_prepare_desktop.py`; the prepared vendor directory is intentionally absent from the development ZIP. A source recipient can recreate it from the pinned public crate and included patch generator. A distributor must ensure the source supplied with each binary is sufficient for the applicable license obligations, including dependency sources and local patches where required.

## Optional tools and dictionary content

Python, PyQt6, mdict-utils, openpyxl and user-installed plugin dependencies belong to the legacy/optional execution environment; they are not bundled as an embedded Python interpreter in the Rust preview. Installing or distributing such tools/plugins can introduce their own license requirements. Merely selecting a user plugin does not change its license.

Dictionary datasets, fonts, stylesheets, images and other user inputs keep their own licenses. Supporting a format or converter does not grant redistribution rights to its source data. No real private dictionary corpus is included in these preview installers. Synthetic fixtures are for testing and do not represent a redistribution of the complete CC-CEDICT or MOE datasets.

## Binary distribution and source

Each preview installer includes a `legal` resource directory with the project license, this notice, reference license copies and the CI-collected dependency notices. GitHub release assets also include a target-specific legal ZIP for convenient inspection. Review `DEPENDENCIES.json` for missing declarations/texts before publishing a draft; collect missing upstream notices and assess any non-permissive terms rather than treating a successful build as license clearance.

Publish the exact tagged source revision alongside binary previews, retain the dependency locks and patch/bootstrap scripts, and preserve required third-party notices. Release notes identify the source repository and tag. macOS, Windows, Linux and WebView/system runtime components have their own platform licenses; this source inventory does not inventory the entire operating system.
