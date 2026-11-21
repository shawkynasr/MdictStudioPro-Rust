"""Full CC-CEDICT qualification with exclusive admission and chunked TXT publication."""
import argparse
import json
import shutil
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller
from m2_converter_runtime import request
from m2_official_mini_idioms import extract_sources
from converter_runtime_fixtures import original
from cc_runtime_lock import MANIFEST,LOCK,check_lock

REFERENCE='docs/evidence/cc-full-source-reference/reference.json'
def exclusive_admission(value):
    shared=value['shared'];readers=value['readers']
    require(shared['max_operations']==2 and shared['memory_cap']==384*1024*1024 and shared['temporary_cap']==4*1024*1024*1024,'Shared ceiling differs')
    require(type(shared['conversions']) is int and 0<=shared['conversions']<=1,'Invalid conversion reservation count')
    require(shared['readers']==shared['packings']==shared['exports']==shared['extractions']==0 and shared['active_operations']==shared['conversions'],'Exclusive conversion overlap')
    require(shared['reserved_memory_bytes']==shared['conversions']*384*1024*1024 and shared['reserved_temporary_bytes']==shared['conversions']*768*1024*1024,'Exclusive conversion charge differs')
    require(readers['live_sessions']==readers['reserved_memory_bytes']==readers['reserved_temp_bytes']==readers['retained_reply_bytes']==readers['retained_session_handles']==0 and readers['retained_reply_cap']==8*1024*1024,'Unexpected reader allocation or retention')
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-concise-full-user-run/m2-concise-full-report.json').read_text())
    result={**r['protected_source_sha256'],**r['source_sha256']}
    require(len(result)==229,'Protected identity inventory differs')
    for name,h in result.items():require(sha(ROOT/name)==h,'Previously qualified source changed: '+name)
    return result
