import copy
import unittest
from m2_jobs import protected_sources,fingerprints,compare_events
from application_lock import check_lock

class BackgroundContracts(unittest.TestCase):
    def test_only_the_explicit_module_export_extends_the_qualified_facade(self):
        self.assertEqual(len(protected_sources()),90);self.assertEqual(len(check_lock()),60)
        self.assertIn('m2/application/src/runner.rs',fingerprints());self.assertIn('m2/application/src/runner/tests.rs',fingerprints())
    def test_event_comparison_rejects_identity_revision_and_terminal_loss(self):
        final={'job_id':'job-1','revision':5,'state':'succeeded','latest_progress':{'job_id':'job-1'}}
        queued={'job_id':'job-1','revision':1,'state':'queued','latest_progress':None}
        compare_events([queued,final],[final])
        for events in [[queued],[final,queued],[final,final],[{**queued,'job_id':'other'},final]]:
            with self.assertRaises(AssertionError):compare_events(events,[final])
        bad=copy.deepcopy(final);bad['latest_progress']['job_id']='other'
        with self.assertRaises(AssertionError):compare_events([bad],[bad])

if __name__=='__main__':unittest.main()
