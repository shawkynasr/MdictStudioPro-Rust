"""Normalize isolated M3 seed-lock edges, verify pins, then run locked tests."""
import argparse
from pathlib import Path
import subprocess
from ci_collect_preview import ROOT, TARGETS
from m3_shell import check_adapter_lock

SUITES = {
    'export': ('m3/export-io/Cargo.toml', None),
    'runtime': ('m3/txt-runtime/Cargo.toml', 'large_export::tests'),
    'packing': ('m3/txt-runtime/Cargo.toml', 'txt_packing::tests::extended_'),
}


def run_tests(root, target, suite):
    if target not in TARGETS or suite not in SUITES:
        raise ValueError('Unsupported CI target or export test suite')
    root = Path(root)
    manifest_name, selection = SUITES[suite]
    manifest = root / manifest_name
    lock = manifest.with_name('Cargo.lock')
    # These distributed M3 seed locks can retain obsolete local/dev edges.
    # Check their registry pins before resolution and reject new versions or
    # checksum changes after resolution, before compiling or executing tests.
    check_adapter_lock(lock, root)
    # A fresh runner may have the desktop graph cached but not this standalone
    # test graph (including its dev dependencies). Fetch before going offline.
    # Cargo may normalize seed edges here; no compilation occurs, and the same
    # accepted version/checksum check must pass before any subsequent step.
    subprocess.run(['cargo', 'fetch', '--manifest-path', str(manifest), '--target', target],
                   cwd=root, check=True)
    check_adapter_lock(lock, root)
    subprocess.run(['cargo', 'metadata', '--offline', '--format-version', '1',
                    '--manifest-path', str(manifest), '--filter-platform', target],
                   cwd=root, stdout=subprocess.DEVNULL, check=True)
    check_adapter_lock(lock, root)
    command = ['cargo', 'test', '--offline', '--locked', '--manifest-path', str(manifest),
               '--target', target]
    if selection:
        command.append(selection)
    return subprocess.run(command, cwd=root, check=True).returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, choices=sorted(TARGETS))
    parser.add_argument('--suite', required=True, choices=sorted(SUITES))
    args = parser.parse_args()
    raise SystemExit(run_tests(ROOT, args.target, args.suite))
