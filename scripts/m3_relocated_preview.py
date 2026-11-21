"""Prepare and verify an exact v6 preview copy outside the source project."""
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
EXPECTED_RESULT = '83288a2c708f4d03a12d08e72eb7a71af3904d37528447ffc3ee1e95fe8415b1'


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify'])
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'mdict-v6-location-check-1')
    args = parser.parse_args()
    out = args.output.absolute()
    if (out.is_symlink() or not out.name.startswith('mdict-v6-location-check-')
            or out.parent.resolve() == ROOT or out.parent.resolve().is_relative_to(ROOT)):
        parser.error('Use a NEW mdict-v6-location-check-* folder outside the project')
    app = out / PRODUCT
    if args.action == 'prepare':
        source_app = ROOT / 'm3-shell-out-mac-preview-v6' / PRODUCT
        before = inspect_bundle(source_app)
        if before['executable_sha256'] != EXPECTED_APP:
            raise RuntimeError('Source app is not the reviewed preview v6 executable')
        source_input = ROOT / 'm3/fixtures/cedict.txt'
        if digest(source_input) != EXPECTED_INPUT:
            raise RuntimeError('Fixture source differs from accepted input')
        out.mkdir(mode=0o700, parents=False, exist_ok=False)
        subprocess.run(['/usr/bin/ditto', str(source_app), str(app)], check=True)
        after = inspect_bundle(app)
        if before != after:
            raise RuntimeError('Copied app differs; do not launch it for this check')
        shutil.copyfile(source_input, out / 'cedict.txt')
        write_new(out / 'prepared.json', {'schema':'studio-relocated-preview-v1',
                  'status':'exact_v6_copy_prepared_GUI_pending', 'bundle':after,
                  'input_sha256':EXPECTED_INPUT, 'scope':'Same-Mac relocation only; not clean-machine or signed distribution qualification'})
        print('Prepared and verified exact preview v6 copy.')
        print('Open in Finder:', app)
        print('CC-CEDICT input:', out / 'cedict.txt')
        print('Save to:', out / 'result.txt')
        print('Quit all original previews and close development Terminal/server before launching this copy.')
        return
    state = json.loads((out / 'prepared.json').read_text())
    if state.get('schema') != 'studio-relocated-preview-v1':
        raise RuntimeError('Unexpected preparation record')
    current = inspect_bundle(app)
    result = out / 'result.txt'
    regular = result.is_file() and not result.is_symlink()
    result_sha = digest(result) if regular else None
    size = result.stat().st_size if regular else None
    passed = (current == state['bundle'] and current['executable_sha256'] == EXPECTED_APP
              and digest(out / 'cedict.txt') == EXPECTED_INPUT
              and result_sha == EXPECTED_RESULT and size == 885)
    report = {'schema':state['schema'], 'status':'passed' if passed else 'failed',
              'bundle_unchanged':current == state['bundle'], 'input_unchanged':digest(out / 'cedict.txt') == EXPECTED_INPUT,
              'output_bytes':size, 'output_sha256':result_sha,
              'Finder_launch_from_copied_path':'requires user confirmation',
              'development_server_and_Terminal_closed_at_launch':'requires user confirmation',
              'scope':state['scope'], 'clean_machine_qualified':False, 'production_release_ready':False}
    write_new(out / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(out / 'report.json')
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
