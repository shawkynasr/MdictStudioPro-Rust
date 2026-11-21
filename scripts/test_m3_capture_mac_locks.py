"""Capture must preserve actual bytes and refuse missing/escaping input locks."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from m3_capture_mac_locks import LOCKS,collect

class CaptureLocksTests(unittest.TestCase):
    def fixture(self,root):
        expected={}
        for name in LOCKS:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
            data=b'{"lockfileVersion":3}\n' if name.endswith('.json') else b'version = 3\n'
            p.write_bytes(data);expected[name]=hashlib.sha256(data).hexdigest()
        return expected

    def test_capture_preserves_original_and_copied_bytes_and_marks_unreviewed_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';out=Path(temp)/'output';expected=self.fixture(root)
            name=LOCKS[0];p=root/name;p.write_bytes(p.read_bytes()+b'# new formatting\n')
            before={n:(root/n).read_bytes() for n in LOCKS}
            captured,issues,unchanged=collect(root,out,expected)
            self.assertFalse(issues);self.assertTrue(unchanged);self.assertFalse(captured[name]['matches_last_reviewed'])
            self.assertEqual({n:(root/n).read_bytes() for n in LOCKS},before)
            for n in LOCKS:self.assertEqual((out/'locks'/n).read_bytes(),before[n])

    def test_missing_and_symlink_locks_are_reported_without_reading_or_replacing_them(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';out=Path(temp)/'output';expected=self.fixture(root)
            (root/LOCKS[0]).unlink();(root/LOCKS[1]).unlink()
            external=Path(temp)/'external';external.write_bytes(b'private outside bytes')
            (root/LOCKS[1]).symlink_to(external)
            captured,issues,unchanged=collect(root,out,expected)
            self.assertEqual(len(issues),2);self.assertTrue(unchanged)
            self.assertNotIn(LOCKS[0],captured);self.assertNotIn(LOCKS[1],captured)
            self.assertFalse((root/LOCKS[0]).exists());self.assertEqual(external.read_bytes(),b'private outside bytes')
