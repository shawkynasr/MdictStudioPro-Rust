"""Recompute session pages and review the recorded application lifecycle.

No Rust execution, private-file inspection or unrecorded test claim is implied.
"""
import json
from collections import Counter
from pathlib import Path
from index_fixtures import SPECIAL,expected_page
from bounded_fixtures import rows as generated_rows

def require(ok,message):
    if not ok:raise AssertionError(message)
def review(report):
    require(report['status']=='m2_persistent_sessions_background_pages_passed_larger_paths_pending' and report['stage']=='complete','Session batch incomplete')
    require(not report['M2_complete'] and not report['production_readiness'] and report['native_readers']=='NOT_REQUESTED','Do not expand session qualification scope')
    steps=report['steps'];cases=report['checks'];labels=['utf8','utf16','binary','larger-mdx','larger-mdd']
    require([(s['name'],s['returncode']) for s in steps]==[(n,0) for n in ['refresh-session-artifacts','session-tests','build-session-cli','build-index-tool']+[n+'-seed-index' for n in labels]],'Session setup/build receipts differ')
    require([c['case'] for c in cases]==labels,'Session scenario inventory differs')
    exchanges=0;primary_pages=0;all_pages=0;successful_jobs=0;cancelled_jobs=0;api_refusals=0;maximum=0
    for c in cases:
        label=c['case'];kind='mdd' if label in ['binary','larger-mdd'] else 'mdx';strip=label in ['utf8','utf16'];policy='raw_exact' if kind=='mdd' else 'header_ascii_v1'
        rows=SPECIAL+[('duplicate',f'body-{i}') for i in range(400)] if strip else list(generated_rows(100 if label=='binary' else 65536,kind))
        queries=[('apple',0,1),('apple',1,1),('APPLE',0,4),('a?b',0,4),('duplicate',384,128),('duplicate',0,0),('absent',2**64-1,2)] if strip else [('row00000000',0,1),('row00000000',1,1),('ROW00000000',0,4),('字',0,2),('𠀀',0,2),('absent',0,0)]
        require(c['status']=='persistent_session_matrix_passed' and 0<c['peak_RSS_bytes']<=384*1024*1024,'Session status/RSS differs');maximum=max(maximum,c['peak_RSS_bytes'])
        m=c['open_manifest'];require(m['kind']==kind and m['policy']==policy and m['records']==len(rows) and m['case_sensitive'] is False and m['strip_key']==strip and m['source_sha256']==c['source_sha256'],'Session manifest/fixture differs')
        require(m['revision']=='studio-disk-index-v1-frozen16' and m['engine_revision']=='mdictlib-0.2.8-studio-sort-v6' and m['casing_sha256']=='f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071','Session manifest revision differs')
        require(len(c['pages'])==len(queries) and len(c['page_job_snapshots'])==len(queries),'Primary page inventory differs')
        def expected(q,offset,limit):return {'operation':'page','value':expected_page(rows,q,offset,limit,policy,False,strip,kind)}
        for page,status,(q,offset,limit) in zip(c['pages'],c['page_job_snapshots'],queries):
            require(page['request']=={'query':q,'offset':offset,'limit':limit} and page['response']==expected(q,offset,limit),'Primary page body/order/ordinal comparison failed')
            require(status['state']=='succeeded' and status['result_available'] and status['error'] is None,'Primary page job did not succeed');primary_pages+=1
        require(c['snapshot_replacement_page']==expected(*queries[0]),'Private-snapshot page differs after public replacement')
        jobs={};sessions=set();taken=set();retained=0;observed_pages=[];errors=Counter();finished=Counter();last_admission=None;progress_seen=0;closed_sessions=set()
        transcript=c['controller_transcript'];require(len(transcript)==(103 if strip else 97),'Controller exchange count differs')
        for exchange in transcript:
            command=exchange['command'];reply=exchange['reply'];op=command['op'];exchanges+=1
            require(('ok' in reply)!=('error' in reply),'Ambiguous controller reply')
            if 'error' in reply:errors[reply['error']['code']]+=1;continue
            value=reply['ok']
            if op=='open':
                spec=command['request'];require(spec['kind']==kind and spec['policy']==policy,'Open policy differs')
                sid=value['session'];jid=value['job'];sessions.add(sid);require(jid not in jobs,'Reused job ID');jobs[jid]={'session':sid,'op':'opened','pre_cancel':command.get('pre_cancel',False),'retained':0,'taken':False}
            elif op=='submit':
                require(command['session'] in sessions and command['session'] not in closed_sessions,'Page admitted after closed acknowledgement');jid=value['job'];require(jid not in jobs,'Reused page ID');jobs[jid]={'session':command['session'],'op':'page','request':command['request'],'pre_cancel':command.get('pre_cancel',False),'retained':0,'taken':False}
            elif op in ['wait','job']:
                jid=command['job'];r=jobs[jid];require(value is not None and value['job_id']==jid,'Wrong job snapshot identity')
                state=value['state'];require(state in ['succeeded','cancelled'],'Unexpected job failure in accepted scenario')
                if 'state' not in r:
                    finished[state]+=1;r['state']=state;r['retained']=value['result_bytes'];retained+=r['retained']
                require(state==r['state'] and value['result_available']==(state=='succeeded' and not r['taken']) and value['result_bytes']==r['retained'],'Result availability/reservation changed unexpectedly')
                if r['pre_cancel']:require(state=='cancelled' and value['cancel_requested'] and value['error']['code']=='cancelled' and not value['result_available'],'Pre-cancelled job retained success')
                else:require(state=='succeeded' and value['error'] is None,'Ordinary job failed')
                p=value['latest_progress']
                if p is not None:require(p['job_id']==jid and p['completed']<=p['total'],'Progress belongs to wrong job');progress_seen+=1
            elif op=='take':
                jid=command['job'];r=jobs[jid]
                if value is None:require(r.get('state')=='cancelled' or r['taken'],'Successful reply disappeared before take')
                else:
                    require(r.get('state')=='succeeded' and not r['taken'],'Reply transferred twice')
                    measured=len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode());require(measured==r['retained'],'Serialized reply byte reservation differs')
                    if r['op']=='opened':require(value=={'operation':'opened','value':m},'Opened manifest differs')
                    else:
                        q=r['request'];require(value==expected(q['query'],q['offset'],q['limit']),'Transcript page comparison failed');observed_pages.append(value);all_pages+=1
                    retained-=r['retained'];r['retained']=0;r['taken']=True;taken.add(jid)
            elif op=='forget':
                r=jobs.pop(command['job']);require(r.get('state') in ['succeeded','cancelled'],'Forgot unfinished job');retained-=r['retained']
            elif op=='cancel':require(value=='already_finished' and jobs[command['job']].get('state')=='succeeded','Late cancel changed completed job')
            elif op=='snapshot':require(value['state']=='ready' and value['session_id']==command['session'],'Open job success raced Ready state')
            elif op=='wait_closed':require(value['closed'],'Close not acknowledged');closed_sessions.add(command['session'])
            elif op=='release':
                sid=command['session'];require(sid in closed_sessions,'Release before cleanup acknowledgement');sessions.remove(sid)
                for jid in [jid for jid,r in jobs.items() if r['session']==sid]:retained-=jobs.pop(jid)['retained']
            elif op=='admission':
                require(value['retained_reply_bytes']==retained and value['live_sessions']<=2 and value['retained_session_handles']<=8,'Pool retention/admission differs')
                require(value['reserved_memory_bytes']==value['live_sessions']*96*1024*1024 and value['reserved_temp_bytes']==value['live_sessions']*768*1024*1024 and value['retained_reply_cap']==8*1024*1024,'Logical resource reservations differ');last_admission=value
            elif op=='events':require(len(value)<=8,'Unbounded progress history')
            elif op not in ['close','shutdown']:raise AssertionError('Unexpected command: '+op)
        require(errors=={'invalid_input':1,'resource_limit':1,'retention_full':1,'closed':2},'Expected API refusal inventory differs')
        require(finished=={'succeeded':18 if strip else 17,'cancelled':2},'Background job lifecycle totals differ')
        require(len(observed_pages)==len(queries)+1 and observed_pages[-1]==c['snapshot_replacement_page'],'Missing snapshot replacement reply')
        require(last_admission==c['final_admission'] and last_admission['closed'] and all(last_admission[k]==0 for k in ['live_sessions','retained_session_handles','reserved_memory_bytes','reserved_temp_bytes','retained_reply_bytes']),'Final pool reservations not released')
        require(retained==0 and not jobs and not sessions and progress_seen>0,'Session metadata/results leaked in transcript')
        successful_jobs+=finished['succeeded'];cancelled_jobs+=finished['cancelled'];api_refusals+=sum(errors.values())
    require(primary_pages==32 and all_pages==37 and exchanges==497 and successful_jobs==87 and cancelled_jobs==10 and api_refusals==25,'Session receipt totals differ')
    require(maximum==6262784,'Maximum observed RSS differs')
    return {'scenarios':5,'primary_pages':32,'snapshot_replacement_pages':5,'controller_exchanges':497,'successful_jobs':87,'cancelled_jobs':10,'expected_API_refusals':25,'max_observed_RSS_bytes':maximum,'review':'embedded pages and logical ledger recomputed; Rust not executed by reviewer'}

if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
