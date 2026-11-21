"""Prepare an exact unsigned Intel v6 test ZIP; never launch or install it."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from m3_mac_preview import inspect_bundle, digest

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = 'Mdict Studio Pro Preview.app'
EXPECTED_APP = '2fdde5759b44256afcf8fddf9e52c2dad59f17c756742e588c478c3bda9b140d'
EXPECTED_INPUT = '463a04e1ad8ff8c3142e1456dc0fb529de2fa62affbe3dd70d4f70afd8e42dec'
README = '''Mdict preview v6 — Intel Mac test kit

This is a local unsigned preview, not a signed/notarized public release.
For this built-in converter test, do not install the source project, Node,
Cargo or Python on the target. Optional Python plugins are not tested.

Record target: another Intel Mac, or a fresh macOS account on the same Mac.
A fresh account is not a clean machine: machine-wide tools remain installed.
Record macOS version, Mac architecture, and transfer route (USB/download/etc.).
Do not use an Apple Silicon/Rosetta result as an Intel clean-machine result.

1. Extract the ZIP using Finder. Do not install development tools or copy the
   original project into the target account/machine for this check.
2. Open Mdict Studio Pro Preview.app from the extracted folder in Finder.
   If macOS blocks launch, capture the exact message and stop; do not remove
   quarantine or change system protections to force the test to pass.
3. Open Converters -> CC-CEDICT. Choose cedict.txt NEXT TO this app. Save to
   a NEW result.txt in a writable folder belonging to the target user.
4. Convert and collect the job receipt. Expected: 3 entries, 885 bytes.
5. Quit normally and reopen this same extracted app. Confirm it opens normally.
6. Return the receipt, result.txt, target details, launch/reopen observations
   and any macOS prompts. No verification script or interpreter is required
   on the target machine. Output bytes will be compared on the reviewer side.

This kit does not configure Python, transfer user settings, sign/notarize,
create an installer, or establish other-platform compatibility. Do not copy
real dictionaries or personal data into the returned evidence.
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m3-shell-out-clean-test-kit-1'))
    args = parser.parse_args()
    out = args.output.absolute()
    if out.parent.resolve() != ROOT or not out.name.startswith('m3-shell-out-') or out.is_symlink():
        parser.error('Use a NEW m3-shell-out-* folder directly under the project')
    source_app = ROOT / 'm3-shell-out-mac-preview-v6' / PRODUCT
    original = inspect_bundle(source_app)
    if original['executable_sha256'] != EXPECTED_APP:
        raise RuntimeError('Expected reviewed Intel preview v6; no kit created')
    fixture = ROOT / 'm3/fixtures/cedict.txt'
    if digest(fixture) != EXPECTED_INPUT:
        raise RuntimeError('Fixture identity differs; no kit created')
    out.mkdir(mode=0o700, exist_ok=False)
    payload = out / 'Mdict-v6-Intel-test'
    payload.mkdir()
    subprocess.run(['/usr/bin/ditto', str(source_app), str(payload / PRODUCT)], check=True)
    if inspect_bundle(payload / PRODUCT) != original:
        raise RuntimeError('Copied bundle differs')
    shutil.copyfile(fixture, payload / 'cedict.txt')
    (payload / 'READ-ME.txt').write_text(README, encoding='utf-8')
    (payload / 'bundle-identity.json').write_text(json.dumps(original, indent=2)+'\n')
    archive = out / 'Mdict-preview-v6-Intel-test.zip'
    subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(payload), str(archive)], check=True)
    unpacked = out / 'roundtrip'
    unpacked.mkdir()
    subprocess.run(['/usr/bin/ditto', '-x', '-k', str(archive), str(unpacked)], check=True)
    restored = unpacked / payload.name
    if (inspect_bundle(restored / PRODUCT) != original
            or digest(restored / 'cedict.txt') != EXPECTED_INPUT
            or (restored / 'READ-ME.txt').read_text() != README):
        raise RuntimeError('Archive round-trip differs; do not distribute this kit')
    report = {'schema':'studio-clean-target-testkit-v1', 'status':'kit_built_target_test_pending',
              'archive':str(archive), 'archive_bytes':archive.stat().st_size,
              'archive_sha256':digest(archive), 'executable_sha256':EXPECTED_APP,
              'input_sha256':EXPECTED_INPUT, 'bundle_copy_and_archive_roundtrip_equal':True,
              'target_launch_tested':False, 'clean_machine_qualified':False,
              'signing_or_notarization_added':False, 'M3_complete':False,
              'production_release_ready':False}
    with (out / 'report.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2))
    print('Send report.json first; transfer only the test ZIP to the selected target.')


if __name__ == '__main__':
    main()
