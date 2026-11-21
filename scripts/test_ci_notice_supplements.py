"""Explicit supplements preserve provenance and never imply upstream recovery."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from ci_collect_preview import ROOT
from ci_notice_supplements import supplement


class NoticeSupplementTests(unittest.TestCase):
    def fixture(self, root, ecosystem, name, version, license_id):
        (root/'LICENSES').mkdir()
        for filename in ('MIT-standard.txt','MPL-2.0.txt'):
            shutil.copyfile(ROOT/'LICENSES'/filename,root/'LICENSES'/filename)
        directory=root/'package';directory.mkdir()
        original=directory/('package.json' if ecosystem=='npm' else 'Cargo.toml')
        original.write_text('original upstream declaration and attribution')
        return directory,{'id':ecosystem+':'+name+'@'+version,'ecosystem':ecosystem,'name':name,'version':version,'license':license_id,'notice_files':[],'license_text_missing':True}

    def test_three_exact_declarations_get_transparent_supplements(self):
        for ecosystem,name,version,license_id in [('cargo','selectors','0.38.0','MPL-2.0'),('npm','is-reference','3.0.3','MIT'),('npm','locate-character','3.0.0','MIT')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);directory,p=self.fixture(root,ecosystem,name,version,license_id);output=root/'legal'
                self.assertTrue(supplement(root,output,directory,p))
                self.assertFalse(p['license_text_missing'])
                self.assertTrue(p['original_upstream_notice_missing'])
                self.assertEqual(p['license_text_basis'],'explicit_standard_text_for_exact_declared_license')
                files=[output/f['path'] for f in p['notice_files']]
                manifest=next(f for f in files if f.name in ('Cargo.toml','package.json'))
                self.assertEqual(manifest.read_bytes(),(directory/manifest.name).read_bytes())
                details=json.loads(next(f for f in files if f.name=='SUPPLEMENT.json').read_text())
                self.assertFalse(details['copyright_years_or_holders_invented'])
                self.assertFalse(supplement(root,output,directory,p))

    def test_version_or_license_drift_cannot_receive_approved_supplement(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory,p=self.fixture(root,'npm','is-reference','4.0.0','MIT')
            self.assertFalse(supplement(root,root/'legal',directory,p))
            self.assertTrue(p['license_text_missing'])
            p['version']='3.0.3';p['license']='UNKNOWN'
            with self.assertRaises(ValueError):supplement(root,root/'legal',directory,p)

    def test_original_source_headers_are_retained_without_added_copyright(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory,p=self.fixture(root,'cargo','selectors','0.38.0','MPL-2.0')
            notice='/* Copyright original holder.\n * This Source Code Form is subject to the MPL. */'
            (directory/'lib.rs').write_text(notice+'\npub fn code() {}')
            output=root/'legal';supplement(root,output,directory,p)
            f=next(output/n['path'] for n in p['notice_files'] if n['path'].endswith('SOURCE-NOTICES.json'))
            self.assertEqual(json.loads(f.read_text())['lib.rs'],notice)


if __name__=='__main__':unittest.main()
