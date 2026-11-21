"""Collect only expected native installers; record CI identity without qualification claims."""
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'x86_64-pc-windows-msvc': ('.exe',),
    'x86_64-apple-darwin': ('.dmg',),
    'aarch64-apple-darwin': ('.dmg',),
    'x86_64-unknown-linux-gnu': ('.deb', '.AppImage'),
}


def collect(root, target, output, revision):
    extensions = TARGETS[target]
    bundle = root / 'm3/desktop/src-tauri/target' / target / 'release/bundle'
    files = sorted(p for p in bundle.rglob('*') if p.is_file() and p.suffix in extensions)
    for extension in extensions:
        if not any(p.suffix == extension for p in files):
            raise ValueError(f'Missing installer: {target} {extension}')
    output.mkdir(exist_ok=False)
    rows = []
    for source in files:
        name = f'MdictStudioPro-Rust-{target}-{source.name}'
        dest = output / name
        if dest.exists():
            raise ValueError('Duplicate installer basename')
        shutil.copyfile(source, dest)
        rows.append({'name': name, 'bytes': dest.stat().st_size,
                     'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    report = {'schema': 'studio-ci-preview-v1', 'target': target, 'commit': revision,
              'installers': rows, 'runtime_launch_tested': False, 'clean_machine_qualified': False,
              'signing': 'ad-hoc, not notarized' if 'apple' in target else 'unsigned',
              'production_release_ready': False}
    (output / f'BUILD-{target}.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (output / f'SHA256SUMS-{target}.txt').write_text(''.join(f"{r['sha256']}  {r['name']}\n" for r in rows), encoding='utf-8')
    shutil.copyfile(root / 'm3/fixtures/cedict.txt', output / f'cedict-{target}.txt')
    shutil.copyfile(root / 'docs/PRERELEASE-TESTING.md', output / f'TESTING-{target}.md')
    return report


if __name__ == '__main__':
    collect(ROOT, os.environ['STUDIO_TARGET'], ROOT / 'm3-shell-out-ci-assets', os.environ['GITHUB_SHA'])
