import copy
import unittest
from m2_import_jobs import protected_sources,request_for,compare_response,validate_background
from v2_import_lock import check_lock
from unittest.mock import patch

class ImportApplicationContracts(unittest.TestCase):
    def test_accepted_sources_preserved_except_explicit_module_export(self):
        self.assertEqual(len(protected_sources()),114);self.assertEqual(len(check_lock()),61)
    def test_requests_select_source_policy_and_actions_explicitly(self):
        case={'kind':'mdx','path':'foreign.mdx','policy':'raw_exact'};request=request_for(case)
        self.assertEqual(request['source'],{'kind':'mdx','policy':'raw_exact'});self.assertEqual(len(request['actions']),30)
        request=request_for({'kind':'mdd','path':'foreign.mdd'});self.assertEqual(request['source'],{'kind':'mdd'});self.assertTrue(all(a['action']=='resource' for a in request['actions']))
    def test_comparator_rejects_missing_duplicate_and_changed_query_outcome(self):
        rows=[{'key':'apple','text':'first'},{'key':'apple','text':'second'}]
        case={'kind':'mdx','path':'unused','policy':'raw_exact','rows':rows,'case_sensitive':False,'strip':False}
        request={'actions':[{'action':'lookup','query':'apple'}]};response={'header':{},'records':2,'policy':'raw-exact-v1','results':[{'request':request['actions'][0],'outcome':{'status':'entries','entries':rows}}]}
        with patch('m2_import_jobs.compare_header'):
            self.assertEqual(compare_response(response,case,request)['exact_query_result'],1)
            wrong=copy.deepcopy(response);wrong['results'][0]['outcome']['entries'].pop()
            with self.assertRaises(AssertionError):compare_response(wrong,case,request)
            wrong=copy.deepcopy(response);wrong['results'][0]['outcome']['status']='resources'
            with self.assertRaises(AssertionError):compare_response(wrong,case,request)
    def test_failed_background_job_cannot_expose_partial_reply(self):
        failure={'code':'integrity','detail':'integrity','message':'bad checksum'}
        terminal={'state':'failed','operation':'import_mdx','result_available':False,'job_id':'import-1','latest_progress':None,'error':failure}
        reply={'state':'failed','terminal':terminal,'collected':dict(terminal),'error':failure,'response':None,'taken_once':True,'forgotten':True,'late_cancel':'already_finished','events':[terminal]}
        validate_background(reply)
        wrong=copy.deepcopy(reply);wrong['response']={'partial':True}
        with self.assertRaises(AssertionError):validate_background(wrong)
        wrong=copy.deepcopy(reply);wrong['events']*=2
        with self.assertRaises(AssertionError):validate_background(wrong)
if __name__=='__main__':unittest.main()
