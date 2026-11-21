"""Review full official Mini/Idioms receipts against retained Python sizing.

Native output files are private on the user's Mac. Their full byte comparison,
source preservation and temporary-file cleanup are assertions of the exact-bound
Mac harness. This review checks hashes against the independent local original
Python references, source/lock identities and every reported controller exchange.
"""
import json
from pathlib import Path
from m2_sizing import ROOT,sha,require,RSS_TARGET
from m2_converter_runtime import admission
from converter_runtime_lock import LOCK,check_lock

def review(report):
    measured=json.loads((ROOT/'docs/evidence/official-converter-input-inspection/measurements.json').read_text())
    require(report['status']=='full_official_mini_idioms_passed_other_real_converters_need_scaling' and report['stage']=='complete','Official batch incomplete')
    require(not report['M2_complete'] and not report['all_six_real_converters_qualified'] and report['native_readers']=='NOT_REQUESTED','Official scope expanded')
    require(report['steps']==[{'name':'build-qualified-runtime','returncode':0}],'Official build receipt differs')
    require(report['protected_source_sha256']==measured['protected_source_sha256'] and len(report['protected_source_sha256'])==214,'Official protected sources differ')
    require(report['legacy_oracle_sha256']==measured['legacy_oracle_sha256'],'Original Python identities differ')
    names={'scripts/m2_official_mini_idioms.py','scripts/test_official_converter_sources.py','docs/evidence/official-converter-input-inspection/measurements.json'}
    require(set(report['source_sha256'])==names,'Official harness identity set differs')
    for name,digest in {**report['protected_source_sha256'],**report['source_sha256'],**report['legacy_oracle_sha256']}.items():
        require(sha(ROOT/name)==digest,'Official source changed: '+name)
    require(report['dependency_packages']==check_lock() and report['dependency_lock_sha256']==sha(ROOT/LOCK),'Official graph/lock differs')
    held=[{'converter':c['converter'],'records':c['records'],'decoded_bytes':c['decoded_key_body_bytes'],'blockers':c['native_profile_blockers']} for c in measured['legacy_output_measurements'] if c['native_profile_blockers']]
    require(report['held_datasets']==held,'Held datasets differ')
    require([c['case'] for c in report['checks']]==['moe_mini','moe_idioms'],'Official case inventory differs')
    exchanges=records=maximum=0
    for case in report['checks']:
        kind=case['case'];spec=next(s for s in measured['legacy_output_measurements'] if s['converter']==kind)
        archive=next(a for a in measured['archives'] if a['member']==spec['input'])
        require(case['status']=='full_official_source_exact_python_parity_passed' and case['source_sha256']==archive['source_sha256'] and case['data_rows']==spec['data_rows'],'Official source/count differs')
        require(case['python_output_sha256']==case['native_output_sha256']==case['reference_output_sha256']==spec['output_sha256'],'Full output differs from independent Python reference')
        expected={'comments_count':0,'converter':kind,'entries':spec['records'],'file_bytes':spec['file_bytes'],'metrics':{'alias_redirects':0,'primary_entries':spec['records'],'skipped_rows_or_lines':0,'traditional_entries':0},'profile':'larger-owned-converters-v1','source_sha256':archive['source_sha256'],'txt_profile':'canonical_v1'}
        require(case['receipt']==expected,'Official native receipt differs')
        require(0<case['peak_RSS_bytes']<=RSS_TARGET,'Official observed RSS exceeds envelope');maximum=max(maximum,case['peak_RSS_bytes'])
        job=None;state=None;revision=0;takes=cancels=forgets=shutdowns=0;observed=[];ledgers=[];last_status=None;forgotten=False
        for exchange in case['controller_transcript']:
            exchanges+=1;command=exchange['command'];reply=exchange['reply'];op=command['op'];require(set(reply)=={'ok'},'Unexpected official API error');value=reply['ok']
            if op=='publish':
                require(job is None and set(command)=={'op','request'},'Unexpected/repeated official publication')
                request=command['request'];payload=request['request'];require(request['kind']=='conversion' and set(payload)=={'converter','input','destination','worksheet'},'Unexpected conversion options')
                require(payload['converter']==kind and payload['worksheet']==spec['worksheet'] and Path(payload['input']).name==spec['input'] and Path(payload['destination']).name==kind+'.txt','Wrong full official input/request')
                job=value['job']
            elif op=='publish_job':
                require(job is not None and not forgotten and command['job']==job and value['job_id']==job and value['operation']=='convert_to_txt','Wrong publication job')
                require(value['revision']>=revision and value['state'] in ['queued','running','succeeded'] and value['error'] is None and not value['cancel_requested'],'Publication failed/regressed')
                require(state!='succeeded' or value['state']=='succeeded','Terminal publication regressed')
                state=value['state'];revision=value['revision'];last_status=value
                if state=='succeeded':require(value==case['success_snapshot'] and value['result_available'],'Official success snapshot differs')
            elif op=='publish_take':
                require(command['job']==job and state=='succeeded' and not forgotten,'Premature/wrong receipt transfer')
                require(value==({'kind':'conversion','receipt':expected} if takes==0 else None) and takes<2,'Repeated/missing official receipt');takes+=1
            elif op=='publish_cancel':
                require(command['job']==job and state=='succeeded' and takes==2 and value=='already_finished','Late cancellation changed success');cancels+=1
            elif op=='publish_forget':
                require(command['job']==job and takes==2 and cancels==1 and not forgotten and value is None,'Wrong publication cleanup');forgotten=True;forgets+=1
            elif op=='admission':
                admission(value,0);require(not any(value['shared'][k] for k in ['readers','packings','exports','extractions']),'Unrequested work active')
                require(value['readers']['retained_session_handles']==value['readers']['retained_reply_bytes']==0,'Reader retention leaked')
                ledgers.append(value)
                if not forgotten:
                    if not observed or observed[-1]!=value:observed.append(value)
                else:require(value['shared']['active_operations']==0 and value['shared']['closed']==bool(shutdowns),'Official idle cleanup differs')
            elif op=='shutdown':
                require(forgotten and shutdowns==0 and value is None,'Premature/repeated shutdown');shutdowns+=1
            else:raise AssertionError('Unexpected official command: '+op)
        require(takes==2 and cancels==forgets==shutdowns==1 and state=='succeeded','Official lifecycle incomplete')
        require(observed==case['active_admission_observations'] and observed and any(x['shared']['conversions']==1 for x in observed),'Active admission summary differs')
        require(ledgers[-1]==case['final_admission'] and ledgers[-1]['shared']['closed'] and last_status==case['success_snapshot'],'Final ledger/snapshot differs')
        records+=expected['entries']
    return {'full_official_datasets':2,'records':records,'controller_exchanges':exchanges,'max_observed_RSS_bytes':maximum,'all_final_reservations_zero':True,'scope':'Full output hashes cross-checked against retained independent original Python references; actual native output bytes, source preservation and private cleanup represented by exact-source-bound Mac harness; M2 partial'}

if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
