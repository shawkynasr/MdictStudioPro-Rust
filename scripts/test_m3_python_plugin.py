"""Executable child-wrapper tests, independent of Rust/native availability."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PythonPluginTests(unittest.TestCase):
    def child(self, class_name, plugin=None, source=None, options=None, mode=None, parent_watch=False):
        with tempfile.TemporaryDirectory(prefix='.tmp-wrapper-') as tmp:
            root = Path(tmp)
            original = plugin or ROOT / 'm3/fixtures/noisy_plugin.py'
            snapshot = root / 'plugin.py'
            shutil.copyfile(original, snapshot)
            input_file = root / 'input.txt'
            input_file.write_bytes((source or ROOT / 'm3/fixtures/build-source.txt').read_bytes())
            output = root / 'output.txt'
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(1)
                listener.settimeout(5)
                config = {'port': listener.getsockname()[1], 'token': 'fixture-secret', 'base': str(ROOT/'m3/txt-runtime/src/base_plugin.py'), 'snapshot': str(snapshot), 'original_plugin': str(original), 'class_name': class_name, 'input': str(input_file), 'output': str(output)}
                wrapper_path = ROOT/'m3/txt-runtime/src/plugin_wrapper.py'
                if parent_watch:
                    wrapper_path = root/'bridge.py'
                    shutil.copyfile(ROOT/'m3/txt-runtime/src/plugin_wrapper.py', wrapper_path)
                    (root/'.studio-parent-watch').write_text('fixture-secret')
                    config['parent_watch'] = {'pid':os.getpid(),'stage':str(root.resolve())}
                if options is not None: config['options']=options
                if mode: config.update(mode=mode,catalog=str(root/'catalog.json'))
                with (root/'stdout').open('wb') as stdout, (root/'stderr').open('wb') as stderr:
                    process = subprocess.Popen([sys.executable, '-u', str(wrapper_path)], stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=root, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'})
                    try:
                        process.stdin.write(json.dumps(config).encode()+b'\n')
                        process.stdin.close()
                        connection, _ = listener.accept()
                        with connection:
                            connection.settimeout(5)
                            with connection.makefile('rb') as stream:
                                messages = [json.loads(line) for line in stream]
                        code = process.wait(timeout=5)
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait(timeout=5)
                return {'catalog': json.loads((root/'catalog.json').read_text()) if (root/'catalog.json').exists() else None, 'messages': messages, 'code': code, 'stdout': (root/'stdout').read_text(), 'stderr': (root/'stderr').read_text(), 'output': output.read_bytes() if output.exists() else None, 'input': input_file.read_bytes(), 'sidecar': (root/'input.txt_log.txt').exists()}

    def test_native_and_python_stdout_do_not_pollute_authenticated_protocol(self):
        result = self.child('NoisyPlugin')
        self.assertEqual(result['code'], 0)
        self.assertEqual(result['messages'][0], {'type': 'hello', 'token': 'fixture-secret', 'version': 1})
        self.assertEqual(result['messages'][-1]['type'], 'done')
        self.assertIn('ordinary stdout', result['stdout'])
        self.assertIn('Native stdout write: not protocol JSON', result['stdout'])
        self.assertIn('Fixture stderr warning', result['stderr'])
        self.assertTrue(any(m['type']=='log' and 'العربية' in m['message'] for m in result['messages']))
        self.assertEqual(result['output'], result['input'])
        self.assertTrue(result['sidecar'])

    def test_plugin_exception_and_wrong_class_are_structured_failures(self):
        for class_name in ['FailingPlugin', 'MissingPlugin']:
            result = self.child(class_name)
            self.assertEqual(result['code'], 1)
            self.assertEqual(result['messages'][-1]['type'], 'error')
            self.assertIn('Traceback', result['stderr'])
            self.assertFalse(any(m['type']=='done' for m in result['messages']))

    def test_original_cc_cedict_plugin_signature_runs_without_original_input_side_effects(self):
        source=ROOT/'m3/fixtures/cedict.txt'
        result=self.child('CCCEDICTPlugin',ROOT/'baseline/legacy/plugins/cccedict_plugin.py',source)
        self.assertEqual(result['code'],0,result['stderr'])
        self.assertIn('字',result['output'].decode('utf-8'))
        self.assertIn('</>',result['output'].decode('utf-8'))
        self.assertTrue(result['sidecar'])
        self.assertEqual(result['input'],source.read_bytes())

    def test_options_are_delivered_before_convert_and_empty_options_preserve_legacy(self):
        result=self.child('OptionsPlugin', options={'prefix':'字 مرحبا','uppercase':True})
        self.assertEqual(result['code'],0,result['stderr'])
        self.assertIn('字 مرحبا',result['output'].decode('utf-8'))
        self.assertIn('APPLE',result['output'].decode('utf-8'))
        self.assertEqual(self.child('NoisyPlugin',options={})['code'],0)

    def test_bad_options_fail_before_plugin_code_or_output(self):
        for options in [{'x':{}},{'x':[]},{'x':None},{'bad-key':True},{'x':'字'*683},{'x':9007199254740992},{f'k{i}':True for i in range(65)},{f'k{i}':'x'*2048 for i in range(5)}]:
            with self.subTest(options=str(options)[:60]):
                result=self.child('OptionsPlugin',options=options)
                self.assertEqual(result['code'],1)
                self.assertEqual(result['messages'][-1]['type'],'error')
                self.assertIsNone(result['output'])
                self.assertNotIn('Plugin import',result['stdout'])

    def test_parent_watch_preserves_successful_conversion_and_structured_failure(self):
        result = self.child('NoisyPlugin', parent_watch=True)
        self.assertEqual(result['code'], 0, result['stderr'])
        self.assertEqual(result['output'], result['input'])
        self.assertEqual(self.child('FailingPlugin', parent_watch=True)['code'], 1)
