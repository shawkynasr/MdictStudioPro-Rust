"""Source/graph preservation, exclusive charges and independent preparation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from m2_sizing import ROOT
from m2_cc_pack import protected_sources,REFERENCE,admission
from cc_pack_lock import check_lock
class CcPack(unittest.TestCase):
    def test_previous_sources_and_registry_graph_stay_qualified(self):
        self.assertEqual(len(protected_sources()),300);self.assertEqual(len(check_lock()),69)
        for name in ['runner.rs','index_jobs.rs','converters.rs','concise.rs','concise_disk.rs','concise_publication.rs','concise_text.rs','txt.rs']:
            self.assertEqual((ROOT/'m2/cc-pack-runtime/src'/name).read_bytes(),(ROOT/'m2/real-publication-runtime/src'/name).read_bytes())
    def test_complete_source_reference_stays_bound_to_accepted_inventory(self):
        r=json.loads((ROOT/REFERENCE).read_text());old=json.loads((ROOT/'docs/evidence/m2-real-publication-user-run/m2-real-publication-report.json').read_text());c=next(c for c in old['checks'] if c['case']=='cc-cedict-mdx');self.assertEqual(r['inventory'],c['inventory']);self.assertEqual(r['expected_sorted_scan'],c['index_verifier_reply']['scan']);self.assertEqual(r['inventory']['records'],202884);self.assertLess(r['inventory']['decoded_bytes'],96*1024**2);self.assertLess(r['inventory']['conservative_plan_charge_bytes'],48*1024**2)
    def test_exclusive_memory_and_temporary_charge_are_checked(self):
        old=json.loads((ROOT/'docs/evidence/m2-real-publication-user-run/m2-real-publication-report.json').read_text());v=copy.deepcopy(old['checks'][0]['final_admission']);s=v['shared'];s.update(cc_packings=1,active_operations=1,reserved_memory_bytes=384*1024**2,reserved_temporary_bytes=3072*1024**2);admission(v)
        for memory,temp in [(192*1024**2,3072*1024**2),(384*1024**2,768*1024**2)]:
            bad=copy.deepcopy(v);bad['shared'].update(reserved_memory_bytes=memory,reserved_temporary_bytes=temp)
            with self.assertRaises(AssertionError):admission(bad)
        bad=copy.deepcopy(v);bad['shared'].update(readers=1,active_operations=2,reserved_memory_bytes=480*1024**2,reserved_temporary_bytes=3840*1024**2)
        with self.assertRaises(AssertionError):admission(bad)
    def test_preparation_retains_all_duplicate_ordinals_and_expected_scan(self):
        from index_fixtures import make
        from cc_pack_oracle import prepare_cc
        from real_publication_oracle import FrozenLower
        from bounded_fixtures import digest_row
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);source=directory/'small.mdx';fixture=make(source,duplicates=8);inv,scan,manifest,resources=prepare_cc(source,directory/'prepared');ordered=sorted(fixture['rows'],key=lambda r:FrozenLower()(r[0]));state=0xcbf29ce484222325
            for i,(k,t) in enumerate(ordered):state=digest_row(state,i,k,t.encode())
            self.assertEqual(scan['framed_fnv64'],f'{state:016x}');self.assertEqual(scan['records'],len(fixture['rows']));self.assertEqual(inv['records'],len(manifest.read_text().splitlines()));self.assertEqual(scan['payload_bytes'],sum(len(t.encode()) for _,t in ordered))
if __name__=='__main__':unittest.main()
