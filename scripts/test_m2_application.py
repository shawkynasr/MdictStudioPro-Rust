import copy
import unittest
from application_lock import ROOT,packages,check_lock
from m2_application import protected_sources,fingerprints,check_progress

class ApplicationContracts(unittest.TestCase):
    def test_joint_lock_uses_exact_qualified_union_without_upgrades(self):
        graph=check_lock();self.assertEqual(len(graph),60)
        self.assertEqual(len([p for p in packages() if p['name']=='studio-application']),1)
        self.assertFalse(any(p['name']=='studio-cli' for p in packages()))
        derive=next(p for p in packages() if p['name']=='serde_derive');self.assertIn('syn 3.0.9',derive['dependencies'])
    def test_all_qualified_sources_are_unchanged_and_facade_is_fingerprinted(self):
        self.assertGreater(len(protected_sources()),60)
        paths=fingerprints()
        for name in ['m2/application/src/lib.rs','m2/application/src/error.rs','m2/application/src/job.rs','m2/application/tests/workflows.rs','m2/application/Cargo.lock']:
            self.assertIn(name,paths)
    def test_progress_comparison_rejects_mixed_jobs_missing_stages_and_false_commit(self):
        events=[{'job_id':'cli-conversion','stage':s,'phase':p,'completed':1,'total':1} for s,p in [('reading_workbook','complete'),('converting','converting'),('validating_output','writing'),('publishing','published')]]
        check_progress(events,True)
        for changes in ['identity','counter','stage','commit']:
            bad=copy.deepcopy(events)
            if changes=='identity':bad[1]['job_id']='other-job'
            elif changes=='counter':bad[1]['completed']=2
            elif changes=='stage':bad.pop(2)
            else:bad[-1]['phase']='writing'
            with self.assertRaises(AssertionError):check_progress(bad,True)
        check_progress(events[1:3],False,False)

if __name__=='__main__':unittest.main()
