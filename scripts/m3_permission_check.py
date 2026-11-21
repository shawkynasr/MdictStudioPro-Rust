"""Prepare and verify a reversible output-directory permission test for preview v6."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'studio-output-permission-check-v1'
SOURCE = ROOT / 'm3/fixtures/cedict.txt'
EXPECTED = '83288a2c708f4d03a12d08e72eb7a71af3904d37528447ffc3ee1e95fe8415b1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'unlock', 'verify'])
    parser.add_argument('--output', type=Path, default=Path('m3-shell-out-permission-1'))
    args = parser.parse_args()
    out = args.output.absolute()
    if (out.parent.resolve() != ROOT or not out.name.startswith('m3-shell-out-')
            or out.is_symlink()):
        parser.error('Use a fresh m3-shell-out-* directory directly inside this project')
    locked = out / 'locked'
    destination = locked / 'result.txt'
    if args.action == 'prepare':
        out.mkdir(mode=0o700, exist_ok=False)
        locked.mkdir(mode=0o700)
        identity = locked.stat()
        write_new(out / 'prepared.json', {'schema': SCHEMA, 'source_sha256': sha(SOURCE),
                  'locked_device': identity.st_dev, 'locked_inode': identity.st_ino,
                  'destination': str(destination)})
        os.chmod(locked, 0o500)
        probe = locked / '.write-probe'
        try:
            with probe.open('xb'):
                pass
        except PermissionError:
            print('Prepared: writes are denied under this account. Keep the app running.')
            print('Input:', SOURCE)
            print('Save to:', destination)
            return
        except Exception:
            os.chmod(locked, 0o700)
            raise
        else:
            # Some privileged accounts bypass mode bits; do not call that a test.
            probe.unlink()
            os.chmod(locked, 0o700)
            raise RuntimeError('This account bypasses the permission restriction; test not prepared')
    state = json.loads((out / 'prepared.json').read_text())
    identity = locked.lstat()
    if (state.get('schema') != SCHEMA or not stat.S_ISDIR(identity.st_mode)
            or (identity.st_dev, identity.st_ino) != (state['locked_device'], state['locked_inode'])):
        raise RuntimeError('Refusing permission change: original test directory identity differs')
    if args.action == 'unlock':
        if (out / 'unlock.json').exists():
            raise RuntimeError('Already unlocked; preserve the first observation')
        entries = list(locked.iterdir())
        report = {'schema': SCHEMA, 'output_existed_after_failure': destination.exists() or destination.is_symlink(),
                  'entries_after_failure': [p.name for p in entries[:32]],
                  'entry_count_after_failure': len(entries),
                  'source_unchanged': sha(SOURCE) == state['source_sha256']}
        os.chmod(locked, 0o700)  # only this newly created, identity-checked directory
        report['test_directory_unlocked'] = True
        write_new(out / 'unlock.json', report)
        print(json.dumps(report, indent=2))
        if entries:
            print('Unexpected output/residue: stop and send this observation before retrying.')
        else:
            print('Retry the same conversion and SAME output path without restarting the app.')
        return
    if not (out / 'unlock.json').is_file():
        raise RuntimeError('Run unlock after the failed GUI attempt, then retry before verify')
    before = json.loads((out / 'unlock.json').read_text())
    regular = destination.is_file() and not destination.is_symlink()
    digest = sha(destination) if regular else None
    size = destination.stat().st_size if regular else None
    source_unchanged = sha(SOURCE) == state['source_sha256']
    passed = (not before['output_existed_after_failure'] and before['entry_count_after_failure'] == 0
              and before['source_unchanged'] and source_unchanged and size == 885 and digest == EXPECTED
              and sorted(p.name for p in locked.iterdir()) == ['result.txt'])
    report = {'schema': SCHEMA, 'status': 'passed' if passed else 'failed',
              'output_bytes': size, 'output_sha256': digest, 'source_unchanged': source_unchanged,
              'initial_failure_observation': before, 'permission_error_text_and_same_session': 'require user GUI confirmation',
              'production_release_ready': False}
    write_new(out / 'report.json', report)
    print(json.dumps(report, indent=2))
    print(out / 'report.json')
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