def fingerprints():
    files=[p for p in (ROOT/'m2/cc-runtime').rglob('*') if p.is_file() and 'target' not in p.parts]
    files += [ROOT/n for n in ['scripts/m2_cc_full.py','scripts/cc_runtime_lock.py','scripts/test_cc_full.py',REFERENCE]]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();require(out.name.startswith('m2-cc-full-out'),'Use m2-cc-full-out prefix for private output exclusion');out.mkdir(exist_ok=False)
    report={'status':'m2_cc_full_failed','stage':'preflight','M2_complete':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'expected_failures':[],'RSS_observation_target_bytes':RSS_TARGET,'RSS_is_OS_limit':False}
    active=None
    try:
        ref=json.loads((ROOT/REFERENCE).read_text());report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['legacy_oracle_sha256']=ref['legacy_oracle_sha256']
        for name,h in report['legacy_oracle_sha256'].items():require(sha(ROOT/name)==h,'Original Python oracle changed: '+name)
        report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        sources=extract_sources(args.archives.resolve(),out/'sources',[ref['archive']]);source=sources[ref['archive']['member']];before=sha(source)
        cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        for name,command in [('cc-runtime-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('build-cc-runtime',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-cc-runtime'])]:
            report['stage']=name;print(name,flush=True);result=timed_run(command);log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':result.returncode};report['steps'].append(step)
            if result.returncode:step['failure_log_tail']=log[-64000:]
            require(result.returncode==0,'Native command failed: '+name)
        binary=ROOT/'m2/cc-runtime/target/debug/studio-cc-runtime';report['binary_sha256']=sha(binary)
        report['stage']='full-python-oracle';print('Converting complete CC-CEDICT source with captured Python',flush=True)
        oracle=out/'python-cc.txt';expected,metrics,comments=original(source,'cc_cedict',oracle)
        report['python_reference_observation']={'source_sha256':before,'raw_sha256':sha(oracle),'file_bytes':oracle.stat().st_size,'metrics':metrics,'comments_count':comments}
        require(sha(oracle)==ref['raw_python_output_sha256'] and oracle.stat().st_size==ref['expected_file_bytes'] and len(expected)==ref['expected_entries'],'Mac original Python differs from complete local reference')
        require(metrics=={'primary_entries':ref['primary_entries'],'alias_redirects':0,'traditional_entries':ref['traditional_entries'],'skipped_rows_or_lines':ref['skipped_lines']} and comments==ref['comments_count'],'Mac Python metrics differ')
        del expected
        outputs=out/'outputs';outputs.mkdir();scratch=out/'private-rust';scratch.mkdir();active=Controller(binary,scratch,out/'controller.json');controller=active
        def observe(value):
            exclusive_admission(value)
            shared=value['shared'];require(shared['readers']==shared['packings']==shared['exports']==shared['extractions']==0,'CC operation overlapped other work')
            require(shared['active_operations']==shared['conversions'] and shared['reserved_memory_bytes']==shared['conversions']*384*1024*1024 and shared['reserved_temporary_bytes']==shared['conversions']*768*1024*1024,'CC exclusive reservation differs')
        def wait_cc(jid,observations=None):
            import time
            deadline=time.monotonic()+300
            while True:
                status=controller.call('publish_job',job=jid)
                if status['state'] in ['succeeded','failed','cancelled']:return status
                value=controller.call('admission');observe(value)
                if observations is not None and (not observations or observations[-1]!=value):observations.append(value)
                require(time.monotonic()<deadline,'Full CC conversion exceeded 300 seconds');time.sleep(0.05)
        def idle():
            value=controller.call('admission');observe(value)
            require(value['shared']['active_operations']==0 and value['readers']['retained_reply_bytes']==value['readers']['retained_session_handles']==0,'Reservation or reply retention leak')
            require(not list(scratch.iterdir()),'Private input snapshot residue');return value
        def refuse(name,code,pre_cancel=False,**options):
            destination=outputs/(name+'.txt');req=request('cc_cedict',source,destination,**options);jid=controller.call('publish',request=req,pre_cancel=pre_cancel)['job'];status=wait_cc(jid)
            require(status['state']==('cancelled' if pre_cancel else 'failed') and status['error']['code']==code and not status['error']['publication_uncertain'],'Wrong typed refusal: '+name)
            require(not destination.exists() and controller.call('publish_take',job=jid) is None,'Refused conversion published or retained a result');controller.call('publish_forget',job=jid)
            report['expected_failures'].append({'case':name,'request':req,'snapshot':status,'admission':idle()})
        report['stage']='limit-refusals';print('Checking old output limits and forbidden profile growth',flush=True)
        refuse('old-entry-cap','limit_exceeded',tighten={'entries':100000})
        refuse('old-decoded-cap','limit_exceeded',tighten={'decoded_bytes':32*1024*1024})
        refuse('old-output-cap','limit_exceeded',tighten={'output_bytes':64*1024*1024})
        refuse('cannot-grow-entries','invalid_input',tighten={'entries':250001})
        refuse('cannot-grow-decoded','invalid_input',tighten={'decoded_bytes':96*1024*1024+1})
        refuse('pre-cancel','cancelled',pre_cancel=True)
        controller.call('publish',request=request('moe_revised',source,outputs/'wrong-converter.txt'),expect='invalid_input')
        controller.call('publish',request=request('cc_cedict',source,outputs/'wrong-worksheet.txt',worksheet='Sheet1'),expect='invalid_input')
        require(not (outputs/'wrong-converter.txt').exists() and not (outputs/'wrong-worksheet.txt').exists(),'Invalid request published')
        report['stage']='full-cc-cedict';print('Converting all 125369 primary rows and 77993 traditional entries',flush=True)
        destination=outputs/'cc-cedict.txt';req=request('cc_cedict',source,destination);jid=controller.call('publish',request=req)['job'];observations=[];status=wait_cc(jid,observations);require(status['state']=='succeeded','Full CC-CEDICT native conversion failed');response=controller.call('publish_take',job=jid);require(response['kind']=='conversion','Wrong native receipt kind');receipt=response['receipt'];report['native_observation']={'snapshot':status,'receipt':receipt,'raw_sha256':sha(destination)}
        require(receipt=={'profile':'cc-cedict-owned-chunked-txt-v1','converter':'cc_cedict','txt_profile':'canonical_v1','entries':ref['expected_entries'],'file_bytes':ref['expected_file_bytes'],'metrics':metrics,'comments_count':comments,'source_sha256':before},'Full CC-CEDICT receipt differs')
        require(sha(destination)==sha(oracle)==ref['raw_python_output_sha256'],'Full native TXT differs from both independent original-Python results')
        require(controller.call('publish_take',job=jid) is None and controller.call('publish_cancel',job=jid)=='already_finished','Thin receipt transfer or late cancellation differs');controller.call('publish_forget',job=jid);after=idle()
        # An overwrite attempt must preserve the already-published complete file.
        preserved=sha(destination);overwrite=controller.call('publish',request=req)['job'];over_status=wait_cc(overwrite);require(over_status['state']=='failed' and over_status['error']['code']=='destination_exists' and not over_status['error']['publication_uncertain'],'Wrong overwrite refusal');require(controller.call('publish_take',job=overwrite) is None and sha(destination)==preserved,'Overwrite modified output');controller.call('publish_forget',job=overwrite);idle()
        report['expected_failures'].append({'case':'existing-output','snapshot':over_status,'output_sha256_preserved':preserved})
        report['checks'].append({'case':'full-official-cc-cedict','primary_rows':ref['primary_entries'],'source_sha256':before,'receipt':receipt,'success_snapshot':status,'python_output_sha256':sha(oracle),'native_output_sha256':preserved,'raw_python_bytes_equal':preserved==sha(oracle),'active_admission_observations':observations,'after_conversion_admission':after})
        controller.call('shutdown');final=controller.call('admission');observe(final);require(final['shared']['closed'] and final['shared']['active_operations']==0,'Final admission cleanup differs');rss=controller.stop();active=None;report.update(final_admission=final,peak_RSS_bytes=rss,controller_transcript=controller.transcript)
        require(rss<=RSS_TARGET,'Observed full CC-CEDICT RSS exceeds provisional 384 MiB threshold');require(sha(source)==before and not list(scratch.iterdir()),'Source changed or private snapshot leaked')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'] and check_lock()==report['dependency_packages'],'Sources or dependencies changed during probe')
        report['stage']='complete';report['status']='full_official_cc_exclusive_chunked_publication_passed_Revised_and_closeout_pending'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'{type(error).__name__}: {error}';report['python_traceback']=traceback.format_exc()
        if isinstance(error,CommandTimeout):report['timed_out_command_output_tail']=error.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-cc-full-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_cc_full_failed')

if __name__=='__main__':raise SystemExit(main())
