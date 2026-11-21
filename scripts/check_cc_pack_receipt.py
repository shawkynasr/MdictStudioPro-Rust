"""Source-bound review of complete CC packing; final M2 closeout stays separate."""
import hashlib
import json
from m2_sizing import ROOT,require,RSS_TARGET
from m2_cc_pack import REFERENCE,admission
from cc_pack_lock import LOCK,check_lock
DIRECTORY=ROOT/'docs/evidence/m2-cc-pack-user-run'
def review(r):
    require(r['status']=='full_CC_CEDICT_block_spooled_packing_passed_M2_closeout_pending' and r['stage']=='complete' and not r['M2_complete'] and not r['RSS_is_OS_limit'] and r['private_cleanup'] and 'error' not in r,'Incomplete or expanded qualification')
    require([(s['name'],s['returncode']) for s in r['steps']]==[('block-writer-tests',0),('runtime-tests',0),('release-runtime',0),('release-index-verifier',0)],'Native command receipts differ')
    require('5 passed; 0 failed' in r['steps'][0]['log_tail'] and '39 passed; 0 failed' in r['steps'][1]['log_tail'],'Native test totals differ')
    require(len(r['protected_source_sha256'])==300 and len(r['source_sha256'])==24 and len({**r['protected_source_sha256'],**r['source_sha256']})==324,'Source inventory differs')
    for n,h in {**r['protected_source_sha256'],**r['source_sha256']}.items():require(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,'Qualified source changed: '+n)
    require(r['dependency_packages']==check_lock() and len(r['dependency_packages'])==69 and r['dependency_lock_sha256']==hashlib.sha256((ROOT/LOCK).read_bytes()).hexdigest(),'Dependency binding differs')
    ref=json.loads((ROOT/REFERENCE).read_text());inv=ref['inventory'];scan=ref['expected_sorted_scan'];require(r['independent_preparation']=={'inventory':inv,'expected_sorted_scan':scan},'Complete independent preparation differs')
    require(inv['records']==202884 and inv['decoded_bytes']==75162810 and scan['records']==202884,'Incomplete source extent')
    require(type(r['peak_RSS_bytes']) is int and 0<r['peak_RSS_bytes']<=RSS_TARGET,'Runtime RSS invalid/exceeds target')
    ix=r['original_index'];require(ix['receipt']['kind']=='index' and ix['receipt']['receipt']['manifest']['source_sha256']==inv['source_sha256'] and ix['receipt']['receipt']['manifest']['records']==202884,'Original reader seed identity differs')
    blocked=r['reader_contention_refusal'];require(blocked['receipt'] is None and blocked['snapshot']['error']['code']=='limit_exceeded' and blocked['snapshot']['error']['detail']=='resource_admission','Reader/CC exclusion differs')
    require([(f['case'],f['snapshot']['error']['code']) for f in r['expected_failures']]==[('old-record-cap','limit_exceeded'),('old-decoded-cap','limit_exceeded'),('old-plan-cap','limit_exceeded'),('cannot-grow','invalid_input'),('pre-cancel','cancelled')],'Lower-cap/growth/cancel controls differ')
    require([c['encoding'] for c in r['checks']]==['utf8','utf16'],'Complete encoding coverage differs');publications=[ix,blocked,*r['expected_failures']];hashes={}
    for c in r['checks']:
        encoding=c['encoding'];pub=c['publication'];wire=c['independent_wire'];reply=pub['receipt'];require(reply['kind']=='cc_packing','Wrong dedicated profile response');s=reply['receipt']
        require(s['profile']=='cc-mdx-block-spool-v1' and s['source_sha256']==inv['manifest_sha256'] and wire['records']==inv['expected_sorted_records'] and all(s[k]==v for k,v in inv['expected_sorted_records'].items()) and s['file_bytes']==wire['file_bytes'] and s['metadata']==wire['metadata'],'Native/full independent output parity differs')
        expected_encoding='UTF-8' if encoding=='utf8' else 'UTF-16';meta=wire['metadata'];require(meta['Encoding']==expected_encoding and all(meta.get(k)==v for k,v in {'Title':inv['metadata']['title'],'Description':inv['metadata']['description'],'StyleSheet':inv['metadata']['stylesheet'],'KeyCaseSensitive':'No','StripKey':'No',**inv['metadata']['extra']}.items()),'Encoding/metadata/No-No profile differs')
        require(any(v['shared']['cc_packings']==1 for v in pub['admission_observations']),'Missing full exclusive packing observation');require(c['overwrite_refusal']['snapshot']['error']['code']=='destination_exists' and c['overwrite_refusal']['receipt'] is None,'Overwrite refusal differs')
        verified=c['index_verifier_reply'];manifest=c['index_publication']['receipt']['receipt']['manifest'];require(c['index_verifier_returncode']==0 and verified['status']=='queried' and verified['scan']==scan and verified['manifest']==manifest and manifest['source_sha256']==wire['file_sha256'] and manifest['records']==202884 and manifest['policy']=='raw_exact' and verified['results']==[],'Complete strict packed source/index reopen differs')
        require(verified['memory']['locator']==0 and verified['memory']['peak']<=verified['memory']['budget']==64*1024**2 and type(c['index_verifier_peak_RSS_bytes']) is int and 0<c['index_verifier_peak_RSS_bytes']<=RSS_TARGET,'Parser/verifier memory differs')
        hashes[encoding]=wire['file_sha256'];publications += [pub,c['overwrite_refusal'],c['index_publication']]
    final=r['final_admission'];admission(final);require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['live_sessions']==final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final cleanup differs')
    expected={p['snapshot']['job_id']:p for p in publications};require(len(expected)==13,'Publication inventory differs');jobs={};terminal={};takes={};forgotten=set();errors=[];reader_results=[];revisions={};cancelled=[]
    for e in r['controller_transcript']:
        cmd=e['command'];reply=e['reply'];op=cmd['op']
        if 'error' in reply:require(op=='publish','Unexpected API refusal');errors.append(reply['error']['code']);continue
        require(set(reply)=={'ok'},'Malformed controller reply');v=reply['ok']
        if op=='publish':
            jid=v['job'];require(jid in expected and jid not in jobs and cmd['request']==expected[jid]['request'],'Submission not bound to reported publication');jobs[jid]=cmd
        elif op=='publish_job':
            jid=cmd['job'];require(jid in jobs and v['job_id']==jid and v['revision']>=revisions.get(jid,0),'Snapshot identity/revision differs');revisions[jid]=v['revision']
            if v['state'] in ['succeeded','failed','cancelled']:terminal[jid]=v
        elif op=='publish_take':
            require(cmd['job'] in jobs,'Take from unknown job')
            if v is not None:takes.setdefault(cmd['job'],[]).append(v)
        elif op=='publish_forget':require(cmd['job'] in terminal and cmd['job'] not in forgotten and v is None,'Invalid forgetting');forgotten.add(cmd['job'])
        elif op=='publish_cancel':cancelled.append(v)
        elif op=='admission':admission(v)
        elif op=='take':reader_results.append(v)
        elif op=='publish_events':require(len(v)<=8,'Unbounded progress')
    require(jobs.keys()==expected.keys() and forgotten==set(jobs) and errors==['closed'] and cancelled==['already_finished']*5,'Lifecycle coverage differs')
    for jid,p in expected.items():
        require(terminal[jid]==p['snapshot'],'Reported terminal snapshot not bound to transcript')
        if p['receipt'] is None:require(takes.get(jid,[])==[] and p['snapshot']['state'] in ['failed','cancelled'] and not p['snapshot']['error']['publication_uncertain'],'Failed publication retained result/uncertainty')
        else:require(takes.get(jid)==[p['receipt']] and p['snapshot']['state']=='succeeded' and p['snapshot']['error'] is None,'Successful one-transfer result differs')
        for v in p['admission_observations']:admission(v)
    require(len(reader_results)==1 and reader_results[0]['operation']=='opened' and reader_results[0]['value']==ix['receipt']['receipt']['manifest'],'Opened original reader identity differs')
    return {'status':'complete_CC_CEDICT_block_spooled_packing_qualified_M2_closeout_pending','native_library_tests_passed':5,'native_runtime_tests_passed':39,'native_commands_passed':4,'records_each_encoding':202884,'encodings':['utf8','utf16'],'packed_file_sha256':hashes,'runtime_peak_RSS_bytes':r['peak_RSS_bytes'],'controller_exchanges':len(r['controller_transcript']),'qualified_source_identities':324,'dependency_packages':69,'M2_complete':False,'next_scope':'M2 closeout review'}
if __name__=='__main__':print(json.dumps(review(json.loads((DIRECTORY/'m2-cc-pack-report.json').read_text())),indent=2))
