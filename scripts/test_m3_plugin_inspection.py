"""Exercise discovery through the authenticated child protocol, not in-process imports."""
import json
from pathlib import Path
import tempfile
import unittest
import test_m3_python_plugin as bridge_tests


class InspectionTests(unittest.TestCase):
    def inspect(self, code=None):
        if code is None:
            return bridge_tests.PythonPluginTests().child('', mode='inspect')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'selected.py'
            p.write_text(code,encoding='utf-8')
            return bridge_tests.PythonPluginTests().child('',plugin=p,mode='inspect')

    def test_discovers_all_local_concrete_classes_without_conversion(self):
        r=self.inspect()
        self.assertEqual(r['code'],0,r['stderr'])
        self.assertEqual([c['class_name'] for c in r['catalog']['classes']],['FailingPlugin','NoisyPlugin','OptionsPlugin','SlowPlugin'])
        self.assertIsNone(r['output'])
        self.assertFalse(r['sidecar'])
        self.assertIn('Native stdout write',r['stdout'])
        self.assertEqual(r['messages'][-1]['type'],'done')
        options=next(c for c in r['catalog']['classes'] if c['class_name']=='OptionsPlugin')
        self.assertEqual([f['key'] for f in options['fields']],['prefix','uppercase'])
        self.assertIsNone(options['schema_error'])

    def test_no_constructor_runs_and_abstract_or_imported_classes_are_excluded(self):
        r=self.inspect('''from base_plugin import BaseConverterPlugin
class Abstract(BaseConverterPlugin): pass
class Concrete(BaseConverterPlugin):
    def __init__(self): raise RuntimeError('constructor must not run')
    def convert(self,*args): raise RuntimeError('conversion must not run')
Alias = Concrete
''')
        self.assertEqual(r['code'],0,r['stderr'])
        self.assertEqual(len(r['catalog']['classes']),1)
        self.assertIsNone(r['output'])

    def test_choice_numeric_defaults_and_unsupported_schema_fallback(self):
        schema=[{'key':'mode','type':'choice','default':'字','choices':['字','مرحبا']}, {'key':'count','type':'number','default':2.5}]
        prefix='from base_plugin import BaseConverterPlugin\nclass Demo(BaseConverterPlugin):\n    def convert(self,*args): pass\n    options_schema = '
        r=self.inspect(prefix+repr(schema)+'\n')
        self.assertEqual(r['code'],0,r['stderr'])
        self.assertEqual(r['catalog']['classes'][0]['fields'][0]['choices'],['字','مرحبا'])
        for bad in [[{'key':'x','type':'file','default':''}],[{'key':'x','type':'number','default':True}],schema+schema, [{'key':'x','type':'choice','default':'z','choices':['a']}],[{'key':'x','type':'string','default':'x'*2049}], [{'key':'x','type':'string','default':'ok','required':True}]]:
            with self.subTest(schema=bad):
                r=self.inspect(prefix+repr(bad)+'\n')
                self.assertEqual(r['code'],0,r['stderr'])
                cls=r['catalog']['classes'][0]
                self.assertEqual(cls['fields'],[])
                self.assertTrue(cls['schema_error'])

    def test_import_errors_and_too_many_classes_return_no_catalog(self):
        for code in ["raise RuntimeError('import fixture failure')", 'from base_plugin import BaseConverterPlugin\n'+''.join(f'class C{i}(BaseConverterPlugin):\n def convert(self,*args):pass\n' for i in range(17))]:
            r=self.inspect(code)
            self.assertEqual(r['code'],1)
            self.assertEqual(r['messages'][-1]['type'],'error')
            self.assertIsNone(r['catalog'])
