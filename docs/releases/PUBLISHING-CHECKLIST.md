# Four-platform experimental preview handoff

The current plan is a **new Rust refactor repository** and GitHub Actions builds for Windows x64, macOS Intel, macOS ARM and Linux x64. The selected repository is [https://github.com/shawkynasr/MdictStudioPro-Rust](https://github.com/shawkynasr/MdictStudioPro-Rust). Hosted builds, draft creation and public publication remain pending. See [setup instructions](../GITHUB-PREVIEWS.md).

Before publishing:

- New project-authored code uses AGPL-3.0-only as selected by the author. Preserve original-project attribution and component-specific notices. Review the generated target-specific LEGAL ZIP and all missing declarations/texts in DEPENDENCIES.json before publishing; the initial run found 36 distinct text gaps and the immutable-source recovery update still needs a new CI run and gap review.
- Review the exact committed source, retained lockfiles and generated vendor provenance. Exclude private dictionaries, user data, logs with secrets and local caches.
- Get all four `Rust desktop previews` jobs passing. Review native build and frontend test results and each BUILD file's target and source commit.
- Test installers as available and label unknown results honestly. Keep clean-machine and new-platform tests pending until observed; community testing is the purpose of the preview.
- Tag the selected commit with `v0.1.0-preview.1`. After the workflow creates a draft prerelease, review installer/fixture/guide coverage for all targets, signing limitations, known unsupported Windows features and generated checksum files. Download and compare actual installer hashes.
- Publish the draft manually as a **prerelease**, then record the URL and initial independent results. Keep stable readiness false.

No remote action has been performed here. Old Intel v6 notes are retained in [local-intel-v6-preview.md](local-intel-v6-preview.md), with its historical checksum in `SHA256SUMS-preview.1.txt`. That hash is for the old Mac test kit and must not be copied onto new CI assets.
