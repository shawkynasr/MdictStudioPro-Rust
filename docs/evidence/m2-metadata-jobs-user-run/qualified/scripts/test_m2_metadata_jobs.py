import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from m2_metadata_jobs import protected_sources,cases,compare_job,compare_file
from test_m2_metadata import fixture
from v2_import_lock import check_lock

class MetadataPublicationContracts(unittest.TestCase):
    def test_accepted_metadata_export_and_dependency_identities_are_pinned(self):
        self.assertEqual(len(protected_sources()),126);self.assertEqual(len(check_lock()),61)
    def test_case_matrix_has_recovery_and_new_native_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            items=cases(Path(tmp)/'jobs');self.assertEqual(len(items),28);self.assertEqual(sum(not c['refusal'] for c in items),10);self.assertEqual(sum(bool(c['refusal']) for c in items),18)
            names=[c['name'] for c in items];self.assertLess(names.index('missing-source'),names.index('recovery-pack'));self.assertEqual(sum(c['native'] for c in items),2)
            self.assertEqual((Path(tmp)/'jobs/existing.mdx').read_bytes(),b'KEEP_SENTINEL')
    def test_typed_failures_cannot_claim_partial_output_or_certain_panic(self):
        actual={'state':'failed','response':None,'error':{'code':'io'},'publication_uncertain':False};case={'refusal':'io'};compare_job(actual,case,False)
        changed=copy.deepcopy(actual);changed['response']={'partial':True}
        with self.assertRaises(AssertionError):compare_job(changed,case,False)
        changed=copy.deepcopy(actual);changed['publication_uncertain']=True
        with self.assertRaises(AssertionError):compare_job(changed,case,False)
    def test_physical_oracle_preserves_stable_duplicates_and_exact_metadata(self):
        data=fixture('<Dictionary GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" Encoding="UTF-8" Format="Html" Title="Title" Description="A&#10;B" StyleSheet="" Compact="No" KeyCaseSensitive="No" StripKey="No"/>')
        rows=[{'key':'apple','text':'first'},{'key':'Apple','text':'upper'},{'key':'apple','text':'second'}];expected=[(r['key'],r['text']) for r in rows]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'packed.mdx';path.write_bytes(data)
            case={'native':False,'request':{'operation':'pack_mdx','destination':str(path),'encoding':'utf8','metadata':{'title':'Title','description':'A\nB','stylesheet':'','extra':{}},'entries':rows}}
            response={'destination':str(path),'profile':'mdict-v2-metadata-v1','operation':'pack_metadata_mdx','records':3,'file_bytes':len(data)}
            with patch('m2_metadata_jobs.audit',return_value={'status':'structural_audit_passed'}),patch('m2_metadata_jobs.read_legacy_physical',return_value=expected):
                self.assertTrue(compare_file(case,response)['metadata_records_wire_passed'])
                wrong=copy.deepcopy(case);wrong['request']['metadata']['description']='wrong'
                with self.assertRaises(AssertionError):compare_file(wrong,response)
            with patch('m2_metadata_jobs.audit',return_value={'status':'structural_audit_passed'}),patch('m2_metadata_jobs.read_legacy_physical',return_value=expected[:2]):
                with self.assertRaises(AssertionError):compare_file(case,response)
if __name__=='__main__':unittest.main()
