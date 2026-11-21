"""Recreate the exact reviewed desktop vendor tree on a fresh CI checkout."""
import hashlib
from pathlib import Path
import tempfile
import tomllib
import urllib.request
from prepare_sort_experiment import ROOT, prepare

URL = 'https://static.crates.io/crates/mdictlib/mdictlib-0.2.8.crate'
PIN = '057225d3100242fb962d93c8c4a4967b07a8bc1903f33850792edf9c95eedf65'
MAX_BYTES = 8 * 1024 * 1024


def verify_archive(data, lock):
    packages = [p for p in lock['package'] if p['name'] == 'mdictlib' and p['version'] == '0.2.8']
    if len(packages) != 1 or packages[0].get('checksum') != PIN:
        raise ValueError('Root Cargo.lock does not match the reviewed crate identity')
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != PIN:
        raise ValueError('Downloaded crate failed size/checksum verification')


def main():
    lock = tomllib.loads((ROOT / 'Cargo.lock').read_text(encoding='utf-8'))
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(MAX_BYTES + 1)
    verify_archive(data, lock)
    with tempfile.TemporaryDirectory(prefix='studio-ci-vendor-') as directory:
        archive = Path(directory) / 'mdictlib-0.2.8.crate'
        archive.write_bytes(data)
        prepare(archive, revision=6, reuse=True)


if __name__ == '__main__':
    main()
