"""Independent source bindings and adversarial ledger checks for the new batch."""
import copy
import json
import unittest
from m2_sizing import ROOT
from m2_full_converters import REFERENCE,PROFILES,protected_sources,check_reference,admission
from full_converter_runtime_lock import check_lock
class FullConverters(unittest.TestCase):
    def test_measured_memory_failure_cannot_be_waived(self):
        from check_full_converters_memory import DIRECTORY,review
        r=json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())
        self.assertFalse(review(r)['M2_complete'])
        bad=copy.deepcopy(r);bad['active_case_observation']['peak_RSS_bytes']=384*1024**2
        with self.assertRaises(AssertionError):review(bad)
        bad=copy.deepcopy(r);bad['active_case_observation']['native_output_sha256']='0'*64
        with self.assertRaises(AssertionError):review(bad)
    def test_disk_concise_changes_profile_and_preserves_output_reference(self):
        from m2_full_converters import runtime_receipt,CONCISE_ROWS
        ref=json.loads((ROOT/REFERENCE).read_text());spec=next(c for c in ref['cases'] if c['converter']=='moe_concise');native=runtime_receipt(spec)['receipt']['receipt']
        self.assertEqual(native['profile'],'moe-concise-disk-groups-txt-v1')
        self.assertEqual({k:v for k,v in native.items() if k!='profile'},{k:v for k,v in spec['receipt'].items() if k!='profile'})
        rows=json.loads((ROOT/CONCISE_ROWS).read_text());self.assertEqual(rows['source_sha256'],spec['receipt']['source_sha256']);self.assertEqual(rows['row_digest']['rows'],45178);self.assertEqual(rows['row_digest']['pairs'],677670)
        before=(ROOT/'m2/revised-render/src/publication.rs').read_text().replace('use crate::{budget,sum,Control,Error,Limits,Result,sha256::{Sha256,hex}};','use super::{budget,sum,Control,Error,Limits,Result,sha256::{Sha256,hex}};')
        self.assertEqual((ROOT/'m2/full-converter-runtime/src/concise_publication.rs').read_text(),before)
        text=(ROOT/'m2/xlsx-reader/src/moe/text.rs').read_text().replace('use crate::{Error,Result,py_space};','use super::{Error,Result,py_space};')
        self.assertEqual((ROOT/'m2/full-converter-runtime/src/concise_text.rs').read_text(),text)
        self.assertIn('#[path="concise_text.rs"]mod text;',(ROOT/'m2/full-converter-runtime/src/concise_disk.rs').read_text())
        old=(ROOT/'m2/revised-render/src/lib.rs').read_text();new=(ROOT/'m2/full-converter-runtime/src/concise_disk.rs').read_text()
        self.assertEqual(old[old.index('pub fn render_to_txt('):],new[new.index('pub fn render_to_txt('):])
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
