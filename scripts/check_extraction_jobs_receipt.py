"""Review reported background publication, shared charges and file recipes.

No Rust execution or access to the user's actual output trees is implied.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import struct
from check_stream_extract_receipt import recipe_hash
from m2_extraction_jobs import admission

def require(ok,message):
    if not ok:raise AssertionError(message)
def review(report):
    require(report['status']=='m2_background_extraction_shared_admission_passed_larger_paths_pending' and report['stage']=='complete','Background batch incomplete')
    require(not report['M2_complete'] and not report['production_readiness'] and report['native_readers']=='NOT_REQUESTED','Do not expand qualification scope')
    require([(s['name'],s['returncode']) for s in report['steps']]==[(n,0) for n in ['refresh-extraction-jobs','extraction-job-tests','build-extraction-jobs','build-index-seed','seed-reader-index']],'Rust/build/index receipt differs')
    require([c['case'] for c in report['checks']]==['cross-block','large-resource','many-files'],'Scenario inventory differs')
    totals=Counter();reader_digests=set();maximum=0
    for case in report['checks']:
        name=case['case'];require(case['status']=='background_extraction_and_shared_admission_passed' and 0<case['peak_RSS_bytes']<=384*1024*1024,'Scenario status/RSS differs');maximum=max(maximum,case['peak_RSS_bytes'])
        if name=='cross-block':recipes=[('data.bin',200000,4),('empty.bin',0,0)]
        elif name=='large-resource':recipes=[('prefix.bin',17,11),('assets/字-مرحبا-𠀀.bin',32*1024*1024+7,37),('empty.bin',0,0)]
        else:recipes=[(f'files/f{i:05d}.bin',256,i) for i in range(4096)]
        expected={};frame=hashlib.sha256()
        for ordinal,(key,size,seed) in enumerate(recipes):
            digest=recipe_hash(size,seed);raw=key.encode();expected[key]={'bytes':size,'sha256':digest.hex()};frame.update(struct.pack('<QQ',ordinal,len(raw))+raw+struct.pack('<Q',size)+digest)
        receipt=case['receipt'];require(case['files']==expected,'Reported background file hashes differ from recipes')
        require(receipt['profile']=='mdd-stream-extract-v1' and receipt['source_sha256']==case['source_sha256'] and receipt['resources']==len(recipes) and receipt['payload_bytes']==sum(s for _,s,_ in recipes) and receipt['largest_resource_bytes']==max(s for _,s,_ in recipes) and receipt['framed_resources_sha256']==frame.hexdigest(),'Background publication receipt differs')
        require(receipt['materialized_record_limit']==receipt['locator_bytes']==0 and receipt['parser_peak_bytes']<=receipt['parser_budget_bytes']==64*1024*1024 and receipt['plan_charge']<=16*1024*1024,'Extractor resource limits differ')
        for field,r,e in [('two_reader_admission',2,0),('after_reader_release',1,0),('overlap_observation',1,1),('after_publication',1,0),('final_admission',0,0)]:admission(case[field],r,e)
        final=case['final_admission'];require(final['shared']['closed'] and final['readers']['closed'] and final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final reservations/handles/replies leaked')
        require(case['success_snapshot']['state']=='succeeded' and case['success_snapshot']['error'] is None and case['success_snapshot']['result_available'],'Missing successful publication snapshot')
        require([s['error']['code'] for s in case['typed_failures']]==['unsafe_path','integrity','destination_exists'] and all(s['state']=='failed' and not s['error']['publication_uncertain'] for s in case['typed_failures']),'Typed ordinary failure receipts differ')
        page={'operation':'page','value':{'basis':'exact','offset':1,'total':2,'next_offset':None,'rows':[{'ordinal':2,'key':'apple','text':'second'}]}}
        require(case['reader_page_replies']==[page],'Reader page changed during extraction composition')
        jobs={};finished=Counter();errors=Counter();receipts=0;reader_pages=0;admissions=[];sessions=set();closed=set();rjobs={}
        for exchange in case['controller_transcript']:
            command=exchange['command'];reply=exchange['reply'];op=command['op'];totals['controller_exchanges']+=1
            require(('ok' in reply)!=('error' in reply),'Ambiguous controller reply')
            if 'error' in reply:errors[reply['error']['code']]+=1;continue
            value=reply['ok']
            if op=='extract':
                jid=value['job'];require(jid not in jobs,'Reused extraction ID');jobs[jid]={'request':command['request'],'pre_cancel':command.get('pre_cancel',False),'taken':False,'revision':0}
            elif op=='extract_job':
                jid=command['job'];record=jobs[jid];state=value['state'];require(value['job_id']==jid and value['operation']=='extract_mdd' and value['revision']>=record['revision'],'Wrong job identity or regressed revision');record['revision']=value['revision']
                if record.get('terminal') is not None:require(state==record['terminal'],'Terminal extraction state changed')
                require(state in ['queued','running','succeeded','failed','cancelled'],'Unknown extraction state')
                if state in ['succeeded','failed','cancelled']:
                    if 'terminal' not in record:finished[state]+=1;record['terminal']=state
                    if state=='succeeded':require(value['error'] is None and value['result_available']==(not record['taken']),'Successful receipt disappeared')
                    else:
                        require(not value['result_available'] and value['error'] is not None and not value['error']['publication_uncertain'],'Ordinary failure became uncertain or retained success')
                        if record['pre_cancel']:require(state=='cancelled' and value['cancel_requested'] and value['error']['code']=='cancelled','Precancelled job ran')
                        else:
                            dest=Path(record['request']['destination']).name;code,detail={name+'-blocked':('limit_exceeded','resource_admission'),name+'-unsafe':('unsafe_path','resource_path'),name+'-checksum':('integrity','engine_checksum'),name+'-existing':('destination_exists','destination_exists')}[dest]
                            require(value['error']['code']==code and value['error']['detail']==detail,'Expected failure mapping differs')
                p=value['latest_progress']
                if p is not None:require(p['job_id']==jid and 0<=p['completed']<=p['total'],'Wrong extraction progress ownership/range')
            elif op=='extract_take':
                record=jobs[command['job']]
                if value is None:require(record.get('terminal') in ['failed','cancelled'] or record['taken'],'Receipt lost before take')
                else:require(record.get('terminal')=='succeeded' and not record['taken'] and value==receipt,'Duplicate or wrong publication receipt');record['taken']=True;receipts+=1
            elif op=='extract_forget':require(jobs[command['job']].get('terminal') in ['succeeded','failed','cancelled'],'Forgot unfinished publication');jobs.pop(command['job'])
            elif op=='extract_cancel':require(value=='already_finished' and jobs[command['job']].get('terminal')=='succeeded','Late cancel changed committed outcome')
            elif op=='extract_events':require(len(value)<=8 and all(v['state']=='cancelled' and v['job_id'] in jobs for v in value),'Unbounded or wrong coalesced events')
            elif op=='open':sessions.add(value['session']);rjobs[value['job']]={'session':value['session'],'operation':'opened','taken':False}
            elif op=='submit':require(command['request']=={'query':'apple','offset':1,'limit':1},'Unexpected reader request');rjobs[value['job']]={'session':command['session'],'operation':'page','taken':False}
            elif op=='wait':require(value is not None and value['job_id']==command['job'] and value['state']=='succeeded','Reader job failed')
            elif op=='take':
                record=rjobs[command['job']];require(not record['taken'],'Reader payload transferred twice');record['taken']=True
                if record['operation']=='page':require(value==page,'Transcript reader page differs');reader_pages+=1
                else:
                    m=value['value'];require(value['operation']=='opened' and m['records']==416 and m['kind']=='mdx' and m['policy']=='header_ascii_v1' and m['strip_key'] and not m['case_sensitive'],'Reader manifest/profile differs');reader_digests.add(m['source_sha256'])
            elif op=='forget':require(rjobs.pop(command['job'])['taken'],'Reader result forgotten without collection')
            elif op=='wait_closed':require(value['closed'],'Reader close unacknowledged');closed.add(command['session'])
            elif op=='release':require(command['session'] in closed,'Reader released before managed barrier');sessions.remove(command['session'])
            elif op=='admission':admission(value);admissions.append(value)
            elif op not in ['close','shutdown']:raise AssertionError('Unexpected controller command: '+op)
        require(finished=={'failed':4,'succeeded':1,'cancelled':8} and receipts==reader_pages==1,'Job or transfer totals differ')
        require(errors=={'retention_full':1,'closed':2} and not jobs and not rjobs and not sessions,'Unexpected API refusal or retained metadata')
        require(len(admissions)==6 and admissions[:4]==[case[k] for k in ['two_reader_admission','after_reader_release','overlap_observation','after_publication']] and admissions[-1]==final,'Admission transcript/summary binding differs')
        admission(admissions[-2],0,0);totals.update(finished);totals['file_hashes_recomputed']+=len(expected);totals['API_refusals']+=sum(errors.values())
    require(len(reader_digests)==1 and totals['file_hashes_recomputed']==4101 and totals['failed']==12 and totals['succeeded']==3 and totals['cancelled']==24 and totals['API_refusals']==9 and totals['controller_exchanges']==1166,'Background matrix totals differ')
    require(maximum==6664192,'Maximum observed RSS differs')
    return {**dict(totals),'scenarios':3,'max_observed_RSS_bytes':maximum,'review':'reported file recipes, job states and shared reservations recomputed; actual user output files and Rust execution not inspected/run by reviewer'}

if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
