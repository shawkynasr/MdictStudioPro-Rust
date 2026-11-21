from pathlib import Path
import tempfile
import unittest
from m2_resources import relative_resource_path, compare_resources, verify_extracted


class ResourceContracts(unittest.TestCase):
    def test_portable_archive_paths_preserve_unicode_and_refuse_traversal(self):
        self.assertEqual(relative_resource_path('\\fonts\\字.ttf'), 'fonts/字.ttf')
        for key in ['../x','a/../x','a//x','//server/x','C:\\x','a:stream','a.','COM1.txt','LPT³','a/']:
            with self.assertRaises(AssertionError): relative_resource_path(key)

    def test_binary_comparison_preserves_zero_ff_empty_and_exact_keys(self):
        rows = [{'key':'a','bytes':[0,255,128,0]}, {'key':'empty','bytes':[]}]
        compare_resources(rows, [('a',b'\0\xff\x80\0'),('empty',b'')])
        for bad in [[('a',b'\0\xff\x80')], [('A',b'\0\xff\x80\0'),('empty',b'')]]:
            with self.assertRaises(AssertionError): compare_resources(rows,bad)

    def test_extraction_verifier_rejects_extra_files_bytes_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'file').write_bytes(b'\0\xff')
            rows=[{'key':'file','bytes':[0,255]}]
            self.assertEqual(len(verify_extracted(root,rows)),1)
            (root/'extra').write_bytes(b'x')
            with self.assertRaises(AssertionError): verify_extracted(root,rows)
            (root/'extra').unlink(); (root/'file').write_bytes(b'wrong')
            with self.assertRaises(AssertionError): verify_extracted(root,rows)
            (root/'file').unlink()
            try: (root/'file').symlink_to('missing')
            except (OSError, NotImplementedError): return
            with self.assertRaises(AssertionError): verify_extracted(root,rows)


if __name__ == '__main__': unittest.main()
