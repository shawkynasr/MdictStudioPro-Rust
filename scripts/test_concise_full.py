"""Concise profile isolation, graph and existing normalization contract checks."""
import json
import unittest
from pathlib import Path
from concise_runtime_lock import check_lock
from m2_sizing import ROOT,sha
from m2_concise_full import protected_sources,fingerprints,REFERENCE
from converter_runtime_fixtures import record_digest
from moe_fixtures import compare

class FullConciseContracts(unittest.TestCase):
    def test_previously_qualified_sources_and_registry_graph_unchanged(self):
        self.assertEqual(len(protected_sources()),217)
        self.assertEqual(len(check_lock()),66)
        self.assertIn('m2/concise-runtime/tests/fixtures/concise.xlsx',fingerprints())
    def test_isolated_runtime_keeps_admission_and_controller_semantics(self):
        for name in ['lib.rs','runner.rs']:
            self.assertEqual((ROOT/'m2/concise-runtime/src'/name).read_bytes(),(ROOT/'m2/converter-runtime/src'/name).read_bytes())
        self.assertEqual((ROOT/'m2/concise-runtime/src/main.rs').read_text(),(ROOT/'m2/converter-runtime/src/main.rs').read_text().replace('studio_converter_runtime','studio_concise_runtime'))
        reference=json.loads((ROOT/REFERENCE).read_text())
        self.assertEqual(reference['normalized_record_digest']['records'],44445)
        self.assertEqual(reference['data_rows'],45178)
        self.assertEqual(reference['rectangle_cells'],677685)
        self.assertFalse(reference['native_run'])
        for name,digest in reference['legacy_oracle_sha256'].items():self.assertEqual(sha(ROOT/name),digest)
    def test_accepted_set_order_comparison_preserves_all_other_content(self):
        a=[{'key':'字','text':'<p>definition</p><span class="polyref"><b>相似詞：</b>甲；乙</span>'}]
        b=[{'key':'字','text':'<p>definition</p><span class="polyref"><b>相似詞：</b>乙；甲</span>'}]
        compare(a,b,'moe_concise');self.assertEqual(record_digest(a,'moe_concise'),record_digest(b,'moe_concise'))
        for changed in [[{'key':'different','text':b[0]['text']}],[{'key':'字','text':b[0]['text'].replace('definition','different')}],b+b]:
            with self.assertRaises(AssertionError):compare(a,changed,'moe_concise')

if __name__=='__main__':unittest.main()
