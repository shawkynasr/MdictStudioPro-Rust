"""Full official Mini/Idioms comparison using unchanged qualified Rust limits.

Select the two eligible uploaded archives by exact name and SHA-256. Extract
only allowlisted source members into a new excluded output directory. Run only
the two complete datasets measured to fit the current native profile.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import traceback
import zipfile
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller
from m2_converter_runtime import admission,wait,request
from converter_runtime_lock import MANIFEST,LOCK,check_lock
from moe_fixtures import load_plugins

MEASUREMENTS='docs/evidence/official-converter-input-inspection/measurements.json'
def extract_sources(archives,destination,specs):
    destination.mkdir(exist_ok=False);result={}
    for spec in specs:
        path=archives/spec['archive'];require(path.is_file(),f'Missing selected archive: {path.name}');require(sha(path)==spec['archive_sha256'],f'Archive differs from uploaded inspected version: {path.name}')
        with zipfile.ZipFile(path) as z:
            info=z.getinfo(spec['member']);require(info.filename==Path(info.filename).name and '\\' not in info.filename and info.file_size==spec['source_bytes']<=64*1024*1024,'Unexpected source member or size');target=destination/info.filename
            with z.open(info) as source,target.open('xb') as out:shutil.copyfileobj(source,out,65536)
        require(sha(target)==spec['source_sha256'],'Extracted source identity differs');result[info.filename]=target
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archives',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-official-converters-out'),'Use m2-official-converters-out prefix for excluded private outputs');out.mkdir(exist_ok=False)
    report={'status':'m2_official_mini_idioms_failed','stage':'preflight','M2_complete':False,'all_six_real_converters_qualified':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[]}
    active=None
    try:
        measured=json.loads((ROOT/MEASUREMENTS).read_text());report['protected_source_sha256']=measured['protected_source_sha256'];report['source_sha256']={n:sha(ROOT/n) for n in ['scripts/m2_official_mini_idioms.py','scripts/test_official_converter_sources.py',MEASUREMENTS]};report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        for n,h in report['protected_source_sha256'].items():require(sha(ROOT/n)==h,'Qualified source changed: '+n)
        report['held_datasets']=[{'converter':c['converter'],'records':c['records'],'decoded_bytes':c['decoded_key_body_bytes'],'blockers':c['native_profile_blockers']} for c in measured['legacy_output_measurements'] if c['native_profile_blockers']]
        report['legacy_oracle_sha256']=measured['legacy_oracle_sha256']
        for n,h in report['legacy_oracle_sha256'].items():require(sha(ROOT/n)==h,'Original Python plugin changed: '+n)
        source_dir=out/'sources';eligible_members={c['input'] for c in measured['legacy_output_measurements'] if c['converter'] in ['moe_mini','moe_idioms']};sources=extract_sources(a.archives.resolve(),source_dir,[s for s in measured['archives'] if s['member'] in eligible_members]);cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac');report['stage']='build-qualified-runtime';print('Building unchanged qualified runtime',flush=True);cmd=[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-converter-runtime'];r=timed_run(cmd);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/'build-runtime.log').write_text(log);step={'name':'build-qualified-runtime','returncode':r.returncode};report['steps'].append(step)
        if r.returncode:step['failure_log_tail']=log[-64000:]
        require(r.returncode==0,'Qualified runtime build failed');binary=ROOT/'m2/converter-runtime/target/debug/studio-converter-runtime';report['binary_sha256']=sha(binary);outputs=out/'outputs';outputs.mkdir();oracles=out/'python-oracles';oracles.mkdir();scratch=out/'private-rust';scratch.mkdir()
        for kind in ['moe_mini','moe_idioms']:
            spec=next(c for c in measured['legacy_output_measurements'] if c['converter']==kind);source=sources[spec['input']];before=sha(source);report['active_case_observation']={'case':kind,'source_sha256':before};report['stage']=kind;print('Comparing full official dataset: '+kind,flush=True);python_output=oracles/(kind+'.txt');load_plugins()[kind].convert(str(source),str(python_output),'utf-8',lambda _:None,lambda _:None);report['active_case_observation']['python_output_sha256']=sha(python_output);require(sha(python_output)==spec['output_sha256'],'Mac original-Python output differs from full local reference');destination=outputs/(kind+'.txt');active=Controller(binary,scratch,out/(kind+'-controller.json'));c=active;req=request(kind,source,destination,worksheet=spec['worksheet']);jid=c.call('publish',request=req)['job'];observations=[];status=wait(c,jid,observations);require(status['state']=='succeeded','Full official native conversion failed');response=c.call('publish_take',job=jid);require(response['kind']=='conversion','Wrong official conversion response');receipt=response['receipt'];require(receipt['entries']==spec['records'] and receipt['file_bytes']==spec['file_bytes'] and receipt['source_sha256']==before and receipt['converter']==kind and receipt['profile']=='larger-owned-converters-v1' and receipt['txt_profile']=='canonical_v1' and receipt['comments_count']==0 and receipt['metrics']=={'primary_entries':spec['records'],'alias_redirects':0,'traditional_entries':0,'skipped_rows_or_lines':0},'Official native receipt differs');native_hash=sha(destination);report['active_case_observation'].update(native_output_sha256=native_hash,receipt=receipt,success_snapshot=status);require(native_hash==sha(python_output)==spec['output_sha256'],'Full official TXT bytes differ from original Python');require(c.call('publish_take',job=jid) is None and c.call('publish_cancel',job=jid)=='already_finished','Receipt transfer or late cancellation differs');c.call('publish_forget',job=jid);idle=c.call('admission');admission(idle,0,0);require(idle['shared']['active_operations']==0 and idle['readers']['retained_reply_bytes']==idle['readers']['retained_session_handles']==0,'Official runtime reservation/retention leak');c.call('shutdown');final=c.call('admission');admission(final,0,0);require(final['shared']['closed'],'Shared admission not closed');rss=c.stop();active=None;require(rss<=RSS_TARGET,'Official source RSS exceeds provisional 384 MiB threshold');require(sha(source)==before and not list(scratch.iterdir()),'Source changed or private native residue');report['checks'].append({'case':kind,'status':'full_official_source_exact_python_parity_passed','source_sha256':before,'data_rows':spec['data_rows'],'receipt':receipt,'success_snapshot':status,'python_output_sha256':sha(python_output),'native_output_sha256':native_hash,'reference_output_sha256':spec['output_sha256'],'active_admission_observations':observations,'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript})
        for n,h in report['protected_source_sha256'].items():require(sha(ROOT/n)==h,'Qualified source changed during full-source probe')
        require(all(sha(ROOT/n)==h for n,h in report['source_sha256'].items()) and sha(ROOT/LOCK)==report['dependency_lock_sha256'],'Probe sources/lock changed');check_lock();report['stage']='complete';report['status']='full_official_mini_idioms_passed_other_real_converters_need_scaling'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-official-converters-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_official_mini_idioms_failed')
if __name__=='__main__':raise SystemExit(main())
