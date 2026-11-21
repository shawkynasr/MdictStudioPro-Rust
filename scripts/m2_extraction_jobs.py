"""Qualify background extraction and shared reader/extractor resource admission."""
import argparse
import json
import os
from pathlib import Path
import shutil
import traceback
import time
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller,review_page
from m2_stream_extract import compare,tree
from extraction_jobs_lock import MANIFEST,LOCK,check_lock
from stream_mdd_fixtures import write
from index_fixtures import make
from bounded_fixtures import mutate

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-stream-extract-user-run/m2-stream-extract-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previous qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/extraction-jobs';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['extraction_jobs_lock.py','m2_extraction_jobs.py','test_m2_extraction_jobs.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def admission(value,readers=None,extractions=None):
    s=value['shared'];r=value['readers'];require(s['active_operations']==s['readers']+s['extractions']<=s['max_operations']<=2,'Active operation accounting differs');require(s['reserved_memory_bytes']==s['active_operations']*96*1024*1024<=s['memory_cap']<=192*1024*1024,'Shared memory accounting differs');require(s['reserved_temporary_bytes']==s['readers']*768*1024*1024+s['extractions']*3*1024*1024*1024<=s['temporary_cap']<=4*1024*1024*1024,'Shared temporary accounting differs')
    if readers is not None:require(s['readers']==readers,'Shared reader lease count differs')
    if extractions is not None:require(s['extractions']==extractions,'Shared extraction lease count differs')
    require(r['live_sessions']<=2 and r['retained_reply_bytes']<=r['retained_reply_cap']==8*1024*1024,'Accepted reader-pool caps differ')
