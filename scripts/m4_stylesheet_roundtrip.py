"""Build UTF-8/UTF-16 numeric-style round trips and independently verify them."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

from m2_closeout import inventory
from m3_shell import ROOT, ADAPTER, check_adapter_lock, sha, sources
from verify_mdx_database import read_mdx, check as check_import
from verify_database_mdx import check as check_rebuild, groups


READER_CHECKS = """Open native/utf8/rebuilt.mdx in MDict and GoldenDict, then repeat with
native/utf16/rebuilt.mdx. Disable other copies of these test dictionaries.
Each dictionary has SEVEN records, including TWO entries named duplicate.

Headword       Expected display
inline         INLINE_BLUE_OK is blue (ordinary inline CSS control).
marker         MARKER_BLUE_OK is blue; no literal `2` marker.
combined       inline-blue and marker-blue are blue; marker-bold is bold.
duplicate      DUPLICATE_ONE_BLUE is blue AND DUPLICATE_TWO_BOLD is bold.
multilingual   English, Chinese and Arabic plus blue MULTILINGUAL_BLUE_OK.
empty          A valid entry with an empty definition.

Compare against original.mdx from the SAME encoding directory separately.
Original and rebuilt should look the same. Their title includes UTF-8/UTF-16.
Automated checks preserve raw markers without applying numeric styles; these
reader checks qualify the actual rendering. No MDD is needed for this fixture.
"""


def verify_case(directory, fixture, label):
    original = directory / 'original.mdx'
    database = directory / 'dictionary.db'
    rebuilt = directory / 'rebuilt.mdx'
    before = {p.name: sha(p) for p in (original, database, rebuilt)}
    source_hash, rows, attributes = read_mdx(original)
    expected = [(r['key'], r['text']) for r in fixture['entries']]
    assert rows == expected, 'Original differs from the declarative fixture'
    assert len(rows) == 7 and len(groups(rows)['duplicate']) == 2
    assert attributes['StyleSheet'] == fixture['stylesheet'], 'Original numeric stylesheet differs from fixture'
    assert attributes['Encoding'] == label, f'Expected encoding {label}, got {attributes["Encoding"]!r}'
    assert attributes['Title'] == f'SQLite stylesheet round trip · {label}'
    assert attributes['Description'] == fixture['description']
    imported = check_import(database, rows, attributes, source_hash)
    rebuilt_hash, rebuilt_rows, rebuilt_attributes = read_mdx(rebuilt)
    rebuilt_result = check_rebuild(database, rebuilt_rows, rebuilt_attributes)
    assert rebuilt_attributes == attributes and groups(rebuilt_rows) == groups(expected)
    assert {p.name: sha(p) for p in (original, database, rebuilt)} == before, 'Verification changed files'
    return {'status': 'passed', 'import': imported, 'rebuild': rebuilt_result,
            'file_sha256': before, 'rebuilt_sha256': rebuilt_hash,
            'raw_numeric_markers_preserved': True, 'reader_visual_checks': 'pending'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('m4-stylesheet-out'))
    parser.add_argument('--verify-existing', type=Path,
                        help='Read existing native/utf8 and native/utf16 files; skip all Rust jobs')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.name.startswith('m4-stylesheet-out'):
        parser.error('Use a new m4-stylesheet-out-prefixed directory')
    out.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'studio-m4-stylesheet-roundtrip-v1', 'status': 'failed',
              'native_jobs_executed': False, 'reader_visual_checks': 'pending', 'steps': []}
    protected = current = None

    def run(name, command):
        print(name, flush=True)
        report['stage'] = name
        done = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=1200,
                              env={**os.environ, 'STUDIO_TEST_PYTHON': sys.executable})
        (out / (name + '.log')).write_text(done.stdout + '\nSTDERR:\n' + done.stderr, encoding='utf-8')
        report['steps'].append({'name': name, 'command': command, 'returncode': done.returncode})
        if done.returncode:
            raise RuntimeError(f'{name} failed; see {out / (name + ".log")}')

    try:
        protected = inventory()
        current = sources()
        report.update(protected_source_sha256=protected, source_sha256=current)
        # Fail before compiling if the independent reader is absent.
        from mdict_utils.base.readmdict import MDX  # noqa: F401
        native = args.verify_existing.resolve() if args.verify_existing else out / 'native'
        report['verification_input'] = str(native)
        if args.verify_existing:
            if not native.is_dir():
                raise ValueError('--verify-existing must point to the existing native directory')
            report['mode'] = 'verify_existing_read_only_no_native_jobs'
        else:
            cargo = shutil.which('cargo')
            if not cargo:
                raise RuntimeError('Rust toolchain missing; run on the Rust-enabled Mac')
            check_adapter_lock()
            run('adapter-resolve', [cargo, 'metadata', '--offline', '--format-version', '1', '--manifest-path', ADAPTER])
            report['adapter_lock'] = check_adapter_lock()
            run('native-roundtrip', [cargo, 'run', '--offline', '--locked', '--manifest-path', ADAPTER,
                                    '--example', 'sqlite_stylesheet', '--', str(native)])
            report['native_jobs_executed'] = True
        report['stage'] = 'independent-verification'
        fixture = json.loads((ROOT / 'm3/fixtures/database-stylesheet.json').read_text(encoding='utf-8'))
        report['cases'] = {}
        for encoding, label in [('utf8', 'UTF-8'), ('utf16', 'UTF-16')]:
            report['verifying_case'] = encoding
            report['cases'][encoding] = verify_case(native / encoding, fixture, label)
        report['status'] = 'automated_roundtrip_passed_reader_checks_pending'
        report['stage'] = 'complete'
    except (Exception, KeyboardInterrupt) as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['traceback'] = traceback.format_exc()
    finally:
        try:
            if protected is not None:
                assert inventory() == protected, 'Protected M2 sources changed'
            if current is not None:
                assert sources() == current, 'M3/M4 sources changed'
        except Exception as error:
            report.update(status='failed', source_error=str(error))
        (out / 'READER-CHECKS.txt').write_text(
            ('Existing fixture directory: ' + str(args.verify_existing.resolve()) + '\n\n' if args.verify_existing else '')
            + READER_CHECKS, encoding='utf-8')
        (out / 'm4-stylesheet-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(report['status'] + ': ' + str(out / 'm4-stylesheet-report.json'))
    return 0 if report['status'] == 'automated_roundtrip_passed_reader_checks_pending' else 1


if __name__ == '__main__':
    raise SystemExit(main())
