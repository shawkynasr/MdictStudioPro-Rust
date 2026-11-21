"""Review the source-bound six-converter integration receipt, without M2 closeout."""
import hashlib
import json
from pathlib import Path
from m2_sizing import ROOT,require,RSS_TARGET
from m2_full_converters import REFERENCE,CONCISE_ROWS,PROFILES,admission,runtime_receipt,check_reference
from full_converter_runtime_lock import check_lock,LOCK
DIRECTORY=ROOT/'docs/evidence/m2-full-converters-user-run'
def review(r):
    require(r['status']=='six_full_converters_shared_runtime_passed_M2_closeout_pending' and r['stage']=='complete' and not r['M2_complete'] and not r['RSS_is_OS_limit'],'Scope expanded or incomplete run')
    require('error' not in r and 'active_case_observation' not in r,'Failure/unfinished case present')
    require([(s['name'],s['returncode']) for s in r['steps']]==[('native-tests',0),('release-build',0),('release-row-reader',0)],'Native command receipt differs')
    require('33 passed; 0 failed' in r['steps'][0]['log_tail'],'Missing successful native test receipt')
    require(len(r['protected_source_sha256'])==265 and len(r['source_sha256'])==17 and len({**r['protected_source_sha256'],**r['source_sha256']})==282,'Source identity inventory differs')
    for n,h in {**r['protected_source_sha256'],**r['source_sha256']}.items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Qualified source changed: '+n)
    require(r['dependency_packages']==check_lock() and len(r['dependency_packages'])==68 and r['dependency_lock_sha256']==hashlib.sha256((ROOT/LOCK).read_bytes()).hexdigest(),'Dependency binding differs')
    ref=json.loads((ROOT/REFERENCE).read_text());check_reference(ref);specs={c['converter']:c for c in ref['cases']}
    row=r['concise_row_normalization'];expected_rows=json.loads((ROOT/CONCISE_ROWS).read_text())
    require(row['returncode']==0 and row['reply']['status']=='succeeded' and row['reply']['private_cleanup'] and row['python_reference']==expected_rows,'Full Concise row oracle failed')
    require(all(row['reply']['receipt'][k]==v for k,v in expected_rows.items()),'Full Concise native row parity differs')
    require(type(row['peak_RSS_bytes']) is int and 0<row['peak_RSS_bytes']<=192*1024**2,'Row reader RSS exceeds target')
    require([c['case'] for c in r['checks']]==[c['converter'] for c in ref['cases']],'Missing or reordered full converter cases')
    exchanges=0;peak=0;counts={}
    for c in r['checks']:
        kind=c['case'];spec=specs[kind];expected=runtime_receipt(spec);counts[kind]=expected['receipt']['receipt']['entries']
        require(c['receipt']==expected and c['native_output_sha256']==c['accepted_output_sha256']==spec['native_output_sha256'],'Full output identity/receipt differs: '+kind)
        require(type(c['peak_RSS_bytes']) is int and 0<c['peak_RSS_bytes']<=RSS_TARGET,'Converter RSS invalid/exceeds target: '+kind);peak=max(peak,c['peak_RSS_bytes'])
        require(c['snapshot']['state']=='succeeded' and c['snapshot']['error'] is None and c['pre_cancelled_retained_jobs']==8,'Success/retention scope differs')
        require([(x['case'],x['snapshot']['error']['code']) for x in c['expected_failures']]==[('overwrite','destination_exists'),('lowered-entries','limit_exceeded')],'Typed refusals differ')
        for v in c['observations']:admission(v)
        final=c['final_admission'];admission(final);require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['closed'] and final['readers']['live_sessions']==final['readers']['retained_session_handles']==final['readers']['retained_reply_bytes']==0,'Final cleanup differs')
        jobs={};revisions={};taken=[];api=[];forgotten=set();terminal={};cancel_outcomes=[];observed_active=False
        for e in c['controller_transcript']:
            exchanges+=1;cmd=e['command'];reply=e['reply'];op=cmd['op']
            if 'error' in reply:
                require(op=='publish','Unexpected API error');api.append(reply['error']['code']);continue
            require(set(reply)=={'ok'},'Malformed controller envelope');v=reply['ok']
            if op=='publish':
                req=cmd['request'];require(req['kind']=='conversion' and req['request']['profile']==PROFILES[kind],'Wrong submitted profile');inner=req['request']['request'];require(inner['converter']==kind and Path(inner['input']).name==spec['member'] and inner.get('worksheet')==spec['worksheet'],'Wrong submitted source/selector')
                jid=v['job'];require(jid not in jobs,'Duplicate job identity');jobs[jid]=cmd
            elif op=='publish_job':
                jid=cmd['job'];require(jid in jobs and v['job_id']==jid and v['revision']>=revisions.get(jid,0),'Snapshot identity/revision differs');revisions[jid]=v['revision']
                if v['state'] in ['succeeded','failed','cancelled']:terminal[jid]=v
            elif op=='admission':
                admission(v);require(v['shared']['readers']==v['shared']['packings']==v['shared']['exports']==v['shared']['extractions']==0,'Unexpected full-data overlap');observed_active|=v['shared']['conversions']==1
            elif op=='publish_take':
                require(cmd['job'] in jobs,'Take from unknown job')
                if v is not None:taken.append((cmd['job'],v))
            elif op=='publish_forget':
                require(cmd['job'] in terminal and cmd['job'] not in forgotten and v is None,'Forget before terminal or repeated');forgotten.add(cmd['job'])
            elif op=='publish_events':require(len(v)<=8,'Unbounded event retention')
            elif op=='publish_cancel':cancel_outcomes.append(v)
            elif op=='shutdown':require(v is None,'Shutdown response differs')
            else:raise AssertionError('Unexpected command in converter proof: '+op)
        require(observed_active and len(jobs)==11 and forgotten==set(jobs) and len(terminal)==11 and api==['retention_full','closed'] and cancel_outcomes==['already_finished'],'Lifecycle inventory differs')
        first=next(iter(jobs));require(taken==[(first,expected)] and terminal[first]==c['snapshot'],'One-transfer success receipt binding differs')
        for failure in c['expected_failures']:require(terminal[failure['snapshot']['job_id']]==failure['snapshot'],'Refusal snapshot not bound to transcript')
        require(sum(x['state']=='succeeded' for x in terminal.values())==1 and sum(x['state']=='failed' for x in terminal.values())==2 and sum(x['state']=='cancelled' for x in terminal.values())==8,'Terminal state counts differ')
        for jid,cmd in jobs.items():
            status=terminal[jid]
            if jid!=first:require(status['error'] is not None and not status['error']['publication_uncertain'],'Unexpected publication uncertainty')
            if cmd.get('pre_cancel'):require(status['state']=='cancelled' and status['error']['code']=='cancelled','Pre-cancel semantics differ')
        require(len(json.dumps(expected).encode())<=4096,'Receipt is not thin')
    return {'status':'six_full_converter_integration_qualified_M2_partial','native_tests_passed':33,'native_commands_passed':3,'converter_count':6,'entry_counts':counts,'controller_exchanges':exchanges,'protected_and_new_source_identities':282,'dependency_packages':68,'Concise_normalized_rows':45178,'Concise_normalized_fields':677670,'Concise_peak_RSS_bytes':next(c['peak_RSS_bytes'] for c in r['checks'] if c['case']=='moe_concise'),'maximum_converter_peak_RSS_bytes':peak,'M2_complete':False,'next_scope':'real dictionary packing and index-build admission'}
if __name__=='__main__':print(json.dumps(review(json.loads((DIRECTORY/'m2-full-converters-report.json').read_text())),indent=2))
