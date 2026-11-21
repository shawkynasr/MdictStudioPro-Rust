"""Observe one v5 SlowPlugin force-quit test; only explicit cleanup may stop its recorded child."""
import argparse
import hashlib
import json
import plistlib
import os
import signal
import time
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def processes(watched=()):
    # Keep free-format/locale-sensitive start dates OUT of the command table.
    env = {**os.environ, 'LC_ALL': 'C'}
    result = subprocess.run(['ps', '-axww', '-o', 'pid=,ppid=,command='],
                            check=True, capture_output=True, text=True, env=env)
    rows = parse_processes(result.stdout)
    for pid in watched:
        if pid not in rows:
            continue
        started = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart='],
                                 capture_output=True, text=True, env=env)
        if started.returncode == 0 and started.stdout.strip():
            rows[pid]['started'] = started.stdout.strip()
        else:
            rows.pop(pid, None)
    return rows


def parse_processes(text):
    rows = {}
    for line in text.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and fields[0].isdigit() and fields[1].isdigit():
            rows[int(fields[0])] = {'pid': int(fields[0]), 'ppid': int(fields[1]),
                                   'command': fields[2]}
    return rows


def record_identity(process):
    current = processes([process['pid']]).get(process['pid'])
    if current is None or current['command'] != process['command']:
        raise RuntimeError('Process changed during arming; no test was armed')
    return current


def executable_path(command, name):
    # ps prints an unquoted path even when the bundle name contains spaces.
    match = re.match(r'^(.*?/Contents/MacOS/' + re.escape(name) + r')(?=\s|$)', command)
    return Path(match[1]) if match else None


def find_apps(table, executable):
    expected_hash = sha(executable)
    expected_info = (executable.parent.parent / 'Info.plist').read_bytes()
    matches, candidates = [], []
    for process in table.values():
        actual = executable_path(process['command'], executable.name)
        if actual is None:
            continue
        candidates.append({'pid': process['pid'], 'executable': str(actual)})
        try:
            # Also permits a macOS-translocated copy only when executable AND
            # bundle metadata are byte-identical to the explicitly selected app.
            if (actual.is_file() and sha(actual) == expected_hash
                    and (actual.parent.parent / 'Info.plist').read_bytes() == expected_info):
                matches.append((process, actual))
        except OSError:
            continue
    return matches, candidates


def same_process(observed, recorded):
    return observed is not None and bool(observed.get('started')) and all(observed[k] == recorded[k]
                                       for k in ('pid', 'started', 'command'))


