"""Review source-bound full CC-CEDICT parity, refusals and controller lifecycle.

Actual native TXT/source/temp files stay private on the Mac. The exact harness
compares complete output hashes and asserts file preservation/cleanup. This reviewer checks
the resulting exact raw hash against the independently retained full Python run,
source identities, dependencies and every reported controller exchange.
"""
import json
from pathlib import Path
from m2_sizing import ROOT,require,sha,RSS_TARGET
from m2_cc_full import REFERENCE,protected_sources,fingerprints
from cc_runtime_lock import LOCK,check_lock
from m2_cc_full import exclusive_admission

def review(r):
    ref=json.loads((ROOT/REFERENCE).read_text());source_hash=ref['archive']['source_sha256']
    require(r['status']=='full_official_cc_exclusive_chunked_publication_passed_Revised_and_closeout_pending' and r['stage']=='complete','CC-CEDICT batch incomplete')
    require(not r['M2_complete'] and not r['RSS_is_OS_limit'] and r['native_readers']=='NOT_REQUESTED' and r['RSS_observation_target_bytes']==RSS_TARGET,'CC-CEDICT scope expanded')
    require(r['steps']==[{'name':'cc-runtime-tests','returncode':0},{'name':'build-cc-runtime','returncode':0}],'CC-CEDICT native commands differ')
    actual_sources={n:h for n,h in fingerprints().items() if Path(n).name!='.DS_Store'}
    expected_sources=r['source_sha256']
    require(r['protected_source_sha256']==protected_sources(),'CC-CEDICT protected source identities changed')
    require(expected_sources==actual_sources, f'CC-CEDICT source identities changed: missing={sorted(expected_sources.keys()-actual_sources.keys())}, extra={sorted(actual_sources.keys()-expected_sources.keys())}, changed={sorted(n for n in expected_sources.keys()&actual_sources.keys() if expected_sources[n]!=actual_sources[n])}')
    require(r['legacy_oracle_sha256']==ref['legacy_oracle_sha256'],'CC-CEDICT Python identities differ')
    for name,digest in r['legacy_oracle_sha256'].items():require(sha(ROOT/name)==digest,'Captured Python source differs')
    require(r['dependency_packages']==check_lock() and r['dependency_lock_sha256']==sha(ROOT/LOCK),'CC-CEDICT dependency graph/lock differs')
    require(len(r['checks'])==1 and r['checks'][0]['case']=='full-official-cc-cedict','CC-CEDICT case inventory differs');case=r['checks'][0]
    require(case['primary_rows']==ref['primary_entries']==125369 and case['source_sha256']==source_hash,'CC-CEDICT full-source identity/count differs')
    expected={'comments_count':30,'converter':'cc_cedict','entries':203362,'file_bytes':76339785,'metrics':{'alias_redirects':0,'primary_entries':125369,'skipped_rows_or_lines':0,'traditional_entries':77993},'profile':'cc-cedict-owned-chunked-txt-v1','source_sha256':source_hash,'txt_profile':'canonical_v1'}
    require(case['receipt']==expected and case['native_output_sha256']==case['python_output_sha256']==ref['raw_python_output_sha256'],'CC-CEDICT exact raw full-output content differs')
    success=case['success_snapshot']
    require(success['state']=='succeeded' and success['error'] is None and success['result_available'] and not success['cancel_requested'],'CC-CEDICT success state differs')
    require(success['latest_progress']=={'completed':203362,'job_id':success['job_id'],'phase':'published','stage':'publishing','total':203362},'CC-CEDICT committed progress differs')
    python=r['python_reference_observation'];native=r['native_observation']
    require(python=={'source_sha256':source_hash,'raw_sha256':case['python_output_sha256'],'file_bytes':expected['file_bytes'],'metrics':expected['metrics'],'comments_count':30},'CC-CEDICT Python reference summary differs')
    require(native=={'snapshot':case['success_snapshot'],'receipt':expected,'raw_sha256':case['native_output_sha256']},'CC-CEDICT native summary differs')
    require(case['raw_python_bytes_equal'] and case['python_output_sha256']==case['native_output_sha256'],'Raw versus normalized comparison misreported')
    require(0<r['peak_RSS_bytes']<=RSS_TARGET,'CC-CEDICT RSS observation exceeds envelope')
    names=['old-entry-cap','old-decoded-cap','old-output-cap','cannot-grow-entries','cannot-grow-decoded','pre-cancel','existing-output'];codes=['limit_exceeded','limit_exceeded','limit_exceeded','invalid_input','invalid_input','cancelled','destination_exists']
    require([f['case'] for f in r['expected_failures']]==names,'CC-CEDICT refusal inventory differs')
    failures={f['case']:f for f in r['expected_failures']};expected_tightens=[{'entries':100000},{'decoded_bytes':32*1024*1024},{'output_bytes':64*1024*1024},{'entries':250001},{'decoded_bytes':96*1024*1024+1},{},{}]
    expected_status={**{f['snapshot']['job_id']:f['snapshot'] for f in r['expected_failures']},case['success_snapshot']['job_id']:case['success_snapshot']}
    require(len(expected_status)==8,'CC-CEDICT job identities collide')
    for f,code in zip(r['expected_failures'],codes):
        s=f['snapshot'];require(s['state']==('cancelled' if code=='cancelled' else 'failed') and s['error']['code']==code and not s['error']['publication_uncertain'] and not s['result_available'],'CC-CEDICT typed refusal differs')
    require(failures['existing-output']['output_sha256_preserved']==case['native_output_sha256'],'Overwrite preservation hash differs')
    jobs={};all_jobs=[];admissions=[];observations=[];rejected=cancelled=shutdowns=0;last_job=None
    for exchange in r['controller_transcript']:
        cmd=exchange['command'];reply=exchange['reply'];op=cmd['op']
        if 'error' in reply:
            require(set(reply)=={'error'} and op=='publish' and rejected<2 and reply['error']['code']=='invalid_input' and cmd['request']['kind']=='conversion','Unexpected CC API error')
            payload=cmd['request']['request']
            require(Path(payload['input']).name==ref['archive']['member'],'Invalid-request source differs')
            if rejected==0:require(payload['converter']=='moe_revised' and Path(payload['destination']).name=='wrong-converter.txt','Wrong converter refusal differs')
            else:require(payload['converter']=='cc_cedict' and payload['worksheet']=='Sheet1' and Path(payload['destination']).name=='wrong-worksheet.txt','Wrong worksheet refusal differs')
            rejected+=1;continue
        require(set(reply)=={'ok'},'Malformed CC-CEDICT controller reply');value=reply['ok']
        if op=='publish':
            require(not jobs and cmd['request']['kind']=='conversion' and not shutdowns,'Unexpected overlapping publication')
            payload=cmd['request']['request'];require(payload['converter']=='cc_cedict' and Path(payload['input']).name==ref['archive']['member'] and 'worksheet' not in payload,'Wrong full-source request')
            index=len(all_jobs);require(index<8,'Extra publication');name=names[index] if index<6 else 'full' if index==6 else 'existing-output';tighten=payload.get('tighten',{})
            require(tighten==(expected_tightens[index] if index<6 else {}),'Wrong limits in refusal/publication request')
            require(bool(cmd.get('pre_cancel',False))==(name=='pre-cancel'),'Precancel option differs')
            jid=value['job'];require(jid in expected_status and jid not in all_jobs,'Unexpected/reused job id');jobs[jid]={'state':None,'revision':0,'takes':0,'case':name};all_jobs.append(jid);last_job=jid
            if index<6:require(cmd['request']==failures[name]['request'],'Refusal request summary differs')
        elif op=='publish_job':
            jid=cmd['job'];job=jobs[jid];require(value['job_id']==jid and value['operation']=='convert_to_txt' and value['revision']>=job['revision'],'CC-CEDICT job revision/identity differs')
            require(job['state'] not in ['succeeded','failed','cancelled'] or value['state']==job['state'],'Terminal CC-CEDICT state regressed');job.update(state=value['state'],revision=value['revision'])
            progress=value['latest_progress']
            if progress:require(progress['job_id']==jid and 0<=progress['completed']<=progress['total'],'CC-CEDICT progress identity/bounds differ')
            if value['state'] in ['succeeded','failed','cancelled']:require(value==expected_status[jid],'CC-CEDICT terminal summary differs')
        elif op=='publish_take':
            job=jobs[cmd['job']];require(job['state'] in ['succeeded','failed','cancelled'],'Premature result take')
            want={'kind':'conversion','receipt':expected} if job['case']=='full' and job['takes']==0 else None
            require(value==want and job['takes']<(2 if job['case']=='full' else 1),'Repeated or wrong result take');job['takes']+=1
        elif op=='publish_cancel':
            job=jobs[cmd['job']];require(job['case']=='full' and job['state']=='succeeded' and job['takes']==2 and value=='already_finished','Late cancellation changed success');cancelled+=1
        elif op=='publish_forget':
            job=jobs.pop(cmd['job']);require(value is None and job['takes']==(2 if job['case']=='full' else 1),'Receipt not collected before forget')
        elif op=='admission':
            exclusive_admission(value);readers=value['readers'];shared=value['shared']
            require(readers['live_sessions']==readers['reserved_memory_bytes']==readers['reserved_temp_bytes']==readers['retained_reply_bytes']==readers['retained_session_handles']==0,'Unexpected reader allocation/retention')
            require(shared['packings']==shared['exports']==shared['extractions']==0 and shared['closed']==bool(shutdowns),'Unexpected work or admission closure');admissions.append(value)
            if not jobs:
                require(shared['active_operations']==0,'Reservation leaked after job forget')
                if last_job==case['success_snapshot']['job_id']:require(value==case['after_conversion_admission'],'After-conversion ledger differs')
            elif jobs[last_job]['case']=='full':
                if not observations or observations[-1]!=value:observations.append(value)
        elif op=='shutdown':require(not jobs and shutdowns==0 and value is None,'Premature/repeated shutdown');shutdowns+=1
        else:raise AssertionError('Unexpected CC-CEDICT command: '+op)
    require(len(all_jobs)==8 and not jobs and rejected==2 and cancelled==shutdowns==1,'CC-CEDICT job/API lifecycle incomplete')
    require(observations==case['active_admission_observations'] and observations and any(x['shared']['conversions']==1 for x in observations),'Active CC-CEDICT admission summary differs')
    require(admissions[-1]==r['final_admission'] and r['final_admission']['shared']['closed'],'CC-CEDICT final cleanup differs')
    return {'primary_rows':125369,'traditional_entries':77993,'entries':203362,'canonical_TXT_bytes':76339785,'controller_exchanges':len(r['controller_transcript']),'successful_publications':1,'expected_job_refusals':7,'expected_API_refusals':2,'max_observed_RSS_bytes':r['peak_RSS_bytes'],'all_final_reservations_zero':True,'scope':'Exact native raw output SHA agrees with fresh Mac original Python and independent complete local reference; exact-source-bound harness asserts file preservation and private cleanup. All reported exclusive ledgers and controller exchanges reviewed. Actual native TXT files not attached; no native execution locally or hard RSS claim; Revised/WFG and M2 closeout pending.'}


if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
