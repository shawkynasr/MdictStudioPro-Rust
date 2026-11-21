"""Complete CC-CEDICT packing with block spools and exclusive shared admission."""
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
from m2_real_readers import wait_reader
from m2_real_publication import index_request
from real_publication_oracle import verify_output
from cc_pack_oracle import prepare_cc
from cc_pack_lock import MANIFEST,LOCK,check_lock
REFERENCE='docs/evidence/cc-pack-source-reference/reference.json'
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-real-publication-user-run/m2-real-publication-report.json').read_text());p={**r['protected_source_sha256'],**r['source_sha256']};require(len(p)==300,'Accepted identity inventory differs')
    for n,h in p.items():require(sha(ROOT/n)==h,'Qualified source changed: '+n)
    return p
def fingerprints():
    paths=[p for d in ['m2/cc-pack-io','m2/cc-pack-runtime'] for p in (ROOT/d).rglob('*') if p.is_file() and 'target' not in p.parts]
    paths += [ROOT/'scripts'/n for n in ['m2_cc_pack.py','cc_pack_oracle.py','cc_pack_lock.py','test_cc_pack.py']]+[ROOT/REFERENCE]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def request(source,destination,encoding,metadata,**options):return {'kind':'cc_packing','request':{'source':str(source),'destination':str(destination),'encoding':encoding,'metadata':metadata,**options}}
def admission(v):
    s=v['shared'];r=v['readers'];unit=1024**2;weights={'readers':(96,768),'extractions':(96,3072),'packings':(192,768),'exports':(96,768),'conversions':(384,768),'index_builds':(384,3072),'cc_packings':(384,3072)}
    require(s['memory_cap']==384*unit and s['temporary_cap']==4096*unit and s['max_operations']==2,'Shared ceiling differs');require(all(type(s[k]) is int and s[k]>=0 for k in weights),'Invalid operation counts')
    require(s['active_operations']==sum(s[k] for k in weights)<=2 and s['reserved_memory_bytes']==sum(s[k]*w[0]*unit for k,w in weights.items())<=384*unit and s['reserved_temporary_bytes']==sum(s[k]*w[1]*unit for k,w in weights.items())<=4096*unit,'Reservation charges or exclusive overlap differ')
    require(0<=r['retained_reply_bytes']<=r['retained_reply_cap']==8*unit,'Reader retention differs');return v
