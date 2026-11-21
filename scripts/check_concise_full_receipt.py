"""Review source-bound full Concise parity, refusals and controller lifecycle.

Actual native TXT/source/temp files stay private on the Mac. The exact harness
compares every record and asserts file preservation/cleanup. This reviewer checks
the resulting normalized digest against independently retained full Python runs,
source identities, dependencies and every reported controller exchange.
"""
import json
from pathlib import Path
from m2_sizing import ROOT,require,sha,RSS_TARGET
from m2_concise_full import REFERENCE,protected_sources,fingerprints
from concise_runtime_lock import LOCK,check_lock
from m2_converter_runtime import admission

def review(r):
    ref=json.loads((ROOT/REFERENCE).read_text());source_hash=ref['archive']['source_sha256']
    require(r['status']=='full_official_concise_passed_other_large_converters_and_closeout_pending' and r['stage']=='complete','Concise batch incomplete')
    require(not r['M2_complete'] and not r['RSS_is_OS_limit'] and r['native_readers']=='NOT_REQUESTED' and r['RSS_observation_target_bytes']==RSS_TARGET,'Concise scope expanded')
    require(r['steps']==[{'name':'concise-runtime-tests','returncode':0},{'name':'build-concise-runtime','returncode':0}],'Concise native commands differ')
    require(r['protected_source_sha256']==protected_sources() and r['source_sha256']==fingerprints(),'Concise source identities changed')
    require(r['legacy_oracle_sha256']==ref['legacy_oracle_sha256'],'Concise Python identities differ')
    for name,digest in r['legacy_oracle_sha256'].items():require(sha(ROOT/name)==digest,'Captured Python source differs')
    require(r['dependency_packages']==check_lock() and r['dependency_lock_sha256']==sha(ROOT/LOCK),'Concise dependency graph/lock differs')
    require(len(r['checks'])==1 and r['checks'][0]['case']=='full-official-concise','Concise case inventory differs');case=r['checks'][0]
    require(case['data_rows']==ref['data_rows']==45178 and case['source_sha256']==source_hash,'Concise full-source identity/count differs')
    expected={'comments_count':0,'converter':'moe_concise','entries':44445,'file_bytes':25093253,'metrics':{'alias_redirects':0,'primary_entries':44445,'skipped_rows_or_lines':0,'traditional_entries':0},'profile':'moe-concise-owned-v1','source_sha256':source_hash,'txt_profile':'canonical_v1'}
    require(case['receipt']==expected and case['normalized_record_digest']==ref['normalized_record_digest'],'Concise normalized full-output content differs')
    success=case['success_snapshot']
    require(success['state']=='succeeded' and success['error'] is None and success['result_available'] and not success['cancel_requested'],'Concise success state differs')
    require(success['latest_progress']=={'completed':44445,'job_id':success['job_id'],'phase':'published','stage':'publishing','total':44445},'Concise committed progress differs')
    python=r['python_reference_observation'];native=r['native_observation']
    require(python=={'source_sha256':source_hash,'raw_sha256':case['python_output_sha256'],'normalized_record_digest':ref['normalized_record_digest'],'file_bytes':expected['file_bytes']},'Concise Python reference summary differs')
    require(native=={'snapshot':case['success_snapshot'],'receipt':expected,'raw_sha256':case['native_output_sha256'],'normalized_record_digest':ref['normalized_record_digest']},'Concise native summary differs')
    require(case['raw_python_bytes_equal']==(case['python_output_sha256']==case['native_output_sha256']),'Raw versus normalized comparison misreported')
    require(0<r['peak_RSS_bytes']<=RSS_TARGET,'Concise RSS observation exceeds envelope')
    names=['old-row-cap','old-rectangle-cap','cannot-grow-rows','cannot-grow-cells','pre-cancel','existing-output'];codes=['limit_exceeded','limit_exceeded','invalid_input','invalid_input','cancelled','destination_exists']
    require([f['case'] for f in r['expected_failures']]==names,'Concise refusal inventory differs')
    failures={f['case']:f for f in r['expected_failures']};expected_tightens=[{'workbook_rows':32000},{'workbook_cells':512000},{'workbook_rows':50001},{'workbook_cells':750001},{},{}]
    expected_status={**{f['snapshot']['job_id']:f['snapshot'] for f in r['expected_failures']},case['success_snapshot']['job_id']:case['success_snapshot']}
    require(len(expected_status)==7,'Concise job identities collide')
    for f,code in zip(r['expected_failures'],codes):
        s=f['snapshot'];require(s['state']==('cancelled' if code=='cancelled' else 'failed') and s['error']['code']==code and not s['error']['publication_uncertain'] and not s['result_available'],'Concise typed refusal differs')
    require(failures['existing-output']['output_sha256_preserved']==case['native_output_sha256'],'Overwrite preservation hash differs')
    jobs={};all_jobs=[];admissions=[];observations=[];rejected=cancelled=shutdowns=0;last_job=None
    for exchange in r['controller_transcript']:
        cmd=exchange['command'];reply=exchange['reply'];op=cmd['op']
        if 'error' in reply:
            require(set(reply)=={'error'} and op=='publish' and rejected==0 and reply['error']['code']=='invalid_input' and cmd['request']['kind']=='conversion','Unexpected Concise API error')
            payload=cmd['request']['request'];require(payload['converter']=='moe_revised' and Path(payload['destination']).name=='wrong-converter.txt','Wrong converter refusal differs');rejected+=1;continue
        require(set(reply)=={'ok'},'Malformed Concise controller reply');value=reply['ok']
        if op=='publish':
            require(not jobs and cmd['request']['kind']=='conversion' and not shutdowns,'Unexpected overlapping publication')
            payload=cmd['request']['request'];require(payload['converter']=='moe_concise' and Path(payload['input']).name==ref['archive']['member'] and payload['worksheet']==ref['worksheet'],'Wrong full-source request')
            index=len(all_jobs);require(index<7,'Extra publication');name=names[index] if index<5 else 'full' if index==5 else 'existing-output';tighten=payload.get('tighten',{})
            require(tighten==(expected_tightens[index] if index<5 else {}),'Wrong limits in refusal/publication request')
            require(bool(cmd.get('pre_cancel',False))==(name=='pre-cancel'),'Precancel option differs')
            jid=value['job'];require(jid in expected_status and jid not in all_jobs,'Unexpected/reused job id');jobs[jid]={'state':None,'revision':0,'takes':0,'case':name};all_jobs.append(jid);last_job=jid
            if index<5:require(cmd['request']==failures[name]['request'],'Refusal request summary differs')
        elif op=='publish_job':
            jid=cmd['job'];job=jobs[jid];require(value['job_id']==jid and value['operation']=='convert_to_txt' and value['revision']>=job['revision'],'Concise job revision/identity differs')
            require(job['state'] not in ['succeeded','failed','cancelled'] or value['state']==job['state'],'Terminal Concise state regressed');job.update(state=value['state'],revision=value['revision'])
            progress=value['latest_progress']
            if progress:require(progress['job_id']==jid and 0<=progress['completed']<=progress['total'],'Concise progress identity/bounds differ')
            if value['state'] in ['succeeded','failed','cancelled']:require(value==expected_status[jid],'Concise terminal summary differs')
        elif op=='publish_take':
            job=jobs[cmd['job']];require(job['state'] in ['succeeded','failed','cancelled'],'Premature result take')
            want={'kind':'conversion','receipt':expected} if job['case']=='full' and job['takes']==0 else None
            require(value==want and job['takes']<(2 if job['case']=='full' else 1),'Repeated or wrong result take');job['takes']+=1
        elif op=='publish_cancel':
            job=jobs[cmd['job']];require(job['case']=='full' and job['state']=='succeeded' and job['takes']==2 and value=='already_finished','Late cancellation changed success');cancelled+=1
        elif op=='publish_forget':
            job=jobs.pop(cmd['job']);require(value is None and job['takes']==(2 if job['case']=='full' else 1),'Receipt not collected before forget')
        elif op=='admission':
            admission(value,0);readers=value['readers'];shared=value['shared']
            require(readers['live_sessions']==readers['reserved_memory_bytes']==readers['reserved_temp_bytes']==readers['retained_reply_bytes']==readers['retained_session_handles']==0,'Unexpected reader allocation/retention')
            require(shared['packings']==shared['exports']==shared['extractions']==0 and shared['closed']==bool(shutdowns),'Unexpected work or admission closure');admissions.append(value)
            if not jobs:
                require(shared['active_operations']==0,'Reservation leaked after job forget')
                if last_job==case['success_snapshot']['job_id']:require(value==case['after_conversion_admission'],'After-conversion ledger differs')
            elif jobs[last_job]['case']=='full':
                if not observations or observations[-1]!=value:observations.append(value)
        elif op=='shutdown':require(not jobs and shutdowns==0 and value is None,'Premature/repeated shutdown');shutdowns+=1
        else:raise AssertionError('Unexpected Concise command: '+op)
    require(len(all_jobs)==7 and not jobs and rejected==cancelled==shutdowns==1,'Concise job/API lifecycle incomplete')
    require(observations==case['active_admission_observations'] and observations and any(x['shared']['conversions']==1 for x in observations),'Active Concise admission summary differs')
    require(admissions[-1]==r['final_admission'] and r['final_admission']['shared']['closed'],'Concise final cleanup differs')
    return {'source_data_rows':45178,'entries':44445,'canonical_TXT_bytes':25093253,'controller_exchanges':len(r['controller_transcript']),'successful_publications':1,'expected_job_refusals':6,'wrong_converter_API_refusals':1,'max_observed_RSS_bytes':r['peak_RSS_bytes'],'all_final_reservations_zero':True,'scope':'Full normalized digest agrees with two independent local original Python runs; exact-source-bound Mac harness asserts full record comparison and file preservation/cleanup. Actual native TXT files are not attached. Full-size reader overlap and hard RSS enforcement are not qualified; M2 partial.'}

if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
