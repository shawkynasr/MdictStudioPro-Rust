"""Review source-bound converter receipts against separately run Python oracles.

No Rust execution or actual user output files are available to this reviewer.
Generate compact oracle receipts with --generate-oracles, then retain them with
the report. Validation uses those source-bound receipts without rerunning work.
"""
import json
from collections import Counter
from pathlib import Path
import tempfile
from converter_runtime_fixtures import generate,original,record_digest
from m2_converter_runtime import admission
from m2_sizing import sha,ROOT

def require(ok,message):
    if not ok:raise AssertionError(message)
def generate_oracles(report):
    for n,h in {**report['source_sha256'],**report['legacy_oracle_sha256']}.items():require(sha(ROOT/n)==h,'Oracle/runtime source changed: '+n)
    values={}
    with tempfile.TemporaryDirectory() as directory:
        directory=Path(directory)
        for case in generate(directory):
            kind=case['kind'];print('Recomputing original Python oracle:',kind,flush=True);output=directory/(kind+'.txt');entries,metrics,comments=original(case['source'],kind,output);values[kind]={'normalized_record_digest':record_digest(entries,kind),'metrics':metrics,'comments_count':comments,'input_rows':case['input_rows'],'raw_python_sha256':sha(output),'file_bytes':output.stat().st_size}
            if kind=='cc_cedict':values[kind]['input_sha256']=sha(case['source'])
    return {'method':'Full regenerated fixture files and captured original Python plugins; existing narrowly scoped MOE set-order comparator only','source_sha256':report['source_sha256'],'legacy_oracle_sha256':report['legacy_oracle_sha256'],'cases':values}
