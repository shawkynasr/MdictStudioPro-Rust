"""Qualification must preserve duplicates, source order policy and input assets."""
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
from real_corpus import connect, record
from real_rebuild import cross_differences, copy_companions, plan, scan
from prepare_sort_experiment import literal_sort_patch, preserve_order_patch
from patched_interop import ROOT


class RealRebuild(unittest.TestCase):
    def test_new_stream_scan_requires_complete_end_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=connect(root/'scan.sqlite')
            messages=[{'type':'header','kind':'mdx','attributes':{}},
                      {'type':'row','key':'word','text':'body\n'}]
            command=[sys.executable,'-c','print('+repr('\n'.join(json.dumps(m) for m in messages))+')']
            try:
                with self.assertRaises(AssertionError):scan(command,db,'p','mdx',root/'scan.log',10)
            finally:db.close()

    def test_cross_comparison_rejects_lost_duplicate_and_added_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=connect(Path(tmp)/'a.sqlite');b=connect(Path(tmp)/'b.sqlite')
            try:
                for db in [a,b]:
                    record(db,'p','duplicate',b'body\n');record(db,'p','duplicate',b'body\n');db.commit()
                self.assertEqual(cross_differences(a,Path(tmp)/'b.sqlite'),0)
                b.execute('UPDATE records SET p=1');b.commit()
                self.assertGreater(cross_differences(a,Path(tmp)/'b.sqlite'),0)
            finally:a.close();b.close()

    def test_companion_font_override_only_writes_output_and_preserves_css(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'inputs';source.mkdir();destination=root/'output';destination.mkdir()
            css=source/'book.css';css.write_bytes(b'@font-face{src:url(fonts/amiri-regular.ttf)}')
            font=root/'actual-amiri.ttf';font.write_bytes(b'original-font-bytes')
            missing=source/'fonts/amiri-regular.ttf'
            items=[{'source':source/'book.mdx','companions_resolved':[css,missing]}]
            result=copy_companions(items,destination,font)
            self.assertTrue(all(x['status']=='copied_exact_bytes' for x in result))
            self.assertEqual((destination/'fonts/amiri-regular.ttf').read_bytes(),font.read_bytes())
            self.assertFalse(missing.exists())
            self.assertEqual(css.read_bytes(),(destination/'book.css').read_bytes())

    def test_case_insensitive_output_collision_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'one').mkdir();(root/'two').mkdir()
            a=root/'one/Book.mdx';b=root/'two/book.mdx';a.touch();b.touch()
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'cases':[
                {'id':'one','path':str(a)},{'id':'two','path':str(b)}]}))
            with patch('real_rebuild.header_details',return_value={'attributes':{'Encoding':'UTF-8'}}):
                with self.assertRaises(AssertionError):plan(manifest)

    def test_preserve_order_patch_leaves_prior_diagnostic_source_recoverable(self):
        source=literal_sort_patch((ROOT/'patches/studio_legacy_sort.rs').read_text())
        new=preserve_order_patch(source)
        self.assertEqual(preserve_order_patch(new,reverse=True),source)
        self.assertIn('return Ordering::Equal',new)
        with self.assertRaises(ValueError):preserve_order_patch(new)


if __name__=='__main__':unittest.main()
