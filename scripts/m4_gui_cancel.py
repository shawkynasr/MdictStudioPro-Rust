"""Prepare a synthetic SQLite fixture, then check GUI cancellation filesystem effects."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from m4_database import MDX_SQL

SOURCE = 'gui-cancel-source.db'
DESTINATION = 'cancelled-rebuild.mdx'
MANIFEST = 'fixture.json'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def fixture_rows(count):
    for number in range(count):
        key = f'g{number:06d}'
        payload = hashlib.sha512(str(number).encode()).hexdigest() * 2
        body = f'<p>{number:06d} English · 中文 · العربية {payload}</p>'
        yield key, body


def prepare(folder, count=100000):
    if not 1 <= count <= 100000:
        raise ValueError('Fixture must contain 1..100,000 records')
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'results').mkdir()
    source = folder / SOURCE
    decoded = 0
    connection = sqlite3.connect(source)
    try:
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.execute(MDX_SQL)
        with connection:
            for key, body in fixture_rows(count):
                decoded += len(key.encode()) + len(body.encode())
                if decoded > 32 * 1024 * 1024:
                    raise ValueError('Decoded fixture exceeds supported profile')
                connection.execute('INSERT INTO mdx VALUES (?,?)', (key, body))
            connection.execute('CREATE INDEX entry_index ON mdx(entry)')
        if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Synthetic database integrity check failed')
    finally:
        connection.close()
    if source.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Fixture exceeds source file cap')
    manifest = {'schema': 'studio-gui-cancel-fixture-v1', 'records': count,
                'decoded_bytes': decoded, 'source_sha256': digest(source),
                'source_bytes': source.stat().st_size,
                'GUI_cancel_verified': False}
    (folder / MANIFEST).write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    destination = folder / 'results' / DESTINATION
    instructions = f'''GUI SQLite → MDX cancellation test

1. Open Mdict Studio Pro and close/release Dictionary Tools readers.
2. In Jobs, dismiss finished jobs if the retention limit was reached.
3. Database: select SQLite → MDX.
4. Source: {source}
5. Save as: {destination}
6. Click Convert. Jobs opens automatically. Click Cancel immediately on
   this conversion, then WAIT until the job says Cancelled.
7. Run the check command documented in docs/M4-GUI-CANCEL.md.

This fixture has {count:,} records and {decoded:,} decoded bytes.
It uses the existing closed legacy SQLite input profile. No real dictionary
or external resource is used. It needs no artificial delay or raised limits.

If the job finishes successfully before cancellation, that is NOT a successful
cancellation test. Keep its output and prepare a new fixture folder to retry.
If it fails for another reason, retain the error; do not report it as cancelled.
The checker verifies files only. A screenshot/user confirmation of the job's
Cancelled state is separate evidence that the GUI cancellation completed.
'''
    (folder / 'GUI-STEPS.txt').write_text(instructions, encoding='utf-8')
    return manifest


def check(folder):
    manifest = json.loads((folder / MANIFEST).read_text(encoding='utf-8'))
    if manifest.get('schema') != 'studio-gui-cancel-fixture-v1':
        raise ValueError('Not a GUI cancel fixture')
    source = folder / SOURCE
    source_regular = source.is_file() and not source.is_symlink()
    source_unchanged = source_regular and digest(source) == manifest['source_sha256']
    result_dir = folder / 'results'
    leftovers = sorted(str(path.relative_to(result_dir)) for path in result_dir.rglob('*')) if result_dir.is_dir() and not result_dir.is_symlink() else ['results directory missing or replaced']
    sidecars = [SOURCE + suffix for suffix in ['-wal', '-shm', '-journal']
                if (folder / (SOURCE + suffix)).exists() or (folder / (SOURCE + suffix)).is_symlink()]
    destination = result_dir / DESTINATION
    absent = not destination.exists() and not destination.is_symlink()
    passed = source_unchanged and absent and not leftovers and not sidecars
    return {'schema': 'studio-gui-cancel-check-v1',
            'status': 'filesystem_checks_passed_GUI_state_pending' if passed else 'failed',
            'source_unchanged': source_unchanged, 'destination_absent': absent,
            'unexpected_result_paths': leftovers, 'source_sidecars': sidecars,
            'GUI_cancel_verified': False,
            'required_GUI_evidence': 'Job shows Cancelled, not Succeeded or Failed',
            'source_sha256': manifest['source_sha256'], 'fixture_records': manifest['records']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['prepare', 'check'])
    parser.add_argument('--folder', type=Path, default=Path('m4-database-out-gui-cancel'))
    args = parser.parse_args()
    folder = args.folder.resolve()
    if not folder.name.startswith('m4-database-out'):
        parser.error('Use an m4-database-out-prefixed fixture folder')
    try:
        if args.operation == 'prepare':
            result = prepare(folder)
            print(json.dumps(result, indent=2))
            print('Source: ' + str(folder / SOURCE))
            print('Save as: ' + str(folder / 'results' / DESTINATION))
            print('Instructions: ' + str(folder / 'GUI-STEPS.txt'))
        else:
            result = check(folder)
            report = folder / 'gui-cancel-check-report.json'
            with report.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(result, indent=2) + '\n')
            print(json.dumps(result, indent=2))
            print('Report: ' + str(report))
            return 0 if result['status'] == 'filesystem_checks_passed_GUI_state_pending' else 1
    except Exception as error:
        print(f'{type(error).__name__}: {error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