def write_new(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def self_test():
    rows = parse_processes(' 42 1 /an app/executable\n')
    rows[42]['started'] = 'Fri Nov 20 22:00:00 2026'
    assert rows[42]['command'] == '/an app/executable'
    assert same_process(rows[42], dict(rows[42], ppid=99))  # reparenting is expected
    assert not same_process(dict(rows[42], started='different'), rows[42])
    assert not same_process(dict(rows[42], command='unrelated'), rows[42])
    assert not same_process(None, rows[42])
    regression = '/Users/shawky/Downloads/mdict-studio-m0-m1/m3-shell-out-mac-preview-v5/Mdict Studio Pro Preview.app/Contents/MacOS/mdict-studio-desktop'
    assert parse_processes('95428 1 ' + regression)[95428]['command'] == regression
    from unittest.mock import patch
    def fake_run(command, **kwargs):
        assert kwargs['env']['LC_ALL'] == 'C'
        if '-axww' in command:
            assert 'lstart' not in ' '.join(command)
            return subprocess.CompletedProcess(command, 0, '95428 1 ' + regression, '')
        return subprocess.CompletedProcess(command, 0, '  arbitrary date text with spaces  \n', '')
    with patch('subprocess.run', side_effect=fake_run):
        captured = processes([95428])[95428]
        assert captured['command'] == regression
        assert captured['started'] == 'arbitrary date text with spaces'
    assert not same_process({'pid':42,'command':'anything'}, rows[42])
    assert executable_path('/long path/Preview.app/Contents/MacOS/studio --arg', 'studio') == Path('/long path/Preview.app/Contents/MacOS/studio')
    assert executable_path('python -u /bridge.py', 'studio') is None
    assert executable_path('/a.app/Contents/MacOS/studio-other', 'studio') is None
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        selected = base / 'selected.app/Contents/MacOS/studio'
        copied = base / 'translocated.app/Contents/MacOS/studio'
        wrong = base / 'other.app/Contents/MacOS/studio'
        for executable in (selected, copied, wrong):
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'fixture executable')
            (executable.parent.parent / 'Info.plist').write_bytes(b'same metadata')
        (wrong.parent.parent / 'Info.plist').write_bytes(b'other app')
        table = {i: {'pid': i, 'ppid': 1, 'started': 'now', 'command': str(path) + ' --args'} for i, path in enumerate((copied, wrong), 1)}
        matches, candidates = find_apps(table, selected)
        assert len(matches) == 1 and matches[0][1] == copied and len(candidates) == 2
        copied.write_bytes(b'changed executable')
        assert not find_apps(table, selected)[0]
    print('Separate date/path regression, copied-app identity, mismatch and PID-reuse checks passed; no processes signalled.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['arm', 'check', 'stop-recorded-child', 'self-test'])
    parser.add_argument('--output', type=Path, default=Path('m3-shell-out-force-quit-1'))
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--app', type=Path, default=ROOT / 'm3-shell-out-mac-preview-v5/Mdict Studio Pro Preview.app')
    args = parser.parse_args()
    if args.action == 'self-test':
        return self_test()
    out = args.output.resolve()
    if out.parent != ROOT or not out.name.startswith('m3-shell-out-'):
        parser.error('Use a fresh m3-shell-out-* directory directly under the project')
    state_path = out / 'armed.json'
    if args.action == 'arm':
        if args.destination is None:
            parser.error('--destination must be the new output folder selected in the app')
        destination = args.destination.absolute()
        if destination.exists() or destination.is_symlink():
            parser.error('Destination must not exist before this test')
        app = args.app.resolve()
        with (app / 'Contents/Info.plist').open('rb') as stream:
            executable = app / 'Contents/MacOS' / plistlib.load(stream)['CFBundleExecutable']
        table = processes()
        apps, candidates = find_apps(table, executable)
        if len(apps) != 1:
            print(json.dumps({'matching_apps': len(apps), 'selected_executable': str(executable),
                              'same_name_candidates': candidates,
                              'hint': 'Open exactly one copy of the selected preview; keep SlowPlugin Running. No app or child was stopped.'}, ensure_ascii=False, indent=2))
            raise RuntimeError('Could not uniquely identify the running selected preview; send the diagnostic above')
        parent, actual_executable = apps[0]
        children = []
        for child in table.values():
            match = re.search(r'\s-u\s+(.+)/bridge\.py$', child['command'])
            if child['ppid'] != parent['pid'] or not match:
                continue
            stage = Path(match[1])
            if stage.parent.resolve() != destination.parent.resolve():
                continue
            if (stage.is_symlink() or not stage.name.startswith('.tmp')
                    or not (stage / 'plugin.py').is_file()
                    or not (stage / 'input/input.txt').is_file()):
                continue
            if (sha(stage / 'plugin.py') == sha(ROOT / 'm3/fixtures/noisy_plugin.py')
                    and sha(stage / 'input/input.txt') == sha(ROOT / 'm3/fixtures/build-source.txt')):
                children.append((child, stage))
        if len(children) != 1:
            raise RuntimeError('Expected one active fixture bridge under the selected app; start SlowPlugin first')
        child, stage = children[0]
        parent = record_identity(parent)
        child = record_identity(child)
        if child['ppid'] != parent['pid']:
            raise RuntimeError('Fixture child was reparented during arming; no test was armed')
        state = {'schema': 'studio-force-quit-observation-v1', 'app': parent,
                 'app_executable_sha256': sha(executable), 'running_executable': str(actual_executable),
                 'app_match': 'executable and Info.plist byte identity; resources not compared', 'child': child,
                 'stage': str(stage), 'destination': str(destination),
                 'source_sha256': sha(ROOT / 'm3/fixtures/build-source.txt'),
                 'plugin_sha256': sha(ROOT / 'm3/fixtures/noisy_plugin.py'),
                 'diagnostic_sha256': sha(Path(__file__)),
                 'scope': 'One observed fixture bridge; no whole-system orphan or crash-recovery claim'}
        out.mkdir(exist_ok=False)
        write_new(state_path, state)
        print('Armed. Now Force Quit ONLY Mdict Studio Pro Preview, then run check before reopening.')
        print('Recorded bridge PID:', child['pid'])
        return
    state = json.loads(state_path.read_text())
    table = processes([state['app']['pid'], state['child']['pid']])
    app_alive = same_process(table.get(state['app']['pid']), state['app'])
    child_alive = same_process(table.get(state['child']['pid']), state['child'])
    if args.action == 'stop-recorded-child':
        if app_alive:
            raise RuntimeError('Refusing: original app is still running; use normal Quit or Cancel')
        if not (out / 'report.json').is_file():
            raise RuntimeError('Run check first to preserve the pre-cleanup observation')
        if child_alive:
            # Signal only the recorded fixture PID after matching start time and command.
            os.kill(state['child']['pid'], signal.SIGKILL)
            for _ in range(20):
                time.sleep(0.1)
                if not same_process(processes([state['child']['pid']]).get(state['child']['pid']), state['child']):
                    break
        still_alive = same_process(processes([state['child']['pid']]).get(state['child']['pid']), state['child'])
        cleanup = {'schema': state['schema'], 'recorded_child_was_running': child_alive,
                   'recorded_child_still_running': still_alive, 'files_deleted': False,
                   'note': 'Explicit diagnostic cleanup, not automatic app recovery; temporary files retained for review'}
        write_new(out / 'diagnostic-cleanup.json', cleanup)
        print(json.dumps(cleanup, indent=2))
        return
    destination = Path(state['destination'])
    stage = Path(state['stage'])
    report = {'schema': state['schema'], 'status': 'app_still_running' if app_alive else 'observation_complete',
              'original_app_still_running': app_alive, 'recorded_bridge_still_running': child_alive,
              'destination_exists': destination.exists() or destination.is_symlink(),
              'recorded_temporary_directory_exists': stage.exists() or stage.is_symlink(),
              'source_unchanged': sha(ROOT / 'm3/fixtures/build-source.txt') == state['source_sha256'],
              'plugin_unchanged': sha(ROOT / 'm3/fixtures/noisy_plugin.py') == state['plugin_sha256'],
              'reopened_app_tested': False, 'processes_signalled': False,
              'files_deleted': False, 'production_release_ready': False,
              'scope': state['scope']}
    # A check does not certify cleanup, even when the app can reopen.
    write_new(out / 'report.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(str(out / 'report.json'))


if __name__ == '__main__':
    main()