def wait_extract(controller,job):
    deadline=time.monotonic()+300
    while True:
        status=controller.call('extract_job',job=job)
        if status['state'] in ['succeeded','failed','cancelled']:return status
        require(time.monotonic()<deadline,'Background extraction exceeded 300 seconds')
        time.sleep(0.1)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_extraction_jobs_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'scope':'one runtime sharing active reservations between managed persistent readers and serial extraction publication jobs; earlier packing/converter runners remain separate'};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Require Rust-enabled Mac')
        def run(name,cmd):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(cmd);step={'name':name,'returncode':r.returncode};report['steps'].append(step);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        run('refresh-extraction-jobs',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-extraction-jobs'])
        try:run('extraction-job-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        run('build-extraction-jobs',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-extraction-jobs','--bin','studio-extraction-jobs'])
        run('build-index-seed',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine'])
        binary=ROOT/'m2/extraction-jobs/target/debug/studio-extraction-jobs';builder=ROOT/'m2/extraction-jobs/target/debug/studio-indexed-engine';report['binary_sha256']=sha(binary);report['index_builder_binary_sha256']=sha(builder)
        inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();scratch=out/'private-scratch';scratch.mkdir();reader=make(inputs/'reader.mdx',strip=True);cache=inputs/'reader.idx';seed=out/'seed-index.json';seed.write_text(json.dumps({'path':str(reader['path']),'kind':'mdx','artifact':str(cache),'policy':'header_ascii_v1','action':'build','queries':[]}));run('seed-reader-index',[str(builder),str(seed)])
        spec={'source':str(reader['path']),'artifact':str(cache),'kind':'mdx','policy':'header_ascii_v1'};reader_hash=sha(reader['path']);cache_hash=sha(cache)
        fixtures=[]
        for name,recipes in [('cross-block',[{'key':'data.bin','bytes':200000,'seed':4},{'key':'empty.bin','bytes':0}]),('large-resource',[{'key':'prefix.bin','bytes':17,'seed':11},{'key':'assets/字-مرحبا-𠀀.bin','bytes':32*1024*1024+7,'seed':37},{'key':'empty.bin','bytes':0}]),('many-files',[{'key':f'files/f{i:05d}.bin','bytes':256,'seed':i} for i in range(4096)])]:
            print(f'Preparing {name}',flush=True);f=write(inputs/(name+'.mdd'),recipes);fixtures.append((name,f))
        unsafe=write(inputs/'unsafe.mdd',[{'key':'../escape','bytes':3}]);bad_path=mutate(fixtures[0][1]['path'],inputs/'bad-checksum.mdd','record_block_checksum')
        for name,f in fixtures:
            report['stage']=name;print(f'Checking background/shared admission: {name}',flush=True);active=Controller(binary,scratch,out/(name+'-controller.json'));c=active;source_hash=sha(f['path']);destination=outputs/name;before=set(outputs.iterdir());page_replies=[]
            def open_reader():
                opened=c.call('open',request=spec);require(c.call('wait',session=opened['session'],job=opened['job'])['state']=='succeeded','Managed reader failed');require(c.call('take',session=opened['session'],job=opened['job'])['operation']=='opened','Managed reader manifest missing');c.call('forget',session=opened['session'],job=opened['job']);return opened['session']
            first=open_reader();second=open_reader();full=c.call('admission');admission(full,2,0)
            blocked=outputs/(name+'-blocked');jid=c.call('extract',request={'source':str(f['path']),'destination':str(blocked)})['job'];s=wait_extract(c,jid);require(s['state']=='failed' and s['error']['code']=='limit_exceeded' and s['error']['detail']=='resource_admission' and not s['error']['publication_uncertain'],'Busy readers did not stop extraction before I/O');require(not blocked.exists(),'Admission failure published output');require(c.call('extract_take',job=jid) is None,'Admission failure retained receipt');c.call('extract_forget',job=jid)
            c.call('close',session=second);require(c.call('wait_closed',session=second)['closed'],'Managed cleanup barrier failed');c.call('release',session=second);freed=c.call('admission');admission(freed,1,0)
            jid=c.call('extract',request={'source':str(f['path']),'destination':str(destination)})['job'];overlap=c.call('admission');admission(overlap)
            request={'query':'apple','offset':1,'limit':1};page=c.call('submit',session=first,request=request)['job'];require(c.call('wait',session=first,job=page)['state']=='succeeded','Page while extraction active failed');reply=c.call('take',session=first,job=page);review_page(reply,reader,'apple',1,1,'header_ascii_v1');page_replies.append(reply);c.call('forget',session=first,job=page)
            status=wait_extract(c,jid);require(status['state']=='succeeded' and status['result_available'],'Background extraction failed');receipt=c.call('extract_take',job=jid);files=compare(receipt,f,destination);require(c.call('extract_take',job=jid) is None,'Receipt transferred twice');require(c.call('extract_cancel',job=jid)=='already_finished','Late cancel changed publication result');c.call('extract_forget',job=jid);after_success=c.call('admission');admission(after_success,1,0)
            failure_statuses=[]
            for label,source,code,existing in [('unsafe',unsafe['path'],'unsafe_path',False),('checksum',bad_path,'integrity',False),('existing',f['path'],'destination_exists',True)]:
                dst=outputs/(name+'-'+label)
                if existing:dst.mkdir();(dst/'sentinel').write_bytes(b'keep')
                old=tree(dst) if dst.exists() else None;before_failure=set(outputs.iterdir());job=c.call('extract',request={'source':str(source),'destination':str(dst)})['job'];s=wait_extract(c,job);require(s['state']=='failed' and s['error']['code']==code and not s['error']['publication_uncertain'],'Typed extraction failure changed');require(c.call('extract_take',job=job) is None,'Failed job retained success');c.call('extract_forget',job=job);require(set(outputs.iterdir())==before_failure and (tree(dst) if dst.exists() else None)==old,'Failed job changed existing output or left staging');failure_statuses.append(s)
            held=[]
            for i in range(8):
                job=c.call('extract',request={'source':str(f['path']),'destination':str(outputs/(name+f'-cancel-{i}'))},pre_cancel=True)['job'];s=wait_extract(c,job);require(s['state']=='cancelled' and s['cancel_requested'] and not s['error']['publication_uncertain'],'Precancelled extraction ran');held.append(job)
            c.call('extract',request={'source':str(f['path']),'destination':str(outputs/(name+'-retention'))},expect='retention_full');events=c.call('extract_events');require(len(events)<=8,'Unbounded extraction event queue')
            for job in held:c.call('extract_forget',job=job)
            c.call('close',session=first);require(c.call('wait_closed',session=first)['closed'],'Last reader cleanup failed');c.call('release',session=first);idle=c.call('admission');admission(idle,0,0);require(idle['readers']['retained_reply_bytes']==idle['readers']['retained_session_handles']==0,'Reader metadata/replies leaked');c.call('shutdown');c.call('extract',request={'source':str(f['path']),'destination':str(outputs/(name+'-closed'))},expect='closed');c.call('open',request=spec,expect='closed');final=c.call('admission');admission(final,0,0);require(final['shared']['closed'],'Shared admission not closed')
            rss=c.stop();active=None;require(rss<=RSS_TARGET,'Runtime observed RSS exceeded provisional threshold');require(not list(scratch.iterdir()),'Private input/cache snapshot residue');require(sha(f['path'])==source_hash and sha(reader['path'])==reader_hash and sha(cache)==cache_hash,'Background runtime changed input/cache bytes');require(set(outputs.iterdir())==before|{destination,outputs/(name+'-existing')},'Unexpected output or staging residue')
            report['checks'].append({'case':name,'status':'background_extraction_and_shared_admission_passed','source_sha256':source_hash,'files':files,'receipt':receipt,'success_snapshot':status,'typed_failures':failure_statuses,'reader_page_replies':page_replies,'two_reader_admission':full,'after_reader_release':freed,'overlap_observation':overlap,'after_publication':after_success,'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during background qualification');check_lock();report['stage']='complete';report['status']='m2_background_extraction_shared_admission_passed_larger_paths_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-extraction-jobs-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_extraction_jobs_failed')
if __name__=='__main__':raise SystemExit(main())
