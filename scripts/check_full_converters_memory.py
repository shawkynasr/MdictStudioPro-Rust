"""Review the measured owned-Concise failure without waiving the RSS ceiling."""
import json
import hashlib
from m2_sizing import ROOT,require,RSS_TARGET
from m2_full_converters import REFERENCE,admission
DIRECTORY=ROOT/'docs/evidence/m2-full-converters-memory-retry'
def review(r):
    require(r['status']=='m2_full_converters_failed' and r['stage']=='moe_concise' and r['error']=='AssertionError: Observed RSS exceeds provisional 384 MiB threshold' and not r['M2_complete'],'Failure scope differs')
    require([(s['name'],s['returncode']) for s in r['steps']]==[('native-tests',0),('release-build',0)] and '32 passed; 0 failed' in r['steps'][0]['log_tail'],'Native command receipts differ')
    require(len(r['source_sha256'])==13 and len(r['protected_source_sha256'])==265,'Attempt inventory differs')
    for n,h in r['source_sha256'].items():require(hashlib.sha256((DIRECTORY/'attempted'/n).read_bytes()).hexdigest()==h,'Measured attempt snapshot differs: '+n)
    for n,h in r['protected_source_sha256'].items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Qualified source changed: '+n)
    refs={c['converter']:c for c in json.loads((ROOT/REFERENCE).read_text())['cases']};exchanges=0
    require([c['case'] for c in r['checks']]==['cc_cedict','moe_mini','moe_idioms'],'Completed case scope differs')
    active=r['active_case_observation'];require(active['case']=='moe_concise' and type(active['peak_RSS_bytes']) is int and active['peak_RSS_bytes']==420204544>RSS_TARGET,'Measured failure peak differs')
    for c in r['checks']+[active]:
        spec=refs[c['case']];expected={'kind':'conversion','receipt':{'profile':spec['profile'],'receipt':spec['receipt']}}
        require(c['receipt']==expected and c['native_output_sha256']==spec['native_output_sha256'] and c['snapshot']['state']=='succeeded' and c['snapshot']['error'] is None,'Conversion parity/success receipt differs')
        if c is not active:require(type(c['peak_RSS_bytes']) is int and 0<c['peak_RSS_bytes']<=RSS_TARGET and c['pre_cancelled_retained_jobs']==8,'Completed case limits/retention differ')
        final=c['final_admission'];admission(final);require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['retained_session_handles']==final['readers']['retained_reply_bytes']==0,'Final ledger differs')
        takes=[];pre=0;errors=[]
        for e in c['controller_transcript']:
            exchanges+=1;cmd=e['command'];reply=e['reply']
            if 'error' in reply:errors.append(reply['error']['code']);continue
            value=reply['ok']
            if cmd['op']=='admission':admission(value)
            if cmd['op']=='publish_take' and value is not None:takes.append(value)
            if cmd['op']=='publish' and cmd.get('pre_cancel'):pre+=1
        require(takes==[expected] and pre==8 and errors==['retention_full','closed'],'Transcript binding differs')
    return {'status':'owned_Concise_RSS_failure_reviewed_not_qualified','native_tests_passed':32,'full_cases_completed':3,'Concise_hash_matches':True,'Concise_peak_RSS_bytes':active['peak_RSS_bytes'],'controller_exchanges':exchanges,'Revised_WFG_integration':'not reached','M2_complete':False}
if __name__=='__main__':print(json.dumps(review(json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())),indent=2))
