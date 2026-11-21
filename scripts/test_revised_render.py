"""Grouped converter identity and streaming comparison contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from m2_sizing import ROOT,sha
from m2_revised_render import protected_sources,fingerprints,REFERENCE
from revised_render_lock import check_lock
from revised_render_oracle import records,compare_files,record_summary

class GroupedRenderContracts(unittest.TestCase):
    def test_qualified_sources_and_registry_versions_stay_unchanged(self):
        self.assertEqual(len(protected_sources()),253);self.assertEqual(len(check_lock()),53)
        self.assertIn('m2/revised-render/tests/fixtures/groups.xlsx',fingerprints())
        ref=json.loads((ROOT/REFERENCE).read_text());self.assertFalse(ref['native_run'])
        self.assertEqual([ref['cases'][k]['entries'] for k in ['moe_revised','moe_revised_wfg']],[162636,161182])
        for name,h in ref['legacy_oracle_sha256'].items():self.assertEqual(sha(ROOT/name),h)
    def test_only_reference_sets_and_per_primary_alias_order_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            a=Path(directory)/'a.txt';b=Path(directory)/'b.txt'
            a.write_text('字\n<p>definition</p><span class="polyref"><b>相似詞：</b>甲；乙</span>\n</>\n別乙\n@@@LINK=字\n</>\n別甲\n@@@LINK=字\n</>\n')
            b.write_text('字\n<p>definition</p><span class="polyref"><b>相似詞：</b>乙；甲</span>\n</>\n別甲\n@@@LINK=字\n</>\n別乙\n@@@LINK=字\n</>\n')
            self.assertEqual(compare_files(a,b,'moe_revised'),3);self.assertEqual(record_summary(a,'moe_revised',True),record_summary(b,'moe_revised',True))
            b.write_text(b.read_text().replace('definition','different'))
            with self.assertRaises(AssertionError):compare_files(a,b,'moe_revised')
    def test_record_parser_preserves_blank_lines_and_refuses_incomplete_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'records.txt';p.write_bytes('字\nfirst\n\n\n</>\n字\n\n</>\n'.encode());self.assertEqual(list(records(p)),[{'key':'字','text':'first\n\n'},{'key':'字','text':''}])
            for data in [b'key\nbody\n',b'\nbody\n</>\n',b'key\r\nbody\n</>\n']:
                p.write_bytes(data)
                with self.assertRaises(AssertionError):list(records(p))
if __name__=='__main__':unittest.main()
