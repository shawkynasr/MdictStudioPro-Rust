"""Full official Concise qualification with explicit measured worksheet limits."""
import argparse
import json
import shutil
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller
from m2_converter_runtime import admission,wait,request
from m2_official_mini_idioms import extract_sources
from converter_runtime_fixtures import parse_txt,record_digest,compare_output
from moe_fixtures import load_plugins
from concise_runtime_lock import MANIFEST,LOCK,check_lock

REFERENCE='docs/evidence/concise-full-source-reference/reference.json'
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-official-converters-user-run/m2-official-converters-report.json').read_text())
    result={**r['protected_source_sha256'],**r['source_sha256']}
    require(len(result)==217,'Protected identity inventory differs')
    for name,h in result.items():require(sha(ROOT/name)==h,'Previously qualified source changed: '+name)
    return result
def fingerprints():
    files=[p for p in (ROOT/'m2/concise-runtime').rglob('*') if p.is_file() and 'target' not in p.parts]
    files += [ROOT/n for n in ['scripts/m2_concise_full.py','scripts/concise_runtime_lock.py','scripts/test_concise_full.py',REFERENCE]]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archives',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();require(out.name.startswith('m2-concise-full-out'),'Use m2-concise-full-out prefix for private output exclusion');out.mkdir(exist_ok=False)
    report={'status':'m2_concise_full_failed','stage':'preflight','M2_complete':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'expected_failures':[],'RSS_observation_target_bytes':RSS_TARGET,'RSS_is_OS_limit':False}
    active=None
    try:
        ref=json.loads((ROOT/REFERENCE).read_text());report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['legacy_oracle_sha256']=ref['legacy_oracle_sha256']
        for name,h in report['legacy_oracle_sha256'].items():require(sha(ROOT/name)==h,'Original Python oracle changed: '+name)
        report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        sources=extract_sources(args.archives.resolve(),out/'sources',[ref['archive']]);source=sources[ref['archive']['member']];before=sha(source)
        cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        for name,command in [('concise-runtime-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('build-concise-runtime',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-concise-runtime'])]:
            report['stage']=name;print(name,flush=True);result=timed_run(command);log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':result.returncode};report['steps'].append(step)
            if result.returncode:step['failure_log_tail']=log[-64000:]
            require(result.returncode==0,'Native command failed: '+name)
        binary=ROOT/'m2/concise-runtime/target/debug/studio-concise-runtime';report['binary_sha256']=sha(binary)
        report['stage']='full-python-oracle';print('Converting complete Concise workbook with captured Python',flush=True)
        oracle=out/'python-concise.txt';load_plugins()['moe_concise'].convert(str(source),str(oracle),'utf-8',lambda _:None,lambda _:None)
        expected=parse_txt(oracle.read_bytes());python_digest=record_digest(expected,'moe_concise');report['python_reference_observation']={'source_sha256':before,'raw_sha256':sha(oracle),'normalized_record_digest':python_digest,'file_bytes':oracle.stat().st_size}
        require(python_digest==ref['normalized_record_digest'] and oracle.stat().st_size==ref['expected_file_bytes'],'Mac Python differs beyond accepted reference-field set ordering')
        outputs=out/'outputs';outputs.mkdir();scratch=out/'private-rust';scratch.mkdir();active=Controller(binary,scratch,out/'controller.json');controller=active
        def idle():
            value=controller.call('admission');admission(value,0,0)
            require(value['shared']['active_operations']==0 and value['readers']['retained_reply_bytes']==value['readers']['retained_session_handles']==0,'Reservation or reply retention leak')
            require(not list(scratch.iterdir()),'Private input snapshot residue');return value
        def refuse(name,code,pre_cancel=False,**options):
            destination=outputs/(name+'.txt');req=request('moe_concise',source,destination,worksheet=ref['worksheet'],**options);jid=controller.call('publish',request=req,pre_cancel=pre_cancel)['job'];status=wait(controller,jid)
            require(status['state']==('cancelled' if pre_cancel else 'failed') and status['error']['code']==code and not status['error']['publication_uncertain'],'Wrong typed refusal: '+name)
            require(not destination.exists() and controller.call('publish_take',job=jid) is None,'Refused conversion published or retained a result');controller.call('publish_forget',job=jid)
            report['expected_failures'].append({'case':name,'request':req,'snapshot':status,'admission':idle()})
        report['stage']='geometry-refusals';print('Checking old geometry limits and invalid profile growth',flush=True)
        refuse('old-row-cap','limit_exceeded',tighten={'workbook_rows':32000})
        refuse('old-rectangle-cap','limit_exceeded',tighten={'workbook_cells':512000})
        refuse('cannot-grow-rows','invalid_input',tighten={'workbook_rows':50001})
        refuse('cannot-grow-cells','invalid_input',tighten={'workbook_cells':750001})
        refuse('pre-cancel','cancelled',pre_cancel=True)
        controller.call('publish',request=request('moe_revised',source,outputs/'wrong-converter.txt'),expect='invalid_input')
        require(not (outputs/'wrong-converter.txt').exists(),'Wrong converter published')
        report['stage']='full-concise';print('Converting all 45178 source rows with explicit native profile',flush=True)
        destination=outputs/'concise.txt';req=request('moe_concise',source,destination,worksheet=ref['worksheet']);jid=controller.call('publish',request=req)['job'];observations=[];status=wait(controller,jid,observations);require(status['state']=='succeeded','Full Concise native conversion failed');response=controller.call('publish_take',job=jid);require(response['kind']=='conversion','Wrong native receipt kind');receipt=response['receipt'];report['native_observation']={'snapshot':status,'receipt':receipt,'raw_sha256':sha(destination)}
        require(receipt=={'profile':'moe-concise-owned-v1','converter':'moe_concise','txt_profile':'canonical_v1','entries':ref['expected_entries'],'file_bytes':ref['expected_file_bytes'],'metrics':{'primary_entries':ref['expected_entries'],'alias_redirects':0,'traditional_entries':0,'skipped_rows_or_lines':0},'comments_count':0,'source_sha256':before},'Full Concise receipt differs')
        native_digest=compare_output(destination,expected,'moe_concise');report['native_observation']['normalized_record_digest']=native_digest;require(native_digest==ref['normalized_record_digest'],'Native output differs from independent full-source reference')
        require(controller.call('publish_take',job=jid) is None and controller.call('publish_cancel',job=jid)=='already_finished','Thin receipt transfer or late cancellation differs');controller.call('publish_forget',job=jid);after=idle()
        # An overwrite attempt must preserve the already-published complete file.
        preserved=sha(destination);overwrite=controller.call('publish',request=req)['job'];over_status=wait(controller,overwrite);require(over_status['state']=='failed' and over_status['error']['code']=='destination_exists' and not over_status['error']['publication_uncertain'],'Wrong overwrite refusal');require(controller.call('publish_take',job=overwrite) is None and sha(destination)==preserved,'Overwrite modified output');controller.call('publish_forget',job=overwrite);idle()
        report['expected_failures'].append({'case':'existing-output','snapshot':over_status,'output_sha256_preserved':preserved})
        report['checks'].append({'case':'full-official-concise','data_rows':ref['data_rows'],'source_sha256':before,'receipt':receipt,'success_snapshot':status,'normalized_record_digest':native_digest,'python_output_sha256':sha(oracle),'native_output_sha256':preserved,'raw_python_bytes_equal':preserved==sha(oracle),'active_admission_observations':observations,'after_conversion_admission':after})
        controller.call('shutdown');final=controller.call('admission');admission(final,0,0);require(final['shared']['closed'] and final['shared']['active_operations']==0,'Final admission cleanup differs');rss=controller.stop();active=None;report.update(final_admission=final,peak_RSS_bytes=rss,controller_transcript=controller.transcript)
        require(rss<=RSS_TARGET,'Observed full Concise RSS exceeds provisional 384 MiB threshold');require(sha(source)==before and not list(scratch.iterdir()),'Source changed or private snapshot leaked')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'] and check_lock()==report['dependency_packages'],'Sources or dependencies changed during probe')
        report['stage']='complete';report['status']='full_official_concise_passed_other_large_converters_and_closeout_pending'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'{type(error).__name__}: {error}';report['python_traceback']=traceback.format_exc()
        if isinstance(error,CommandTimeout):report['timed_out_command_output_tail']=error.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-concise-full-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_concise_full_failed')

if __name__=='__main__':raise SystemExit(main())