def wait(c,jid,observations):
    deadline=time.monotonic()+300
    while True:
        s=c.call('publish_job',job=jid);v=admission(c.call('admission'))
        if not observations or observations[-1]!=v:observations.append(v)
        if s['state'] in ['succeeded','failed','cancelled']:return s
        require(time.monotonic()<deadline,'Packing/index job exceeded 300 seconds');time.sleep(.05)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-cc-pack-out'),'Use m2-cc-pack-out prefix for private exclusions');out.mkdir(exist_ok=False)
    report={'status':'m2_cc_pack_failed','stage':'preflight','M2_complete':False,'RSS_is_OS_limit':False,'scope':'complete previously selected 202884-entry CC-CEDICT MDX packing in UTF-8 and UTF-16; unchanged old packing profile','steps':[],'checks':[],'expected_failures':[]};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK);ref=json.loads((ROOT/REFERENCE).read_text());source=(a.inputs/'CC-CEDICT 092026.mdx').resolve();require(source.is_file() and sha(source)==ref['inventory']['source_sha256'],'Require exact previously selected CC-CEDICT 092026.mdx')
        cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        for name,command in [('block-writer-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-cc-pack-io']),('runtime-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('release-runtime',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-cc-pack-runtime']),('release-index-verifier',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine'])]:
            report['stage']=name;print(name,flush=True);v=timed_run(command);log=v.stdout+'\nSTDERR:\n'+v.stderr;(out/(name+'.log')).write_text(log);report['steps'].append({'name':name,'returncode':v.returncode,'log_tail':log[-64000:]});require(v.returncode==0,'Native command failed: '+name)
        report['stage']='complete-independent-source-preparation';print('Preparing all 202884 records and frozen-sort scan',flush=True);inventory,scan,manifest,resources=prepare_cc(source,out/'prepared');require(inventory==ref['inventory'] and scan==ref['expected_sorted_scan'],'Complete independent source preparation differs');report['independent_preparation']={'inventory':inventory,'expected_sorted_scan':scan}
        binary=ROOT/'m2/cc-pack-runtime/target/release/studio-cc-pack-runtime';verifier=binary.with_name('studio-indexed-engine');report['binary_sha256']=sha(binary);report['verifier_sha256']=sha(verifier);outputs=out/'outputs';outputs.mkdir();requests=out/'requests';requests.mkdir();scratch=out/'native-private';scratch.mkdir();oracle_private=out/'oracle-private';oracle_private.mkdir();active=Controller(binary,scratch,out/'controller.json');c=active;before=sha(source)
        def publication(req,code=None,pre_cancel=False):
            jid=c.call('publish',request=req,pre_cancel=pre_cancel)['job'];observations=[];s=wait(c,jid,observations);reply=c.call('publish_take',job=jid);result={'request':req,'snapshot':s,'receipt':reply,'admission_observations':observations}
            if code:require(s['state']==('cancelled' if pre_cancel else 'failed') and s['error']['code']==code and not s['error']['publication_uncertain'] and reply is None,'Wrong typed refusal: '+json.dumps(s))
            else:require(s['state']=='succeeded' and reply is not None,'Publication failed: '+json.dumps(s));require(c.call('publish_take',job=jid) is None and c.call('publish_cancel',job=jid)=='already_finished','Transfer or late cancellation differs')
            c.call('publish_forget',job=jid);return result
        report['stage']='reader-contention';original_cache=outputs/'original.idx';report['original_index']=publication(index_request(source,original_cache,'mdx'));cache_hash=sha(original_cache);opened=c.call('open',request={'source':str(source),'artifact':str(original_cache),'kind':'mdx','policy':'raw_exact'});sid=opened['session'];require(wait_reader(c,sid,opened['job'])['state']=='succeeded','Original reader failed');opened_manifest=c.call('take',session=sid,job=opened['job']);c.call('forget',session=sid,job=opened['job']);require(opened_manifest['value']['source_sha256']==before,'Original reader identity differs')
        target=outputs/'reader-blocked.mdx';blocked=publication(request(manifest,target,'utf8',inventory['metadata']),'limit_exceeded');require(blocked['snapshot']['error']['detail']=='resource_admission' and not target.exists(),'CC packing overlapped admitted reader');report['reader_contention_refusal']=blocked;c.call('close',session=sid);require(c.call('wait_closed',session=sid)['closed'],'Reader cleanup barrier failed');c.call('release',session=sid)
        report['stage']='old-cap-and-cancel-controls'
        for name,code,opts,pre_cancel in [('old-record-cap','limit_exceeded',{'records':100000},False),('old-decoded-cap','limit_exceeded',{'decoded_bytes':32*1024**2},False),('old-plan-cap','limit_exceeded',{'plan_charge':16*1024**2},False),('cannot-grow','invalid_input',{'records':250001},False),('pre-cancel','cancelled',{},True)]:
            target=outputs/(name+'.mdx');failure=publication(request(manifest,target,'utf8',inventory['metadata'],tighten=opts),code,pre_cancel);require(not target.exists(),'Control published output');report['expected_failures'].append({'case':name,**failure})
        expected_outputs={original_cache}
        for encoding in ['utf8','utf16']:
            report['stage']='full-'+encoding;print('Complete CC-CEDICT packing: '+encoding,flush=True);destination=outputs/('cc-'+encoding+'.mdx');req=request(manifest,destination,encoding,inventory['metadata']);packed=publication(req);reply=packed['receipt'];require(reply['kind']=='cc_packing','Wrong packing receipt kind');summary=reply['receipt'];wire=verify_output(destination,'mdx',inventory['expected_sorted_records'],inventory['metadata'],oracle_private);require(summary['profile']=='cc-mdx-block-spool-v1' and summary['source_sha256']==inventory['manifest_sha256'] and all(summary[k]==v for k,v in wire['records'].items()) and summary['file_bytes']==wire['file_bytes'] and summary['metadata']==wire['metadata'],'Native receipt differs from complete independent wire comparison');require(wire['metadata']['Encoding']==('UTF-8' if encoding=='utf8' else 'UTF-16'),'Wrong encoding')
            overwrite=publication(req,'destination_exists');require(sha(destination)==wire['file_sha256'],'Overwrite modified output');cache=outputs/('cc-'+encoding+'.idx');indexed=publication(index_request(destination,cache,'mdx'));q=requests/(encoding+'-verify.json');q.write_text(json.dumps({'path':str(destination),'artifact':str(cache),'kind':'mdx','policy':'raw_exact','action':'query','queries':[]})+'\n');v=timed_run(['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v',str(verifier),str(q)],env=dict(os.environ,TMPDIR=str(scratch)));(out/(encoding+'-verify.stdout')).write_text(v.stdout);(out/(encoding+'-verify.stderr')).write_text(v.stderr);verified=json.loads(v.stdout);rss=peak_rss(v.stderr,platform.system());check={'encoding':encoding,'publication':packed,'independent_wire':wire,'overwrite_refusal':overwrite,'index_publication':indexed,'index_verifier_returncode':v.returncode,'index_verifier_reply':verified,'index_verifier_peak_RSS_bytes':rss};report['checks'].append(check)
            require(v.returncode==0 and verified['status']=='queried' and verified['scan']==scan and verified['manifest']==indexed['receipt']['receipt']['manifest'] and verified['manifest']['source_sha256']==wire['file_sha256'] and verified['results']==[],'Strict full packed dictionary/index scan differs');require(rss<=RSS_TARGET and verified['memory']['locator']==0 and not list(scratch.iterdir()),'Verifier RSS/locator/private cleanup differs');expected_outputs|={destination,cache}
        require(len(c.call('publish_events'))<=8,'Unbounded progress retention');c.call('shutdown');c.call('publish',request=req,expect='closed');final=admission(c.call('admission'));require(final['shared']['closed'] and final['shared']['active_operations']==0 and final['readers']['retained_reply_bytes']==final['readers']['retained_session_handles']==0,'Final reservation/retention leak');rss=c.stop();active=None;report.update(final_admission=final,peak_RSS_bytes=rss,controller_transcript=c.transcript)
        require(rss<=RSS_TARGET,'Observed CC packing runtime RSS exceeds provisional 384 MiB target');require(set(outputs.iterdir())==expected_outputs and not list(scratch.iterdir()) and not list(oracle_private.iterdir()) and sha(source)==before and sha(original_cache)==cache_hash,'Source/cache changed or private/staging residue');shutil.rmtree(out/'prepared');report['private_cleanup']=True
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during qualification');check_lock();report['stage']='complete';report['status']='full_CC_CEDICT_block_spooled_packing_passed_M2_closeout_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-cc-pack-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_cc_pack_failed')
if __name__=='__main__':raise SystemExit(main())
