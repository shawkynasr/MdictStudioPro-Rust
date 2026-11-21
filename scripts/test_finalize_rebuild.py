"""Finalize only when every previous scan and current file identity still agrees."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from finalize_real_rebuild import finalize
from patched_interop import ROOT


class FinalizeRebuild(unittest.TestCase):
    def fixture(self,root):
        out=root/'rebuild-out';stage=out/'work/dictionaries';stage.mkdir(parents=True)
        source=root/'source.mdx';source.write_bytes(b'original dictionary')
        rebuilt=stage/'source.mdx';rebuilt.write_bytes(b'rebuilt dictionary')
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        scan={'records':1,'attributes':{'Title':'original'},'ordered_key_payload_sha256':'ordered-identity'}
        case={'status':'passed_rebuild_records_metadata_and_order','different_key_payload_counts':0,
            'source':str(source),'source_sha256':sha(source),'output_name':'source.mdx','output_sha256':sha(rebuilt),
            'builder':{'records':1},'source_scans':{'r':scan,'p':scan},'rebuilt_scans':{'r':scan,'p':scan},
            'lookups':{'word':{'status':'passed'}},'structural_audit':{'records':1,'status':'structural_audit_passed','sha256':sha(rebuilt),'sha256_after':sha(rebuilt)}}
        report={'status':'rebuild_records_passed_companions_pending','engine_revision':6,'cases':[case],
            'input_integrity':{str(source):{'before':sha(source),'after':sha(source)}},
            'companions':[{'status':'missing','relative_output':'fonts/amiri-regular.ttf','declared':str(root/'fonts/amiri-regular.ttf')}]}
        (out/'real-rebuild-report.json').write_text(json.dumps(report))
        font=root/'original-font.ttf';font.write_bytes((ROOT/'baseline/resource-probe/studio-probe.ttf').read_bytes())
        return out,font,source,rebuilt

    def test_finalization_copies_only_font_and_preserves_before_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out,font,source,rebuilt=self.fixture(Path(tmp));original=source.read_bytes()
            self.assertEqual(finalize(out,font),0)
            report=json.loads((out/'real-rebuild-report.json').read_text())
            self.assertEqual(report['status'],'real_rebuild_offline_passed_native_untested')
            self.assertEqual((out/'verified-dictionaries/fonts/amiri-regular.ttf').read_bytes(),font.read_bytes())
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(json.loads((out/'real-rebuild-report.before-finalize.json').read_text())['status'],'rebuild_records_passed_companions_pending')
            self.assertFalse((out/'work/dictionaries').exists())

    def test_changed_source_or_output_prevents_publication(self):
        for which in ['source','output']:
            with self.subTest(which=which),tempfile.TemporaryDirectory() as tmp:
                out,font,source,rebuilt=self.fixture(Path(tmp))
                (source if which=='source' else rebuilt).write_bytes(b'changed')
                with self.assertRaises(AssertionError):finalize(out,font)
                self.assertFalse((out/'verified-dictionaries').exists())
                self.assertFalse((out/'work/dictionaries/fonts/amiri-regular.ttf').exists())

    def test_extra_unverified_dictionary_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            out,font,source,rebuilt=self.fixture(Path(tmp))
            (rebuilt.parent/'unexpected.mdx').write_bytes(b'unverified')
            with self.assertRaises(AssertionError):finalize(out,font)
            self.assertFalse((out/'verified-dictionaries').exists())


if __name__=='__main__':unittest.main()
