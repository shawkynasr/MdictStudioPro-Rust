"""Review shared publication receipts and recompute reported recipe digests.

Only the report is attached; user output files and successful Rust test stdout
are not. This checks source-bound consistency, not a second execution of Rust.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path
import struct
from large_io_oracle import ordered,digest,row,json_line
from m2_large_io import METADATA
from m2_publication_runtime import admission
from check_stream_extract_receipt import recipe_hash
from check_large_io_receipt import stream_hash

def require(ok,message):
    if not ok:raise AssertionError(message)
def review(r):
    require(r['status']=='m2_shared_larger_publication_runtime_first_gate_passed_converter_sizing_pending' and r['stage']=='complete','Shared runtime did not complete')
    require(not r['M2_complete'] and not r['production_readiness'] and r['native_readers']=='NOT_REQUESTED','Scope expanded')
    require([(s['name'],s['returncode']) for s in r['steps']]==[(n,0) for n in ['refresh-publication-runtime','publication-runtime-tests','build-publication-runtime','build-reader-seed','seed-reader-index']],'Rust/build/seed receipts differ')
    require([c['case'] for c in r['checks']]==['utf8','utf16'],'Controller scenario inventory differs')
    rows=ordered(65536,'mdx');mdx=digest(rows);mdd=digest((f'files/r{i:05d}.bin',bytes(range(256)) if i else b'') for i in range(65536));manifest=stream_hash(json_line(*row(i,'mdx')) for i in range(65536))['sha256'];exports={txt:stream_hash(k.encode()+b'\n'+p+b'\n</>\n' if txt else json_line(k,p) for k,p in rows) for txt in [False,True]};totals=Counter();maximum=0
    page={'operation':'page','value':{'basis':'exact','offset':1,'total':2,'next_offset':None,'rows':[{'ordinal':2,'key':'apple','text':'second'}]}}
    for c in r['checks']:
        name=c['case'];require(c['status']=='publication_runtime_and_shared_admission_passed' and 0<c['peak_RSS_bytes']<=384*1024*1024,'Scenario status/RSS differs');maximum=max(maximum,c['peak_RSS_bytes']);publications=c['publications'];ops=['pack_mdx','export_jsonl','export_txt','extract_mdd']+(['pack_mdd'] if name=='utf8' else []);require(len(publications)==len(ops),'Publication inventory differs');receipts={}
        for p,op in zip(publications,ops):
            q=p['request'];s=p['snapshot'];response=p['response'];value=response['receipt'];require(s['state']=='succeeded' and s['error'] is None and s['result_available'] and s['operation']==op,'Success snapshot differs');require(s['job_id'] not in receipts,'Duplicate published job');receipts[s['job_id']]=p
            require(response['kind']==q['kind']==('extraction' if op=='extract_mdd' else 'dictionary'),'Tagged response kind differs')
            if op=='extract_mdd':
                expected={};h=hashlib.sha256()
                for i,(key,size,seed) in enumerate([('assets/data.bin',200000,37),('empty.bin',0,0)]):
                    sha=recipe_hash(size,seed);raw=key.encode();expected[key]={'bytes':size,'sha256':sha.hex()};h.update(struct.pack('<QQ',i,len(raw))+raw+struct.pack('<Q',size)+sha)
                require(p['files']==expected and value['framed_resources_sha256']==h.hexdigest() and value['resources']==2 and value['payload_bytes']==value['largest_resource_bytes']==200000,'Extracted file recipes differ');require(value['profile']=='mdd-stream-extract-v1' and value['locator_bytes']==value['materialized_record_limit']==0 and value['parser_peak_bytes']<=value['parser_budget_bytes']==64*1024*1024,'Extraction profile/caps differ');totals['extracted_file_hashes_recomputed']+=2
            else:
                want=mdd if op=='pack_mdd' else mdx;require(value['profile']=='large-dictionary-io-v1' and value['operation']==op and all(value[k]==v for k,v in want.items()),'Dictionary receipt differs from recipe')
                metadata={**METADATA,'stylesheet':''} if op=='pack_mdd' else METADATA
                for k,v in {'Title':metadata['title'],'Description':metadata['description'],'StyleSheet':metadata['stylesheet'],**metadata['extra'],'KeyCaseSensitive':'No','StripKey':'No'}.items():require(value['metadata'].get(k)==v,'Metadata preservation differs')
                if op.startswith('pack_'):
                    require(q['request']['operation']==op and q['request']['metadata']==metadata and p['wire_record_digest']==want,'Packing request/wire digest differs');totals['wire_records_recomputed']+=want['records']
                    if op=='pack_mdx':
                        a=p['structural_audit'];require(q['request']['encoding']==name and value['source_sha256']==manifest,'MDX manifest/encoding differs');require(a['status']=='structural_audit_passed' and a['sha256']==a['sha256_after']==p['file_sha256'] and a['size_bytes']==value['file_bytes'] and a['records']==65536,'MDX structural audit differs');require(a['duplicate_headwords']==a['empty_bodies']==1 and a['style_markers']==65535 and a['records_without_terminal_null']==0,'MDX audit counters differ')
                else:
                    txt=op=='export_txt';require(p['file_check']==exports[txt] and value['file_bytes']==exports[txt]['bytes'],'Export bytes/hash differ');require(q['request']['operation']==op and value['source_sha256']==publications[0]['file_sha256'] and value['metadata']==publications[0]['response']['receipt']['metadata'],'Export source binding differs');totals['export_hashes_recomputed']+=1
            if 'admission_after' in p:admission(p['admission_after'],1,0,0,0)
        admission(c['two_reader_admission'],2,0,0,0);admission(c['after_reader_release'],1,0,0,0);admission(c['final_admission'],0,0,0,0);final=c['final_admission'];require(final['shared']['closed'] and final['readers']['closed'] and final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final reservations or retention leaked');require(c['reader_page_replies']==[page],'Reader page differs')
        for value in c['active_admission_observations']:admission(value,1)
        require(any(v['shared']['packings']==1 for v in c['active_admission_observations']) and any(v['shared']['exports']==1 for v in c['active_admission_observations']),'No observed reader overlap with packing/export')
        failures=c['typed_failures'];require([s['error']['code'] for s in failures]==['limit_exceeded','invalid_input','destination_exists','io'] and failures[0]['error']['detail']=='resource_admission' and all(s['state']=='failed' and not s['error']['publication_uncertain'] for s in failures),'Typed failure inventory differs');failure_map={s['job_id']:s for s in failures}
        jobs={};rjobs={};sessions=set();closed=set();outcomes=Counter();api=Counter();transferred=set();admissions=[];reader_pages=0
        for x in c['controller_transcript']:
            command=x['command'];reply=x['reply'];op=command['op'];totals['controller_exchanges']+=1;require(('ok' in reply)!=('error' in reply),'Ambiguous controller reply')
            if 'error' in reply:
                code=reply['error']['code'];require((op=='publish' and code in ['retention_full','closed']) or (op=='open' and code=='closed'),'Unexpected API error');api[code]+=1;continue
            value=reply['ok']
            if op=='publish':
                jid=value['job'];require(jid not in jobs,'Publication job reused');jobs[jid]={'request':command['request'],'pre_cancel':command.get('pre_cancel',False),'revision':0,'taken':False}
            elif op=='publish_job':
                jid=command['job'];job=jobs[jid];state=value['state'];require(value['job_id']==jid and value['revision']>=job['revision'],'Job identity/revision differs');job['revision']=value['revision'];request=job['request'];require(value['operation']==('extract_mdd' if request['kind']=='extraction' else request['request']['operation']),'Snapshot operation differs')
                require(state in ['queued','running','succeeded','failed','cancelled'],'Unknown job state')
                if 'terminal' in job:require(state==job['terminal'],'Terminal job changed')
                if state in ['succeeded','failed','cancelled']:
                    if 'terminal' not in job:outcomes[state]+=1;job['terminal']=state
                    if state=='succeeded':require(jid in receipts and value['error'] is None and value['result_available']==(not job['taken']),'Success retained-result state differs')
                    else:
                        require(not value['result_available'] and value['error'] is not None and not value['error']['publication_uncertain'],'Ordinary failure retained success/became uncertain')
                        if job['pre_cancel']:require(state=='cancelled' and value['cancel_requested'] and value['error']['code']=='cancelled','Precancelled publication ran')
                        else:require(value==failure_map[jid],'Failed snapshot differs from summary')
                progress=value['latest_progress']
                if progress is not None:require(progress['job_id']==jid and 0<=progress['completed']<=progress['total'],'Progress ownership/range differs')
            elif op=='publish_take':
                jid=command['job'];job=jobs[jid]
                if value is None:require(job.get('terminal') in ['failed','cancelled'] or job['taken'],'Success result lost before transfer')
                else:require(job.get('terminal')=='succeeded' and not job['taken'] and value==receipts[jid]['response'] and job['request']==receipts[jid]['request'],'Wrong or repeated receipt');job['taken']=True;transferred.add(jid)
            elif op=='publish_cancel':require(value=='already_finished' and jobs[command['job']].get('terminal')=='succeeded','Late cancellation changed publication')
            elif op=='publish_forget':require(jobs.pop(command['job']).get('terminal') in ['failed','cancelled','succeeded'],'Forgot active job')
            elif op=='publish_events':require(len(value)<=8 and all(s['state']=='cancelled' and s['job_id'] in jobs for s in value),'Event mailbox bound differs')
            elif op=='open':require(value['session'] not in sessions,'Reader ID reused');sessions.add(value['session']);rjobs[value['job']]={'session':value['session'],'page':False,'taken':False}
            elif op=='submit':require(command['session'] in sessions and command['request']=={'query':'apple','offset':1,'limit':1},'Reader request differs');rjobs[value['job']]={'session':command['session'],'page':True,'taken':False}
            elif op=='wait':require(value['state']=='succeeded' and value['job_id']==command['job'] and command['session']==rjobs[command['job']]['session'],'Reader job failed or identity differs')
            elif op=='take':
                job=rjobs[command['job']];require(not job['taken'] and command['session']==job['session'],'Reader result transferred twice');job['taken']=True
                if job['page']:require(value==page,'Transcript page differs');reader_pages+=1
                else:require(value['operation']=='opened' and value['value']['records']==416 and value['value']['kind']=='mdx' and value['value']['policy']=='header_ascii_v1' and value['value']['strip_key'] and not value['value']['case_sensitive'],'Reader profile differs')
            elif op=='forget':require(rjobs.pop(command['job'])['taken'],'Reader result discarded')
            elif op=='wait_closed':require(value['closed'],'Reader close not acknowledged');closed.add(command['session'])
            elif op=='release':require(command['session'] in closed,'Reader released before acknowledgement');sessions.remove(command['session'])
            elif op=='admission':admission(value);admissions.append(value)
            elif op not in ['close','shutdown']:raise AssertionError('Unknown controller command '+op)
        require(outcomes=={'succeeded':len(ops),'failed':4,'cancelled':8} and transferred==set(receipts) and reader_pages==1,'Controller terminal/transfer counts differ');require(api=={'retention_full':1,'closed':2} and not jobs and not rjobs and not sessions,'Unexpected API refusal or retained jobs/readers');require(admissions[0]==c['two_reader_admission'] and admissions[1]==c['after_reader_release'] and admissions[-1]==final,'Admission summary/transcript binding differs')
        for v in c['active_admission_observations']:require(v in admissions,'Observation absent from transcript')
        totals.update(outcomes);totals['API_refusals']+=sum(api.values());totals['reader_pages']+=reader_pages
    require(totals['succeeded']==9 and totals['failed']==8 and totals['cancelled']==16 and totals['controller_exchanges']==3331 and totals['wire_records_recomputed']==196608,'Review aggregate totals differ')
    return {**dict(totals),'scenarios':2,'max_observed_RSS_bytes':maximum,'review':'reported recipe digests, export/extraction hashes, controller states and logical ledgers recomputed; actual output files and successful Rust test stdout not attached'}
if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
