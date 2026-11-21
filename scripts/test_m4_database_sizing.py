"""Validate performance oracle identities, literal query semantics and profile boundaries."""
import copy
import tempfile
from pathlib import Path
import unittest
from m4_database_sizing import synthetic,queries,verify_queries,profile_issue
from verify_database_jsonl import read_jsonl


def result_for(rows,specs):
    result={'info':{'operation':'opened','value':{'records':len(rows),'source_sha256':'a'*64}},
            'admission_after_close':{'active_operations':0},'queries':[]}
    for spec in specs:
        q=spec['request'];needle=q['query'];matches=[]
        for i,(key,body) in enumerate(rows):
            match=(needle is None or (needle in body if q['definition'] else key.startswith(needle) if q['prefix'] else key==needle))
            if match:matches.append({'rowid':str(i+1),'key':key,'text':body})
        offset,limit=q['offset'],q['limit']
        for repeat in range(5):
            result['queries'].append({'label':spec['label'],'repeat':repeat,'elapsed_ms':repeat+.5,
                'reply':{'operation':'page','value':{'rows':matches[offset:offset+limit],
                    'total':len(matches),'offset':offset,'next_offset':offset+limit if offset+limit<len(matches) else None,
                    'source_sha256':'a'*64}}})
    return result


class SizingOracleTests(unittest.TestCase):
    def test_warm_queries_preserve_duplicates_and_report_five_samples(self):
        rows=[('a%','first'),('a_b','a'),('a%','last'),('字','')];specs=queries(rows,2)
        result=result_for(rows,specs);metrics=verify_queries(rows,specs,result)
        self.assertEqual(len(metrics),5)
        self.assertEqual(metrics['exact']['samples'],5)
        self.assertEqual(metrics['exact']['warm_median_ms'],3.0)
        for mutation in ['rowid','total','snapshot','repeat','lease','time']:
            bad=copy.deepcopy(result)
            if mutation=='rowid':bad['queries'][0]['reply']['value']['rows'][0]['rowid']='3'
            elif mutation=='total':bad['queries'][0]['reply']['value']['total']-=1
            elif mutation=='snapshot':bad['queries'][0]['reply']['value']['source_sha256']='b'*64
            elif mutation=='repeat':bad['queries'][0]['repeat']=3
            elif mutation=='lease':bad['admission_after_close']['active_operations']=1
            else:bad['queries'][0]['elapsed_ms']=float('nan')
            with self.subTest(mutation=mutation),self.assertRaises(AssertionError):verify_queries(rows,specs,bad)

    def test_synthetic_rows_have_exact_body_size_and_three_separate_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'fixture.jsonl';synthetic(path,count=10,body_bytes=32);rows=read_jsonl(path)
            self.assertEqual(len(rows),10);self.assertTrue(all(len(t.encode())==32 for _,t in rows))
            self.assertEqual(sum(k=='duplicate' for k,_ in rows),3)
            self.assertEqual(profile_issue(rows),None)

    def test_record_key_body_and_aggregate_limits_are_distinct(self):
        self.assertEqual(profile_issue([]),'empty dictionary')
        self.assertEqual(profile_issue([('a','')]*100001),'record count')
        self.assertIsNone(profile_issue([('a','')]*100000))
        self.assertEqual(profile_issue([('字'*1366,'')]),'key/body size')
        self.assertEqual(profile_issue([('a','x'*(1024*1024+1))]),'key/body size')
        self.assertIsNone(profile_issue([('a','x'*(1024*1024-1))]*32))
        self.assertEqual(profile_issue([('a','x'*(1024*1024))]*32),'decoded text')
