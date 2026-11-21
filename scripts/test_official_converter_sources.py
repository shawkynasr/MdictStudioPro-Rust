import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile
from m2_official_mini_idioms import extract_sources
class OfficialSourcePreparationContracts(unittest.TestCase):
    def spec(self,p,member,data):return {'archive':p.name,'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'member':member,'source_bytes':len(data),'source_sha256':hashlib.sha256(data).hexdigest()}
    def test_exact_member_only_is_extracted_and_other_workbooks_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'dataset.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('main.xlsx',b'data');z.writestr('notes.xlsx',b'notes')
            result=extract_sources(root,root/'sources',[self.spec(archive,'main.xlsx',b'data')]);self.assertEqual(result['main.xlsx'].read_bytes(),b'data');self.assertEqual([p.name for p in (root/'sources').iterdir()],['main.xlsx'])
    def test_unmatched_archive_and_traversal_member_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'bad.zip'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.xlsx',b'bad')
            spec=self.spec(archive,'../escape.xlsx',b'bad')
            with self.assertRaises(AssertionError):extract_sources(root,root/'sources',[spec])
            self.assertFalse((root.parent/'escape.xlsx').exists());spec['archive_sha256']='0'*64
            with self.assertRaises(AssertionError):extract_sources(root,root/'other',[spec])
if __name__=='__main__':unittest.main()
