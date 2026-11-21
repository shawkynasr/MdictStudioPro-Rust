"""Exercise the delivered folder fixtures through the real Python wrapper."""
from pathlib import Path
import unittest
import test_m3_python_plugin as bridge_tests

ROOT=Path(__file__).resolve().parents[1]


class FolderFixtures(unittest.TestCase):
    def test_folder_fixture_has_three_choices_and_one_explicit_import_failure(self):
        choices=[]
        for name in ['copy_a.py','copy_b.py','options.py','broken.py']:
            result=bridge_tests.PythonPluginTests().child('',plugin=ROOT/'m3/fixtures/plugin-folder'/name,mode='inspect')
            if name=='broken.py':
                self.assertEqual(result['code'],1)
                self.assertIn('Intentional folder discovery fixture failure',result['messages'][-1]['message'])
            else:
                self.assertEqual(result['code'],0,result['stderr'])
                choices.extend((name,c['class_name'],c['name']) for c in result['catalog']['classes'])
                self.assertIsNone(result['output'])
        self.assertEqual(len(choices),3)
        self.assertEqual(choices[0][1:],choices[1][1:])
        self.assertNotEqual(choices[0][0],choices[1][0])

    def test_options_fixture_conversion_has_exact_multilingual_prefix_and_uppercase_source(self):
        r=bridge_tests.PythonPluginTests().child('OptionsPlugin',plugin=ROOT/'m3/fixtures/plugin-folder/options.py',options={'prefix':'字 مرحبا','uppercase':True})
        self.assertEqual(r['code'],0,r['stderr'])
        expected=('plugin-options\n字 مرحبا\n</>\n'+r['input'].decode('utf-8').upper()).encode('utf-8')
        self.assertEqual(r['output'],expected)
