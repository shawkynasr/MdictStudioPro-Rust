"""Bounded new-runtime contracts and independent disk preparation checks."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from m2_sizing import ROOT
from m2_real_publication import protected_sources,admission
from real_publication_lock import check_lock
from real_publication_oracle import FrozenLower,prepare
from large_io_oracle import digest
class RealPublication(unittest.TestCase):
    def test_qualified_sources_graph_and_unchanged_workers(self):
        self.assertEqual(len(protected_sources()),282);self.assertEqual(len(check_lock()),68)
        for name in ['runner.rs','converters.rs','concise.rs','concise_disk.rs','concise_publication.rs','concise_text.rs','txt.rs']:
            self.assertEqual((ROOT/'m2/full-converter-runtime/src'/name).read_bytes(),(ROOT/'m2/real-publication-runtime/src'/name).read_bytes())
    def test_frozen_contextual_lowercase(self):
        lower=FrozenLower()
        for original,expected in [('ΣΟΣ','σος'),('ΟΣ\u0301','ος\u0301'),('ΟΣΑ','οσα'),('İ','i\u0307'),('\U00010d50','\U00010d70'),('مرحبا','مرحبا')]:self.assertEqual(lower(original),expected)
    def test_full_disk_preparation_preserves_duplicate_records_and_binary_payloads(self):
        from index_fixtures import make
        from bounded_fixtures import write,rows
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);source=directory/'fixture.mdx';fixture=make(source,duplicates=4);info,manifest,resources=prepare(source,'mdx',directory/'mdx-prepared');expected=sorted(((k,t.encode()) for k,t in fixture['rows']),key=lambda r:FrozenLower()(r[0]));self.assertEqual(info['expected_sorted_records'],digest(expected));self.assertFalse(info['packing_blockers']);self.assertEqual(len(manifest.read_text().splitlines()),len(expected))
            source=directory/'fixture.mdd';write(source,8,'mdd',payload_size=16);info,manifest,resources=prepare(source,'mdd',directory/'mdd-prepared');expected=sorted(rows(8,'mdd',16),key=lambda r:FrozenLower()(r[0]));self.assertEqual(info['expected_sorted_records'],digest(expected));self.assertEqual(len(list(resources.iterdir())),8)
    def test_index_charge_is_exclusive_and_counts_three_GiB_temporary(self):
        report=json.loads((ROOT/'docs/evidence/m2-full-converters-user-run/m2-full-converters-report.json').read_text());v=copy.deepcopy(report['checks'][0]['final_admission']);s=v['shared'];s.update(index_builds=1,active_operations=1,reserved_memory_bytes=384*1024**2,reserved_temporary_bytes=3072*1024**2);admission(v)
        bad=copy.deepcopy(v);bad['shared']['reserved_temporary_bytes']=768*1024**2
        with self.assertRaises(AssertionError):admission(bad)
        bad=copy.deepcopy(v);bad['shared'].update(readers=1,active_operations=2,reserved_memory_bytes=480*1024**2,reserved_temporary_bytes=3840*1024**2)
        with self.assertRaises(AssertionError):admission(bad)
if __name__=='__main__':unittest.main()