def review(r,oracles):
    require(r['status']=='m2_larger_six_converter_shared_runtime_first_gate_passed_real_inputs_pending' and r['stage']=='complete','Converter runtime incomplete');require(not r['M2_complete'] and not r['production_readiness'] and r['native_readers']=='NOT_REQUESTED','Scope expanded')
    require([(s['name'],s['returncode']) for s in r['steps']]==[(n,0) for n in ['refresh-converter-runtime','converter-runtime-tests','build-converter-runtime','build-reader-seed','seed-reader-index']],'Rust/build command receipts differ');require(oracles['source_sha256']==r['source_sha256'] and oracles['legacy_oracle_sha256']==r['legacy_oracle_sha256'],'Independent oracle source bindings differ')
    kinds=['cc_cedict','moe_revised','moe_revised_wfg','moe_concise','moe_idioms','moe_mini'];require([c['case'] for c in r['checks']]==kinds and set(oracles['cases'])==set(kinds),'Six-converter inventory differs');totals=Counter();maximum=0;nonidentical=[]
    page={'operation':'page','value':{'basis':'exact','offset':1,'total':2,'next_offset':None,'rows':[{'ordinal':2,'key':'apple','text':'second'}]}}
    for c in r['checks']:
        kind=c['case'];o=oracles['cases'][kind];receipt=c['receipt'];require(c['status']=='larger_converter_python_parity_and_shared_admission_passed' and 0<c['peak_RSS_bytes']<=384*1024*1024,'Scenario status/RSS differs');maximum=max(maximum,c['peak_RSS_bytes']);require(c['normalized_record_digest']==o['normalized_record_digest'] and c['expected_metrics']==receipt['metrics']==o['metrics'],'Records/HTML/order/metrics differ from independent original Python conversion');require(receipt['entries']==o['normalized_record_digest']['records'] and receipt['comments_count']==o['comments_count'] and receipt['file_bytes']==o['file_bytes'],'Thin counts/file extent differ')
        require(c['input_rows']==o['input_rows'] and receipt['profile']=='larger-owned-converters-v1' and receipt['converter']==kind and receipt['txt_profile']=='canonical_v1' and receipt['source_sha256']==c['input_sha256'],'Profile/input/fixture binding differs');require(c['request']['kind']=='conversion' and c['request']['request']['converter']==kind,'Conversion request differs')
        if kind=='cc_cedict':require(c['input_sha256']==o['input_sha256'],'CC-CEDICT recipe byte identity differs')
        require(c['raw_python_bytes_equal']==(c['rust_output_sha256']==c['python_output_sha256']),'Raw equality/hash fields disagree')
        if kind not in ['moe_revised','moe_concise']:require(c['raw_python_bytes_equal'] and c['rust_output_sha256']==o['raw_python_sha256'],'Exact Python/Rust byte equality differs')
        elif not c['raw_python_bytes_equal']:nonidentical.append(kind)
        expected=['limit_exceeded','destination_exists','limit_exceeded','limit_exceeded']
        if kind=='cc_cedict':expected+=['invalid_encoding','invalid_input','limit_exceeded','limit_exceeded','invalid_input']
        if kind=='moe_revised':expected+=['limit_exceeded','limit_exceeded','limit_exceeded','malformed_source','malformed_workbook','sheet_not_found']
        failures=c['typed_failures'];require([s['error']['code'] for s in failures]==expected and failures[0]['error']['detail']=='resource_admission' and all(s['state']=='failed' and not s['error']['publication_uncertain'] for s in failures),'Typed refusal inventory differs');failure_map={s['job_id']:s for s in failures}
        admission(c['two_reader_admission'],2,0);admission(c['after_reader_release'],1,0);admission(c['after_publication'],1,0);admission(c['final_admission'],0,0);final=c['final_admission'];require(final['shared']['active_operations']==0 and final['shared']['closed'] and final['readers']['closed'] and final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final admission/reader retention not empty');require(c['reader_page_reply']==page,'Concurrent reader page differs')
        require(c['active_admission_observations'],'No conversion overlap observation')
        for a in c['active_admission_observations']:admission(a,1,1)
        success=c['success_snapshot'];require(success['state']=='succeeded' and success['operation']=='convert_to_txt' and success['result_available'] and success['error'] is None,'Success snapshot differs');success_id=success['job_id'];jobs={};rjobs={};sessions=set();closed=set();finished=Counter();api=Counter();taken=0;pages=0;admissions=[]
        for x in c['controller_transcript']:
            command=x['command'];reply=x['reply'];op=command['op'];totals['controller_exchanges']+=1;require(('ok' in reply)!=('error' in reply),'Ambiguous controller response')
            if 'error' in reply:
                code=reply['error']['code'];require((op=='publish' and code in ['retention_full','closed']) or (op=='open' and code=='closed'),'Unexpected API error');api[code]+=1;continue
            value=reply['ok']
            if op=='publish':
                jid=value['job'];require(jid not in jobs,'Publication ID reused');require(command['request']['kind']=='conversion' and command['request']['request']['converter']==kind,'Unexpected queued converter');jobs[jid]={'request':command['request'],'revision':0,'taken':False,'pre_cancel':command.get('pre_cancel',False)}
            elif op=='publish_job':
                jid=command['job'];job=jobs[jid];state=value['state'];require(value['job_id']==jid and value['operation']=='convert_to_txt' and value['revision']>=job['revision'],'Job identity/revision differs');job['revision']=value['revision'];require(state in ['queued','running','succeeded','failed','cancelled'],'Unknown job state')
                if 'terminal' in job:require(job['terminal']==state,'Terminal state changed')
                if state in ['succeeded','failed','cancelled']:
                    if 'terminal' not in job:finished[state]+=1;job['terminal']=state
                    if state=='succeeded':require(jid==success_id and value['error'] is None and value['result_available']==(not job['taken']),'Success/result availability differs')
                    else:
                        require(not value['result_available'] and value['error'] is not None and not value['error']['publication_uncertain'],'Failed/cancelled job retained success or uncertainty')
                        if job['pre_cancel']:require(state=='cancelled' and value['cancel_requested'] and value['error']['code']=='cancelled','Precancelled job ran')
                        else:require(value==failure_map[jid],'Failure snapshot summary differs')
                p=value['latest_progress']
                if p is not None:require(p['job_id']==jid and 0<=p['completed']<=p['total'],'Progress identity/range differs')
            elif op=='publish_take':
                job=jobs[command['job']]
                if value is None:require(job.get('terminal') in ['failed','cancelled'] or job['taken'],'Result disappeared before transfer')
                else:require(command['job']==success_id and job.get('terminal')=='succeeded' and not job['taken'] and value=={'kind':'conversion','receipt':receipt} and job['request']==c['request'],'Wrong/repeated thin result');job['taken']=True;taken+=1
            elif op=='publish_cancel':require(value=='already_finished' and jobs[command['job']].get('terminal')=='succeeded','Late cancel changed committed success')
            elif op=='publish_forget':require(jobs.pop(command['job']).get('terminal') in ['succeeded','failed','cancelled'],'Forgot active job')
            elif op=='publish_events':require(len(value)<=8 and all(s['state']=='cancelled' and s['job_id'] in jobs for s in value),'Mailbox retention differs')
            elif op=='open':sessions.add(value['session']);rjobs[value['job']]={'session':value['session'],'page':False,'taken':False}
            elif op=='submit':require(command['session'] in sessions and command['request']=={'query':'apple','offset':1,'limit':1},'Page request differs');rjobs[value['job']]={'session':command['session'],'page':True,'taken':False}
            elif op=='wait':require(value['state']=='succeeded' and value['job_id']==command['job'] and command['session']==rjobs[command['job']]['session'],'Reader job failed or mismatched')
            elif op=='take':
                job=rjobs[command['job']];require(not job['taken'],'Reader result repeated');job['taken']=True
                if job['page']:require(value==page,'Transcript page differs');pages+=1
                else:require(value['operation']=='opened' and value['value']['records']==416 and value['value']['policy']=='header_ascii_v1','Reader manifest differs')
            elif op=='forget':require(rjobs.pop(command['job'])['taken'],'Reader result not collected')
            elif op=='wait_closed':require(value['closed'],'Reader close not acknowledged');closed.add(command['session'])
            elif op=='release':require(command['session'] in closed,'Reader released before barrier');sessions.remove(command['session'])
            elif op=='admission':admission(value);admissions.append(value)
            elif op not in ['close','shutdown']:raise AssertionError('Unknown command '+op)
        require(finished=={'succeeded':1,'failed':len(expected),'cancelled':8} and taken==pages==1,'Terminal/transfer totals differ');require(api=={'retention_full':1,'closed':2} and not jobs and not rjobs and not sessions,'API inventory or retained objects differ');require(admissions[0]==c['two_reader_admission'] and admissions[1]==c['after_reader_release'] and admissions[-1]==final and c['after_publication'] in admissions,'Admission transcript binding differs')
        for v in c['active_admission_observations']:require(v in admissions,'Overlap observation absent from transcript')
        totals.update(finished);totals['API_refusals']+=sum(api.values());totals['reader_pages']+=pages;totals['records_recomputed']+=receipt['entries']
    require(totals['succeeded']==6 and totals['failed']==35 and totals['cancelled']==48 and totals['records_recomputed']==68000 and totals['controller_exchanges']==2964,'Converter aggregate inventory differs')
    return {**dict(totals),'converters':6,'max_observed_RSS_bytes':maximum,'documented_set_order_raw_differences':nonidentical,'review':'full local original-Python oracle records recomputed; reported normalized parity and controller/admission states checked; user output files and successful Rust test stdout not attached'}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--generate-oracles',type=Path);p.add_argument('--oracles',type=Path);a=p.parse_args();r=json.loads(a.report.read_text())
    if a.generate_oracles:
        o=generate_oracles(r);a.generate_oracles.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
    else:o=json.loads(a.oracles.read_text())
    print(json.dumps(review(r,o),indent=2))
