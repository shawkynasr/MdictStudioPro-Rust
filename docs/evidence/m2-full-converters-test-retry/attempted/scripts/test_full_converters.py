"""Independent source bindings and adversarial ledger checks for the new batch."""
import copy
import json
import unittest
from m2_sizing import ROOT
from m2_full_converters import REFERENCE,PROFILES,protected_sources,check_reference,admission
from full_converter_runtime_lock import check_lock
class FullConverters(unittest.TestCase):
    def test_partial_attempt_cannot_accept_changed_receipt_or_excess_RSS(self):
        from check_full_converters_attempt import DIRECTORY,review
        report=json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())
        self.assertEqual(review(report)['controller_exchanges'],415)
        for value in [0,384*1024**2+1]:
            bad=copy.deepcopy(report);bad['checks'][0]['peak_RSS_bytes']=value
            with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(report);bad['checks'][0]['receipt']['receipt']['receipt']['entries']-=1
        with self.assertRaises(AssertionError):review(bad)
    def test_composed_dependencies_and_qualified_source_identity(self):
        self.assertEqual(len(protected_sources()),265);self.assertEqual(len(check_lock()),68)
        for name in ['runner.rs','txt.rs']:
            self.assertEqual((ROOT/'m2/full-converter-runtime/src'/name).read_bytes(),(ROOT/'m2/cc-runtime/src'/name).read_bytes())
    def test_reference_rejects_wrong_accepted_output_and_profile(self):
        ref=json.loads((ROOT/REFERENCE).read_text());check_reference(ref);self.assertEqual(len(ref['cases']),6)
        for field,value in [('native_output_sha256','0'*64),('profile','small_moe')]:
            bad=copy.deepcopy(ref);bad['cases'][0][field]=value
            with self.assertRaises(AssertionError):check_reference(bad)
        for c in ref['cases']:
            self.assertLess(len(json.dumps(c['receipt']).encode()),4096)
            self.assertNotIn('row_source',c['receipt']);self.assertNotIn('headers',c['receipt'])
    def test_ledger_rejects_undercharge_and_reader_conversion_overlap(self):
        old=json.loads((ROOT/'docs/evidence/m2-cc-full-user-run/m2-cc-full-report.json').read_text())
        base=copy.deepcopy(old['checks'][0]['after_conversion_admission']);admission(base)
        s=base['shared'];s.update(conversions=1,active_operations=1,reserved_memory_bytes=384*1024**2,reserved_temporary_bytes=768*1024**2);admission(base)
        bad=copy.deepcopy(base);bad['shared']['reserved_memory_bytes']=96*1024**2
        with self.assertRaises(AssertionError):admission(bad)
        bad=copy.deepcopy(base);bad['shared'].update(readers=1,active_operations=2,reserved_memory_bytes=480*1024**2,reserved_temporary_bytes=1536*1024**2)
        with self.assertRaises(AssertionError):admission(bad)
if __name__=='__main__':unittest.main()
