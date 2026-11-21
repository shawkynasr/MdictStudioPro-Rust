"""Full Revised/WFG grouping, existing layouts and bounded TXT publication gate."""
import argparse
import json
import os
import platform
import shutil
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,CommandTimeout
from m2_official_mini_idioms import extract_sources
from moe_fixtures import load_plugins
from xlsx_spool_oracle import inspect
from revised_render_oracle import records,record_summary,compare_files
from revised_render_lock import MANIFEST,LOCK,check_lock
REFERENCE='docs/evidence/revised-render-source-reference/reference.json'
RSS_TARGET=256*1024*1024
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-xlsx-spool-user-run/m2-xlsx-spool-report.json').read_text());result={**r['protected_source_sha256'],**r['source_sha256']}
    require(len(result)==253,'Protected source inventory differs')
    for name,h in result.items():require(sha(ROOT/name)==h,'Qualified source changed: '+name)
    require('m2/xlsx-reader/src/moe/text.rs' in result,'Shared layout validator not source-bound')
    return result
def fingerprints():
    paths=[p for p in (ROOT/'m2/revised-render').rglob('*') if p.is_file() and 'target' not in p.parts]
    paths += [ROOT/n for n in ['scripts/m2_revised_render.py','scripts/revised_render_lock.py','scripts/revised_render_oracle.py','scripts/test_revised_render.py',REFERENCE]]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archives',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();require(out.name.startswith('m2-revised-render-out'),'Use m2-revised-render-out prefix for private output exclusion');out.mkdir(exist_ok=False)
    report={'status':'m2_revised_render_failed','stage':'preflight','M2_complete':False,'application_background_integration_qualified':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'build_profile':'release_for_process_cases_debug_for_tests','RSS_is_OS_limit':False,'RSS_observation_target_bytes':RSS_TARGET}
    try:
        ref=json.loads((ROOT/REFERENCE).read_text());report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['legacy_oracle_sha256']=ref['legacy_oracle_sha256']
        for name,h in report['legacy_oracle_sha256'].items():require(sha(ROOT/name)==h,'Captured original Python code changed')
        report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        sources=extract_sources(args.archives.resolve(),out/'sources',[ref['archive']]);source=sources[ref['archive']['member']];before=sha(source);cargo=shutil.which('cargo');require(cargo is not None,'Run this gate on the Rust-enabled Mac')
        for name,cmd in [('grouped-render-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('build-release-grouped-render',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-revised-render'])]:
            report['stage']=name;print(name,flush=True);result=timed_run(cmd);log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':result.returncode};report['steps'].append(step)
            if result.returncode:step['failure_log_tail']=log[-64000:]
            require(result.returncode==0,'Native command failed: '+name)
        binary=ROOT/'m2/revised-render/target/release/studio-revised-render';report['binary_sha256']=sha(binary);outputs=out/'outputs';outputs.mkdir();requests=out/'requests';requests.mkdir();scratch=out/'private-rust';scratch.mkdir();oracles=out/'python-oracles';oracles.mkdir();env=dict(os.environ);env.update(TMPDIR=str(scratch),LC_ALL='C');system=platform.system()
        def run(name,path,kind,destination=None,worksheet=None,code=None,**options):
            destination=destination or outputs/(name+'.txt');request={'source':str(path),'destination':str(destination),'converter':kind,'worksheet':worksheet,**options};request_path=requests/(name+'.json');request_path.write_text(json.dumps(request,ensure_ascii=False)+'\n');old_names={p.name for p in outputs.iterdir()};old_hash=sha(destination) if destination.exists() else None;report['stage']=name;print(name,flush=True)
            result=timed_run(['/usr/bin/time','-l' if system=='Darwin' else '-v',str(binary),str(request_path)],env=env);(out/(name+'.stdout')).write_text(result.stdout);(out/(name+'.stderr')).write_text(result.stderr)
            try:reply=json.loads(result.stdout)
            except Exception:report['invalid_native_response']={'case':name,'stdout_tail':result.stdout[-64000:],'stderr_tail':result.stderr[-64000:]};raise
            rss=peak_rss(result.stderr,system);check={'case':name,'request':request,'returncode':result.returncode,'reply':reply,'peak_RSS_bytes':rss};report['checks'].append(check);require(rss<=RSS_TARGET,'Native renderer exceeds provisional 256 MiB observation target');require(not list(scratch.iterdir()),'Private row-spool residue')
            if code:
                require(result.returncode==1 and reply['status']=='failed' and reply['error']['code']==code,'Unexpected rendering refusal: '+name);require({p.name for p in outputs.iterdir()}==old_names and (sha(destination) if destination.exists() else None)==old_hash,'Refused conversion changed outputs')
                if old_hash:check['existing_output_sha256_preserved']=old_hash
            else:
                require(result.returncode==0 and reply['status']=='succeeded' and destination.is_file(),'Rendering did not publish: '+name);require({p.name for p in outputs.iterdir()}==old_names|{destination.name},'Unexpected private output residue');receipt=reply['receipt'];check['output_sha256']=sha(destination)
                require(receipt['profile']=='moe-grouped-disk-rows-txt-v1' and receipt['converter']==kind and receipt['file_sha256']==check['output_sha256'] and receipt['file_bytes']==destination.stat().st_size and receipt['source_sha256']==sha(path),'Renderer receipt identity/extent differs')
                raw=record_summary(destination,kind);check['raw_record_digest']=raw;require(raw=={'records':receipt['entries'],'key_bytes':receipt['key_bytes'],'payload_bytes':receipt['body_bytes'],'framed_records_sha256':receipt['framed_records_sha256']} and receipt['decoded_bytes']==raw['key_bytes']+raw['payload_bytes'],'Strict reopen/raw digest differs')
                require(receipt['entries']==receipt['primary_entries']+receipt['alias_redirects'] and receipt['groups']==receipt['primary_entries'] and receipt['index_charge_bytes']<=64*1024*1024 and receipt['largest_group_rows']<=4096 and receipt['largest_group_input_bytes']<=16*1024*1024 and receipt['temporary_file_peak_bytes']<=512*1024*1024,'Group/output bounds differ')
            return check,destination
        def compare(check,path,oracle,kind):
            count=compare_files(path,oracle,kind);normalized=record_summary(path,kind,True);expected=record_summary(oracle,kind,True);require(normalized==expected and count==normalized['records'],'Complete normalized output differs from captured Python');check.update(python_output_sha256=sha(oracle),normalized_record_digest=normalized,raw_python_bytes_equal=sha(path)==sha(oracle),records_compared=count)
            if kind=='moe_revised_wfg':require(check['raw_python_bytes_equal'],'WFG raw bytes differ')
        small=ROOT/'m2/revised-render/tests/fixtures/groups.xlsx';small_rows=inspect(small);small_oracles={}
        for kind in ['moe_revised','moe_revised_wfg']:
            oracle=oracles/(kind+'-small.txt');load_plugins()[kind].convert(str(small),str(oracle),'utf-8',lambda _:None,lambda _:None);small_oracles[kind]=oracle;check,path=run('small-'+kind,small,kind);compare(check,path,oracle,kind);require(check['reply']['receipt']['row_source']['row_digest']==small_rows['row_digest'],'Small normalized source rows differ')
            for phase in ['index_rows','render_group','append_record','verify_output','before_publish']:run(kind+'-cancel-'+phase,small,kind,code='cancelled',cancel_phase=phase)
            check,path=run(kind+'-late-cancel',small,kind,cancel_phase='published');require(check['reply']['late_cancel_observed'],'Postcommit cancellation not observed');compare(check,path,oracle,kind)
            for name,options in [('group-rows',{'group_rows':1}),('index-charge',{'index_charge_bytes':1}),('entries',{'entries':1}),('file-bytes',{'output_bytes':4})]:run(kind+'-lower-'+name,small,kind,code='limit_exceeded',tighten=options)
        run('unknown-converter',small,'moe_mini',code='invalid_input');run('cannot-grow-entries',small,'moe_revised',code='invalid_input',tighten={'entries':200001});run('cannot-grow-reader',small,'moe_revised',code='invalid_input',reader_tighten={'rows':200001});run('missing-sheet',small,'moe_revised',worksheet='missing',code='sheet_not_found')
        row_ref=json.loads((ROOT/'docs/evidence/revised-row-source-reference/reference.json').read_text())['expected']
        for kind in ['moe_revised','moe_revised_wfg']:
            report['stage']='full-python-'+kind;print('Complete original Python conversion: '+kind,flush=True);oracle=oracles/(kind+'-full.txt');load_plugins()[kind].convert(str(source),str(oracle),'utf-8',lambda _:None,lambda _:None);expected=record_summary(oracle,kind,True);require(expected==ref['cases'][kind]['normalized_record_digest'],'Full Mac Python differs beyond accepted set ordering')
            check,path=run('full-'+kind,source,kind,worksheet=ref['worksheet']);compare(check,path,oracle,kind);receipt=check['reply']['receipt'];expected=ref['cases'][kind]
            require(receipt['entries']==expected['entries'] and receipt['primary_entries']==expected['primary_entries'] and receipt['alias_redirects']==expected['alias_redirects'] and receipt['file_bytes']==expected['file_bytes'] and receipt['input_rows']==163909 and receipt['skipped_rows']==0 and receipt['row_source']['row_digest']==row_ref['row_digest'] and check['normalized_record_digest']==expected['normalized_record_digest'],'Full renderer source/count/content differs')
            if kind=='moe_revised_wfg':require(sha(path)==expected['raw_python_output_sha256'],'Full WFG bytes differ from independent local Python reference')
            run(kind+'-existing-output',source,kind,destination=path,worksheet=ref['worksheet'],code='destination_exists')
        require(sha(source)==before and protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'] and check_lock()==report['dependency_packages'],'Source or dependency identities changed');report['stage']='complete';report['status']='full_Revised_and_WFG_grouped_TXT_publication_passed_application_integration_pending'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'{type(error).__name__}: {error}';report['python_traceback']=traceback.format_exc()
        if isinstance(error,CommandTimeout):report['timed_out_command_output_tail']=error.output_tail
    path=out/'m2-revised-render-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_revised_render_failed')
if __name__=='__main__':raise SystemExit(main())
