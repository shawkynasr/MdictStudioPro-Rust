"""Real bounded repacking and exclusive shared index-build qualification.

CC-CEDICT MDX remains outside current packing caps; test its typed refusal and
index its complete original source. No partial dataset is presented as full.
"""
import argparse
import json
import os
import platform
import shutil
import time
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,RSS_TARGET,CommandTimeout
from m2_sessions import Controller
from m2_real_readers import catalog,wait_reader
from real_publication_oracle import prepare,verify_output
from real_publication_lock import MANIFEST,LOCK,check_lock
ACCEPTED='docs/evidence/m2-full-converters-user-run/m2-full-converters-report.json'
REAL='docs/evidence/m2-real-readers-user-run/m2-real-readers-report.json'
REFERENCE='docs/evidence/real-publication-preflight/reference.json'
def protected_sources():
    r=json.loads((ROOT/ACCEPTED).read_text());expected={**r['protected_source_sha256'],**r['source_sha256']};require(len(expected)==282,'Accepted inventory differs')
    for n,h in expected.items():require(sha(ROOT/n)==h,'Qualified source changed: '+n)
    return expected
def fingerprints():
    paths=[p for p in (ROOT/'m2/real-publication-runtime').rglob('*') if p.is_file() and 'target' not in p.parts]
    paths += [ROOT/'scripts'/n for n in ['m2_real_publication.py','real_publication_lock.py','real_publication_oracle.py','test_real_publication.py']]
    paths.append(ROOT/REFERENCE)
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def admission(v):
    s=v['shared'];r=v['readers'];unit=1024**2;weights={'readers':(96,768),'extractions':(96,3072),'packings':(192,768),'exports':(96,768),'conversions':(384,768),'index_builds':(384,3072)}
    require(s['memory_cap']==384*unit and s['temporary_cap']==4096*unit and s['max_operations']==2,'Shared cap differs')
    require(all(type(s[k]) is int and s[k]>=0 for k in weights),'Invalid counters');require(s['active_operations']==sum(s[k] for k in weights)<=2,'Operation count differs')
    require(s['reserved_memory_bytes']==sum(s[k]*w[0]*unit for k,w in weights.items())<=384*unit and s['reserved_temporary_bytes']==sum(s[k]*w[1]*unit for k,w in weights.items())<=4096*unit,'Incorrect charge or forbidden overlap')
    require(0<=r['retained_reply_bytes']<=r['retained_reply_cap']==8*unit,'Reader retention differs');return v
def wait(c,jid,observations=None):
    deadline=time.monotonic()+300
    while True:
        s=c.call('publish_job',job=jid);v=admission(c.call('admission'))
        if observations is not None and (not observations or observations[-1]!=v):observations.append(v)
        if s['state'] in ['succeeded','failed','cancelled']:return s
        require(time.monotonic()<deadline,'Job exceeded 300 seconds');time.sleep(.05)
