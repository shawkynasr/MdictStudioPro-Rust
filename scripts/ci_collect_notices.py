"""Collect actual dependency notices on a CI runner; report gaps without inventing licenses."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from ci_collect_preview import ROOT, TARGETS
from ci_upstream_notices import UpstreamNotices, repository, save_recovered


def notice_paths(directory):
    for p in sorted(directory.rglob('*')):
        if p.is_symlink() or not p.is_file():
            continue
        if p.name.lower().startswith(('license', 'licence', 'copying', 'copyright', 'notice', 'unlicense')):
            if p.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f'Unexpectedly large notice: {p.name}')
            yield p


def collect_package(output, directory, identity, metadata):
    folder = output / 'dependencies' / hashlib.sha256(identity.encode()).hexdigest()[:24]
    folder.mkdir(parents=True)
    texts = []
    paths = list(notice_paths(directory))
    declared = metadata.get('license_file')
    if declared:
        explicit = Path(declared)
        if not explicit.is_absolute(): explicit = directory / explicit
        explicit = explicit.resolve()
        if explicit.is_relative_to(directory.resolve()) and explicit.is_file() and explicit not in paths:
            paths.append(explicit)
    for p in paths:
        relative = p.relative_to(directory)
        dest = folder / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        texts.append({'path': dest.relative_to(output).as_posix(),
                      'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
    return {'id': identity, **metadata, 'notice_files': texts,
            'license_text_missing': not bool(texts), 'license_declaration_missing': not bool(metadata.get('license') or metadata.get('license_file'))}


def collect(root, cargo_metadata, output, target, resolver=None):
    if target not in TARGETS:
        raise ValueError('Unknown target')
    output.mkdir(exist_ok=False)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copyfile(root / name, output / name)
    shutil.copytree(root / 'LICENSES', output / 'LICENSES')
    packages = []
    first_party = []
    contexts = {}
    for p in cargo_metadata['packages']:
        directory = Path(p['manifest_path']).parent.resolve()
        try:
            relative = directory.relative_to(root.resolve())
            owned = p.get('source') is None and relative.parts[0] in ('crates', 'm2', 'm3', 'm4', 'experiments')
        except ValueError:
            owned = False
        if owned:
            first_party.append({'name':p['name'], 'version':p['version']})
            continue
        identity = 'rust:' + p['id']
        contexts[identity] = (directory, None)
        packages.append(collect_package(output, directory, identity, {
            'ecosystem':'cargo', 'name':p['name'], 'version':p['version'],
            'license':p.get('license'), 'license_file':p.get('license_file'), 'authors':p.get('authors',[]),
            'repository':p.get('repository'), 'source':p.get('source'),
            'scope':'resolved dependency graph; may include build/development dependencies'}))
    frontend = root / 'm3/desktop'
    lock = json.loads((frontend / 'package-lock.json').read_text(encoding='utf-8'))
    absent = []
    for name, entry in lock['packages'].items():
        if not name:
            continue
        directory = frontend / name
        if not (directory / 'package.json').is_file():
            if not entry.get('optional'):
                raise FileNotFoundError(f'Locked npm package not installed: {name}')
            absent.append({'path':name, 'version':entry['version'], 'scope':'optional, not installed on runner'})
            continue
        package = json.loads((directory / 'package.json').read_text(encoding='utf-8'))
        if package.get('version') != entry['version']:
            raise ValueError(f'Installed npm version differs from lock: {name}')
        identity = 'npm:' + name + '@' + entry['version']
        contexts[identity] = (directory, entry)
        packages.append(collect_package(output, directory, identity, {
            'ecosystem':'npm', 'name':package['name'], 'version':package['version'],
            'license':package.get('license'), 'repository':package.get('repository'),
            'scope':'build/development dependency' if entry.get('dev') else 'application dependency'}))
    # Native npm distribution packages use their same-version wrapper's
    # upstream license set. Require the same repository and declaration too.
    by_name = {p['name']:p for p in packages if p['ecosystem'] == 'npm'}
    for package in packages:
        if not package['license_text_missing']: continue
        if package['ecosystem'] == 'npm':
            wrapper = next((parent for prefix, parent in [('@esbuild/', 'esbuild'), ('@rollup/rollup-', 'rollup'), ('@tauri-apps/cli-', '@tauri-apps/cli')] if package['name'].startswith(prefix)), None)
            parent = by_name.get(wrapper)
            if parent and parent['version'] == package['version'] and parent['license'] == package['license'] and parent['notice_files']:
                if repository(parent['repository']) == repository(package['repository']):
                    package['notice_files'] = [{**f, 'origin':'same_version_distribution_wrapper', 'source_package':parent['id']} for f in parent['notice_files']]
                    package['license_text_missing'] = False
                    continue
        if resolver:
            directory, entry = contexts[package['id']]
            try:
                save_recovered(output, package, resolver.recover(directory, package, entry))
            except Exception as error:
                package['upstream_notice_error'] = str(error)
    report = {'schema':'studio-preview-license-inventory-v1', 'target':target,
              'commit':os.environ.get('GITHUB_SHA'), 'packages':packages,
              'first_party_packages':first_party, 'absent_optional_packages':absent,
              'missing_license_texts':[p['id'] for p in packages if p['license_text_missing']],
              'missing_license_declarations':[p['id'] for p in packages if p['license_declaration_missing']],
              'legal_compatibility_qualified':False}
    (output / 'DEPENDENCIES.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"Collected notices for {len(packages)} packages; {len(report['missing_license_texts'])} missing texts; {len(report['missing_license_declarations'])} missing declarations. Review before publishing.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=sorted(TARGETS))
    parser.add_argument('--archive', action='store_true')
    parser.add_argument('--fetch-upstream', action='store_true', help='Recover omitted notices only at immutable package source revisions')
    args = parser.parse_args()
    output = ROOT / 'm3-shell-out-ci-legal'
    if args.archive:
        assets = ROOT / 'm3-shell-out-ci-assets'
        with zipfile.ZipFile(assets / f'LEGAL-{args.target}.zip','w',zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(output.rglob('*')):
                if p.is_file(): archive.write(p,p.relative_to(output))
        return
    command = ['cargo','metadata','--manifest-path',str(ROOT/'m3/desktop/src-tauri/Cargo.toml'),
               '--locked','--format-version','1','--filter-platform',args.target]
    metadata = json.loads(subprocess.run(command,cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf-8').stdout)
    collect(ROOT,metadata,output,args.target,UpstreamNotices() if args.fetch_upstream else None)


if __name__ == '__main__': main()
