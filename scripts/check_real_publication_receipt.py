"""Review bounded real packing/index receipts without qualifying held CC packing."""
import hashlib
import json
from m2_sizing import ROOT,require,RSS_TARGET
from m2_real_publication import REFERENCE,REAL,admission
from real_publication_lock import LOCK,check_lock
DIRECTORY=ROOT/'docs/evidence/m2-real-publication-user-run'
def review(r):
    require(r['status']=='bounded_real_packing_and_exclusive_index_admission_passed_CC_packing_and_closeout_pending' and r['stage']=='complete' and not r['M2_complete'] and not r['RSS_is_OS_limit'] and 'error' not in r and 'active_case_observation' not in r,'Incomplete/expanded qualification scope')
    require([(s['name'],s['returncode']) for s in r['steps']]==[('native-tests',0),('release-runtime',0),('release-index-verifier',0)] and '36 passed; 0 failed' in r['steps'][0]['log_tail'],'Native commands/tests differ')
    require(len(r['protected_source_sha256'])==282 and len(r['source_sha256'])==18 and len({**r['protected_source_sha256'],**r['source_sha256']})==300,'Identity inventory differs')
    for n,h in {**r['protected_source_sha256'],**r['source_sha256']}.items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Qualified source changed: '+n)
    require(r['dependency_packages']==check_lock() and len(r['dependency_packages'])==68 and r['dependency_lock_sha256']==hashlib.sha256((ROOT/LOCK).read_bytes()).hexdigest(),'Dependency bindings differ')
    ref=json.loads((ROOT/REFERENCE).read_text());old={c['case']:c for c in json.loads((ROOT/REAL).read_text())['checks']};require([c['case'] for c in r['checks']]==list(ref),'Original case selection differs')
    exchanges=packed_count=0;peak=0;index_peak=0
    for c in r['checks']:
        cid=c['case'];inv=ref[cid];require(c['inventory']==inv,'Complete independent source preflight differs')
        require(type(c['peak_RSS_bytes']) is int and 0<c['peak_RSS_bytes']<=RSS_TARGET and type(c['index_verifier_peak_RSS_bytes']) is int and 0<c['index_verifier_peak_RSS_bytes']<=RSS_TARGET,'RSS invalid/exceeds target');peak=max(peak,c['peak_RSS_bytes']);index_peak=max(index_peak,c['index_verifier_peak_RSS_bytes'])
        ix=c['index_publication'];require(ix['receipt']['kind']=='index','Wrong index response');manifest=ix['receipt']['receipt']['manifest'];require(manifest['source_sha256']==inv['source_sha256'] and manifest['records']==inv['records'] and manifest['kind']==inv['kind'] and manifest['policy']=='raw_exact','Full index identity differs')
        require(len(json.dumps(ix['receipt']).encode())<=4096,'Index result is not thin')
        verified=c['index_verifier_reply'];require(verified['status']=='queried' and verified['manifest']==manifest and verified['scan']==old[cid]['independent_scan'] and verified['results']==[] and verified['memory']['locator']==0 and verified['memory']['peak']<=verified['memory']['budget']==64*1024**2,'Strict complete cache/source reopen differs')
        expected_encodings=[] if inv['packing_blockers'] else (['binary'] if inv['kind']=='mdd' else ['utf8','utf16']);require([x['encoding'] for x in c['packing']]==expected_encodings,'Packing coverage differs')
        publications=[ix,c['reader_contention_refusal'],c['index_overwrite_refusal'],c['pre_cancelled_index']]
        for item in c['packing']:
            packed_count+=1;pub=item['publication'];wire=item['wire_verification'];receipt=pub['receipt'];require(receipt['kind']=='dictionary','Wrong pack result');s=receipt['receipt'];expected=inv['expected_sorted_records']
            require(wire['records']==expected and all(s[k]==v for k,v in expected.items()) and s['source_sha256']==inv['manifest_sha256'] and s['file_bytes']==wire['file_bytes'] and s['metadata']==wire['metadata'],'Pack receipt/independent complete output differs')
            meta=wire['metadata'];require(all(meta.get(k)==v for k,v in {'Title':inv['metadata']['title'],'Description':inv['metadata']['description'],'StyleSheet':inv['metadata']['stylesheet'],'KeyCaseSensitive':'No','StripKey':'No',**inv['metadata']['extra']}.items()),'Metadata/No-No profile differs')
            require(meta['Encoding']==('' if inv['kind']=='mdd' else ('UTF-8' if item['encoding']=='utf8' else 'UTF-16')),'Output encoding differs')
            require(any(v['shared']['readers']==1 and v['shared']['packings']==1 for v in pub['admission_observations']),'Missing real reader/packer overlap observation')
            publications += [pub,item['overwrite_refusal']]
        held=c['packing_refusal'];require((held is not None)==bool(inv['packing_blockers']),'Held packing scope differs')
        if held:require(cid=='cc-cedict-mdx' and held['snapshot']['error']['code']=='limit_exceeded' and held['receipt'] is None,'Full CC packing refusal was waived');publications.append(held)
        blocked=c['reader_contention_refusal'];require(blocked['snapshot']['error']['code']=='limit_exceeded' and blocked['snapshot']['error']['detail']=='resource_admission','Reader/index contention refusal differs')
        require(c['index_overwrite_refusal']['snapshot']['error']['code']=='destination_exists' and c['pre_cancelled_index']['snapshot']['state']=='cancelled' and c['pre_cancelled_index']['snapshot']['error']['code']=='cancelled','Overwrite/pre-cancel differs')
        final=c['final_admission'];admission(final);require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['live_sessions']==final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final cleanup differs')
        expected_jobs={p['snapshot']['job_id']:p for p in publications};jobs={};terminal={};takes={};forgotten=set();errors=[];reader_taken=[];index_observed=False;revisions={}
        for e in c['controller_transcript']:
            exchanges+=1;cmd=e['command'];reply=e['reply'];op=cmd['op']
            if 'error' in reply:require(op=='publish','Unexpected API error');errors.append(reply['error']['code']);continue
            require(set(reply)=={'ok'},'Controller envelope differs');v=reply['ok']
            if op=='publish':
                jid=v['job'];require(jid not in jobs and jid in expected_jobs and cmd['request']==expected_jobs[jid]['request'],'Submission not bound to reported publication');jobs[jid]=cmd
            elif op=='publish_job':
                jid=cmd['job'];require(jid in jobs and v['job_id']==jid and v['revision']>=revisions.get(jid,0),'Job identity/revision differs');revisions[jid]=v['revision']
                if v['state'] in ['succeeded','failed','cancelled']:terminal[jid]=v
            elif op=='publish_take':
                require(cmd['job'] in jobs,'Take from unknown job')
                if v is not None:takes.setdefault(cmd['job'],[]).append(v)
            elif op=='publish_forget':require(cmd['job'] in terminal and cmd['job'] not in forgotten and v is None,'Invalid job forgetting');forgotten.add(cmd['job'])
            elif op=='publish_cancel':require(v=='already_finished','Late cancel differs')
            elif op=='admission':
                admission(v);index_observed|=v['shared']['index_builds']==1
            elif op=='take':reader_taken.append(v)
            elif op=='publish_events':require(len(v)<=8,'Unbounded progress')
        require(jobs.keys()==expected_jobs.keys() and forgotten==set(jobs) and errors==['closed'] and index_observed,'Lifecycle coverage differs')
        for jid,p in expected_jobs.items():
            require(terminal[jid]==p['snapshot'],'Terminal snapshot not bound to transcript')
            if p['receipt'] is None:require(takes.get(jid,[])==[] and p['snapshot']['state'] in ['failed','cancelled'] and not p['snapshot']['error']['publication_uncertain'],'Refused result/uncertainty differs')
            else:require(takes.get(jid)==[p['receipt']] and p['snapshot']['state']=='succeeded' and p['snapshot']['error'] is None,'Publication result transfer differs')
            for v in p['admission_observations']:admission(v)
        require(len(reader_taken)==1 and reader_taken[0]['operation']=='opened' and reader_taken[0]['value']==manifest,'Opened reader identity differs')
    require(packed_count==5,'Expected five full packed outputs')
    return {'status':'bounded_real_packing_and_shared_index_builds_qualified_M2_partial','native_tests_passed':36,'native_commands_passed':3,'original_sources_indexed':4,'complete_sources_repacked':3,'packed_outputs':5,'CC_CEDICT_full_packing':'controlled limit refusal; not qualified','controller_exchanges':exchanges,'qualified_source_identities':300,'dependency_packages':68,'maximum_runtime_peak_RSS_bytes':peak,'maximum_verifier_peak_RSS_bytes':index_peak,'M2_complete':False,'next_scope':'full CC-CEDICT packing capacity, then M2 closeout'}
if __name__=='__main__':print(json.dumps(review(json.loads((DIRECTORY/'m2-real-publication-report.json').read_text())),indent=2))