def index_request(source,destination,kind):return {'kind':'index','request':{'source':str(source),'destination':str(destination),'kind':kind,'policy':'raw_exact'}}
def pack_request(source,destination,kind,meta,resources,encoding='utf8'):
    req={'operation':'pack_'+kind,'source':str(source),'destination':str(destination),'metadata':meta}
    if kind=='mdx':req['encoding']=encoding
    else:req['resource_root']=str(resources)
    return {'kind':'dictionary','request':req}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-real-publication-out'),'Use m2-real-publication-out prefix for private exclusions');out.mkdir(exist_ok=False)
    report={'status':'m2_real_publication_failed','stage':'preflight','M2_complete':False,'scope':'three complete bounded real dictionaries repacked; full CC-CEDICT packing refusal; all four original dictionaries indexed with shared admission','RSS_is_OS_limit':False,'steps':[],'checks':[]};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK);cases=catalog(a.inputs);old={c['case']:c for c in json.loads((ROOT/REAL).read_text())['checks']};require({c['id'] for c in cases}==set(old),'Require exact four previously qualified selections');cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        for c in cases:require(c['source'].is_file() and sha(c['source'])==old[c['id']]['source_sha256'],'Selected original dictionary differs: '+c['source'].name)
        for name,command in [('native-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('release-runtime',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-real-publication-runtime']),('release-index-verifier',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine'])]:
            report['stage']=name;print(name,flush=True);v=timed_run(command);log=v.stdout+'\nSTDERR:\n'+v.stderr;(out/(name+'.log')).write_text(log);report['steps'].append({'name':name,'returncode':v.returncode,'log_tail':log[-64000:]});require(v.returncode==0,'Native command failed: '+name)
        binary=ROOT/'m2/real-publication-runtime/target/release/studio-real-publication-runtime';verifier=binary.with_name('studio-indexed-engine');report['binary_sha256']=sha(binary);report['verifier_sha256']=sha(verifier)
        outputs=out/'outputs';outputs.mkdir()
        for case in cases:
            cid=case['id'];source=case['source'];kind=case['kind'];report['stage']=cid;print('Real packing/index qualification: '+source.name,flush=True);directory=outputs/cid;directory.mkdir();oracle_scratch=directory/'oracle-scratch';oracle_scratch.mkdir();scratch=directory/'native-scratch';scratch.mkdir();before=sha(source)
            inventory,manifest,resources=prepare(source,kind,directory/'prepared');require(inventory==json.loads((ROOT/REFERENCE).read_text())[cid],'Independent preparation differs from complete local preflight');require(inventory['records']==old[cid]['independent_scan']['records'] and inventory['key_bytes']==old[cid]['independent_scan']['key_bytes'] and inventory['decoded_bytes']==inventory['key_bytes']+old[cid]['independent_scan']['payload_bytes'],'Independent source inventory differs from accepted scan');report['active_case_observation']={'case':cid,'inventory':inventory}
            active=Controller(binary,scratch,out/(cid+'-controller.json'));c=active
            def publication(req,code=None,pre_cancel=False):
                jid=c.call('publish',request=req,pre_cancel=pre_cancel)['job'];observations=[];status=wait(c,jid,observations);reply=c.call('publish_take',job=jid)
                result={'request':req,'snapshot':status,'receipt':reply,'admission_observations':observations}
                if code:
                    require(status['state']==('cancelled' if pre_cancel else 'failed') and status['error']['code']==code and not status['error']['publication_uncertain'] and reply is None,'Wrong typed publication refusal')
                else:
                    require(status['state']=='succeeded' and reply is not None,'Publication failed: '+json.dumps(status));require(c.call('publish_take',job=jid) is None and c.call('publish_cancel',job=jid)=='already_finished','Result transfer or late cancellation differs')
                c.call('publish_forget',job=jid);return result
            cache=directory/'original.idx';index=publication(index_request(source,cache,kind));receipt=index['receipt'];require(receipt['kind']=='index' and receipt['receipt']['manifest']['source_sha256']==before and receipt['receipt']['manifest']['records']==inventory['records'] and receipt['receipt']['manifest']['policy']=='raw_exact' and len(json.dumps(receipt).encode())<=4096,'Index source/count/profile differs');cache_hash=sha(cache)
            opened=c.call('open',request={'source':str(source),'artifact':str(cache),'kind':kind,'policy':'raw_exact'});sid=opened['session'];require(wait_reader(c,sid,opened['job'])['state']=='succeeded','Managed source reader failed');opened_manifest=c.call('take',session=sid,job=opened['job']);c.call('forget',session=sid,job=opened['job']);require(opened_manifest['operation']=='opened' and opened_manifest['value']['source_sha256']==before,'Reader cache identity differs')
            blocked_target=directory/'reader-blocked.idx';blocked=publication(index_request(source,blocked_target,kind),'limit_exceeded');require(blocked['snapshot']['error']['detail']=='resource_admission' and not blocked_target.exists(),'Index ran while a reader held capacity')
            packed=[];held=None
            for enc in (['utf8','utf16'] if kind=='mdx' else ['binary']):
                destination=directory/('packed-'+enc+'.'+kind);req=pack_request(manifest,destination,kind,inventory['metadata'],resources,enc)
                if inventory['packing_blockers']:
                    held=publication(req,'limit_exceeded');require(not destination.exists(),'Blocked full source was published');break
                result=publication(req);summary=result['receipt'];require(summary['kind']=='dictionary','Wrong packing result');summary=summary['receipt'];require(summary['source_sha256']==inventory['manifest_sha256'],'Packing snapshot identity differs');wire=verify_output(destination,kind,inventory['expected_sorted_records'],inventory['metadata'],oracle_scratch);require(all(summary[k]==v for k,v in wire['records'].items()) and summary['file_bytes']==wire['file_bytes'] and summary['metadata']==wire['metadata'],'Packing receipt differs from complete independent output scan');preserved=sha(destination);overwrite=publication(req,'destination_exists');require(sha(destination)==preserved,'Packing overwrite changed output');packed.append({'encoding':enc,'publication':result,'wire_verification':wire,'overwrite_refusal':overwrite})
            c.call('close',session=sid);require(c.call('wait_closed',session=sid)['closed'],'Reader cleanup barrier failed');c.call('release',session=sid)
            overwrite_index=publication(index_request(source,cache,kind),'destination_exists');require(sha(cache)==cache_hash,'Index overwrite changed cache');cancel_target=directory/'pre-cancel.idx';pre_cancel=publication(index_request(source,cancel_target,kind),'cancelled',pre_cancel=True);require(not cancel_target.exists(),'Pre-cancelled cache published');require(len(c.call('publish_events'))<=8,'Unbounded retained progress')
            c.call('shutdown');c.call('publish',request=index_request(source,directory/'closed.idx',kind),expect='closed');final=admission(c.call('admission'));require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final reservation/retention leak');rss=c.stop();active=None;report['active_case_observation'].update(peak_RSS_bytes=rss,controller_transcript=c.transcript);require(rss<=RSS_TARGET,'Runtime RSS exceeds provisional 384 MiB target');require(not list(scratch.iterdir()) and not list(oracle_scratch.iterdir()) and sha(source)==before and sha(cache)==cache_hash,'Source/cache changed or scratch leaked')
            # Strictly reopen the managed cache in a separate accepted verifier;
            # query list is empty, so no definition bodies enter the report.
            q=directory/'verify-index-request.json';q.write_text(json.dumps({'path':str(source),'artifact':str(cache),'kind':kind,'policy':'raw_exact','action':'query','queries':[]})+'\n');env=dict(os.environ,TMPDIR=str(scratch));v=timed_run(['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v',str(verifier),str(q)],env=env);(directory/'verify-index.stdout').write_text(v.stdout);(directory/'verify-index.stderr').write_text(v.stderr);verified=json.loads(v.stdout);verify_rss=peak_rss(v.stderr,platform.system());report['active_case_observation'].update(index_verifier_returncode=v.returncode,index_verifier_reply=verified,index_verifier_peak_RSS_bytes=verify_rss);require(v.returncode==0 and verified['status']=='queried' and verified['scan']==old[cid]['independent_scan'] and verified['manifest']==receipt['receipt']['manifest'],'Complete strict source/cache reopen differs');require(verify_rss<=RSS_TARGET and verified['memory']['locator']==0 and not list(scratch.iterdir()),'Verifier RSS, locator or scratch differs')
            shutil.rmtree(directory/'prepared');report['checks'].append({'case':cid,'inventory':inventory,'index_publication':index,'reader_contention_refusal':blocked,'packing':packed,'packing_refusal':held,'index_overwrite_refusal':overwrite_index,'pre_cancelled_index':pre_cancel,'final_admission':final,'peak_RSS_bytes':rss,'index_verifier_peak_RSS_bytes':verify_rss,'index_verifier_reply':verified,'index_sha256':cache_hash,'controller_transcript':c.transcript});report.pop('active_case_observation',None)
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during qualification');check_lock();report['stage']='complete';report['status']='bounded_real_packing_and_exclusive_index_admission_passed_CC_packing_and_closeout_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-real-publication-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_real_publication_failed')
if __name__=='__main__':raise SystemExit(main())
