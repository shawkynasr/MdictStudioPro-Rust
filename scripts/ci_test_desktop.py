"""Run native desktop tests with the same preview override used by bundling."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from ci_collect_preview import ROOT, TARGETS


def run_tests(root, target):
    if target not in TARGETS:
        raise ValueError('Unsupported CI target')
    tauri = root / 'm3/desktop/src-tauri'
    config = json.loads((tauri / 'tauri.ci.conf.json').read_text(encoding='utf-8'))
    # Icon generation is an explicit earlier step. Never silently fall back to
    # the development config's missing Windows icons/icon.ico.
    icons = config['bundle']['icon']
    for name in icons:
        if not (tauri / name).is_file():
            raise FileNotFoundError(f'Generate platform icons before native tests: {name}')
    if target.endswith('windows-msvc') and not any(name.endswith('.ico') for name in icons):
        raise ValueError('Windows preview configuration must include an ICO icon')
    environment = {**os.environ, 'TAURI_CONFIG': json.dumps(config)}
    return subprocess.run(['cargo', 'test', '--manifest-path', str(tauri / 'Cargo.toml'),
                           '--target', target, '--locked', 'project_link_tests'],
                          cwd=root, env=environment, check=True).returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=sorted(TARGETS))
    args = parser.parse_args()
    raise SystemExit(run_tests(ROOT, args.target))
