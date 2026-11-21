"""Abrupt-parent-death tests of the actual wrapper in an isolated process group."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'm3/txt-runtime/src/plugin_wrapper.py'


@unittest.skipUnless(os.name == 'posix', 'Unix plugin profile')
class ParentDeathTests(unittest.TestCase):
    def exercise(self, replace_stage=False):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            stage = base / '.tmp-parent-watch'
            stage.mkdir()
            published = base / 'published'
            published.mkdir()
            sentinel = published / 'keep.txt'
            sentinel.write_text('completed output must survive')
            (stage / 'external-link').symlink_to(published, target_is_directory=True)
            shutil.copyfile(WRAPPER, stage / 'bridge.py')
            shutil.copyfile(ROOT / 'm3/txt-runtime/src/base_plugin.py', stage / 'base_plugin.py')
            shutil.copyfile(ROOT / 'm3/fixtures/noisy_plugin.py', stage / 'plugin.py')
            (stage / '.studio-parent-watch').write_text('fixture-token')
            (stage / 'input.txt').write_text('word\nbody\n</>\n')
            pidfile = base / 'child.pid'
            configfile = base / 'config.json'
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(1)
                listener.settimeout(10)
                config = {'port': listener.getsockname()[1], 'token': 'fixture-token',
                          'base': str(stage / 'base_plugin.py'), 'snapshot': str(stage / 'plugin.py'),
                          'original_plugin': str(ROOT / 'm3/fixtures/noisy_plugin.py'),
                          'class_name': 'SlowPlugin', 'input': str(stage / 'input.txt'),
                          'output': str(stage / 'output.txt')}
                configfile.write_text(json.dumps(config))
                # A disposable launcher stands for the abruptly killed native app.
                launcher_code = '''import json,os,pathlib,subprocess,sys,time
root=pathlib.Path(sys.argv[1]);config=json.loads(pathlib.Path(sys.argv[2]).read_text())
config['parent_watch']={'pid':os.getpid(),'stage':str(root)}
p=subprocess.Popen([sys.executable,'-u',str(root/'bridge.py')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
pathlib.Path(sys.argv[3]).write_text(str(p.pid));p.stdin.write(json.dumps(config).encode()+b'\\n');p.stdin.close()
while True: time.sleep(1)
'''
                launcher = subprocess.Popen([sys.executable, '-c', launcher_code, str(stage), str(configfile), str(pidfile)],
                                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                child_pid = None
                try:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(10)
                        stream = connection.makefile('rb')
                        with stream:
                            while True:
                                line = stream.readline()
                                self.assertTrue(line, 'wrapper exited before SlowPlugin started')
                                message = json.loads(line)
                                if message.get('type') == 'progress' and message.get('value') == 1:
                                    break
                            child_pid = int(pidfile.read_text())
                            if replace_stage:
                                stage.rename(base / 'old-stage')
                                stage.mkdir()
                                (stage / 'keep.txt').write_text('replacement is not owned')
                            launcher.kill()
                            launcher.wait(timeout=5)
                            self.assertEqual(stream.read(), b'', 'orphan bridge did not exit')
                    deadline = time.monotonic() + 3
                    while stage.exists() and not replace_stage and time.monotonic() < deadline:
                        time.sleep(0.02)
                    if replace_stage:
                        self.assertEqual((stage / 'keep.txt').read_text(), 'replacement is not owned')
                        self.assertTrue((base / 'old-stage').exists())
                    else:
                        self.assertFalse(stage.exists(), 'owned unpublished stage survived')
                    self.assertEqual(sentinel.read_text(), 'completed output must survive')
                finally:
                    if launcher.poll() is None:
                        launcher.kill()
                    launcher.wait(timeout=5)
                    launcher.stderr.close()
                    if child_pid is not None:
                        try:
                            os.kill(child_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_force_killed_parent_stops_idle_bridge_and_removes_only_owned_stage(self):
        self.exercise()

    def test_replaced_directory_is_not_deleted_on_parent_death(self):
        self.exercise(replace_stage=True)

    def test_invalid_stage_marker_refuses_before_starting_watch(self):
        spec = importlib.util.spec_from_file_location('wrapper_parent_test', WRAPPER)
        wrapper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wrapper)
        with self.assertRaises(ValueError):
            wrapper.start_parent_watch({'token': 'x', 'parent_watch': {'pid': os.getpid(), 'stage': str(ROOT)}})
        with tempfile.TemporaryDirectory(prefix='.tmp-marker-') as directory:
            root = Path(directory).resolve()
            wrapper.__file__ = str(root/'bridge.py')
            (root/'.studio-parent-watch').write_text('wrong-token')
            with self.assertRaises(ValueError):
                wrapper.start_parent_watch({'token':'correct-token','parent_watch':{'pid':os.getpid(),'stage':str(root)}})


if __name__ == '__main__':
    unittest.main()
