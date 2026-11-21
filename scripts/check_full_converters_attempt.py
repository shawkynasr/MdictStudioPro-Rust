"""Review the incomplete first integration attempt without qualifying later cases."""
import hashlib
import json
from m2_sizing import ROOT,require,RSS_TARGET
from m2_full_converters import admission,REFERENCE
DIRECTORY=ROOT/'docs/evidence/m2-full-converters-first-run'
def review(r):
    require(r['status']=='m2_full_converters_failed' and r['stage']=='moe_concise' and r['error']=='AssertionError: Observed RSS exceeds provisional 384 MiB threshold','Unexpected failure scope')
    require(not r['M2_complete'] and len(r['protected_source_sha256'])==265 and len(r['source_sha256'])==12,'Attempt source/scope inventory differs')
    require([(s['name'],s['returncode']) for s in r['steps']]==[('native-tests',0),('release-build',0)],'Native commands differ')
    require('31 passed; 0 failed' in r['steps'][0]['log_tail'],'Missing native test receipt')
    for n,h in r['protected_source_sha256'].items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Protected source changed: '+n)
    for n,h in r['source_sha256'].items():require(hashlib.sha256((DIRECTORY/'attempted'/n).read_bytes()).hexdigest()==h,'Attempted source snapshot differs: '+n)
    refs={c['converter']:c for c in json.loads((ROOT/REFERENCE).read_text())['cases']}
    require([c['case'] for c in r['checks']]==['cc_cedict','moe_mini','moe_idioms'],'Completed case scope differs')
    exchanges=0
    for c in r['checks']:
        spec=refs[c['case']];receipt={'kind':'conversion','receipt':{'profile':spec['profile'],'receipt':spec['receipt']}}
        require(c['receipt']==receipt and c['native_output_sha256']==c['accepted_output_sha256']==spec['native_output_sha256'],'Completed output reference differs')
        require(c['snapshot']['state']=='succeeded' and c['snapshot']['error'] is None and c['pre_cancelled_retained_jobs']==8,'Completed job/retention differs')
        require(type(c['peak_RSS_bytes']) is int and 0<c['peak_RSS_bytes']<=RSS_TARGET,'Completed case RSS invalid')
        for v in c['observations']:admission(v)
        final=c['final_admission'];admission(final);require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['retained_session_handles']==final['readers']['retained_reply_bytes']==0,'Final cleanup differs')
        require([(x['case'],x['snapshot']['error']['code']) for x in c['expected_failures']]==[('overwrite','destination_exists'),('lowered-entries','limit_exceeded')],'Expected refusals differ')
        taken=[];pre=0;api=[]
        for e in c['controller_transcript']:
            exchanges+=1;cmd=e['command'];reply=e['reply']
            if 'error' in reply:api.append(reply['error']['code']);continue
            value=reply['ok']
            if cmd['op']=='admission':admission(value)
            if cmd['op']=='publish_take' and value is not None:taken.append(value)
            if cmd['op']=='publish' and cmd.get('pre_cancel'):pre+=1
        require(taken==[receipt] and pre==8 and api==['retention_full','closed'],'Transcript result transfer or refusal binding differs')
    return {'status':'incomplete_attempt_reviewed_not_full_qualification','native_tests_passed':31,'completed_case_count':3,'controller_exchanges':exchanges,'failure':'Concise RSS threshold','Concise_peak_RSS':'not retained by first harness','Revised_WFG_integration':'not reached','M2_complete':False}
if __name__=='__main__':print(json.dumps(review(json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())),indent=2))
