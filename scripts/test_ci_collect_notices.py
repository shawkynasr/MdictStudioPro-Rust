"""Validate actual notice copying, dependency gaps and exclusion of owned code."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from ci_collect_notices import collect


class LicenseInventoryTests(unittest.TestCase):
    def fixture(self, root):
        (root/'LICENSE').write_text('project AGPL fixture')
        (root/'THIRD_PARTY_NOTICES.md').write_text('component exceptions')
        (root/'LICENSES').mkdir()
        (root/'LICENSES/GPL-3.0.txt').write_text('unchanged historical GPL fixture')
        frontend=root/'m3/desktop';frontend.mkdir(parents=True)
        lock={'packages':{'':{},'node_modules/sample':{'version':'1.0','dev':True},'node_modules/other-platform':{'version':'1.0','optional':True}}}
        (frontend/'package-lock.json').write_text(json.dumps(lock))
        package=frontend/'node_modules/sample';package.mkdir(parents=True)
        (package/'package.json').write_text(json.dumps({'name':'sample','version':'1.0','license':'MIT'}))
        (package/'LICENSE').write_bytes(b'Copyright sample\nMIT exact notice\r\n')
        vendor=root/'vendor/mdictlib';vendor.mkdir(parents=True)
        (vendor/'LICENSE').write_text('upstream unchanged MIT text')
        return {'packages':[{'name':'studio-owned','version':'0.1','source':None,'manifest_path':str(frontend/'src-tauri/Cargo.toml'),'id':'owned'},
                            {'name':'mdictlib','version':'0.2.8','source':None,'manifest_path':str(vendor/'Cargo.toml'),'id':'patched-vendor','license':'MIT'}]},package

    def test_collects_vendor_not_owned_code_and_preserves_notice_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);metadata,package=self.fixture(root);out=root/'legal'
            r=collect(root,metadata,out,'x86_64-pc-windows-msvc')
            self.assertEqual(len(r['first_party_packages']),1)
            self.assertEqual(len(r['packages']),2)
            self.assertFalse(r['missing_license_texts'])
            self.assertFalse(r['missing_license_declarations'])
            self.assertEqual(len(r['absent_optional_packages']),1)
            notice=next(p for p in r['packages'] if p['ecosystem']=='npm')['notice_files'][0]
            self.assertEqual((out/notice['path']).read_bytes(),(package/'LICENSE').read_bytes())
            self.assertEqual(notice['sha256'],hashlib.sha256((package/'LICENSE').read_bytes()).hexdigest())
            self.assertFalse(r['legal_compatibility_qualified'])
            with self.assertRaises(FileExistsError):collect(root,metadata,out,'x86_64-pc-windows-msvc')

    def test_native_wrapper_notices_require_same_version_and_repository(self):
        for child_version in ('1.0','2.0'):
            with self.subTest(child_version=child_version), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);metadata,_=self.fixture(root)
                frontend=root/'m3/desktop'
                lock=json.loads((frontend/'package-lock.json').read_text())
                for location,name,version in [('node_modules/esbuild','esbuild','1.0'),('node_modules/@esbuild/darwin-x64','@esbuild/darwin-x64',child_version)]:
                    directory=frontend/location;directory.mkdir(parents=True)
                    (directory/'package.json').write_text(json.dumps({'name':name,'version':version,'license':'MIT','repository':'https://github.com/evanw/esbuild'}))
                    lock['packages'][location]={'version':version}
                    if name=='esbuild':(directory/'LICENSE').write_bytes(b'original esbuild distribution license')
                (frontend/'package-lock.json').write_text(json.dumps(lock))
                report=collect(root,metadata,root/'legal','x86_64-apple-darwin')
                child=next(p for p in report['packages'] if p['name']=='@esbuild/darwin-x64')
                self.assertEqual(child['license_text_missing'], child_version!='1.0')
                if child_version=='1.0':self.assertEqual(child['notice_files'][0]['origin'],'same_version_distribution_wrapper')

    def test_missing_notices_and_declarations_remain_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);metadata,package=self.fixture(root)
            (package/'LICENSE').unlink()
            data=json.loads((package/'package.json').read_text());data.pop('license');(package/'package.json').write_text(json.dumps(data))
            r=collect(root,metadata,root/'legal','x86_64-apple-darwin')
            self.assertEqual(len(r['missing_license_texts']),1)
            self.assertEqual(len(r['missing_license_declarations']),1)

    def test_required_uninstalled_package_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);metadata,package=self.fixture(root)
            (package/'package.json').unlink()
            with self.assertRaises(FileNotFoundError):collect(root,metadata,root/'legal','x86_64-apple-darwin')


if __name__=='__main__':unittest.main()
