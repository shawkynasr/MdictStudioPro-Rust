"""First real MDX/MDD qualification through the accepted reader/runtime paths.

Selected inputs stay read-only. Private caches/extracted resources stay in the
new local output folder. Report page bodies are replaced with byte counts/SHA.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import tempfile
import time
import traceback
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,RSS_TARGET,CommandTimeout
from m2_sessions import Controller
from m2_converter_runtime import admission,wait
from converter_runtime_lock import MANIFEST,LOCK,check_lock
from real_reader_oracle import attrs,scan_to_database,page,redact_page

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-converter-runtime-user-run/m2-converter-runtime-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previously qualified source changed: {n}')
    return expected
def fingerprints():return {n:sha(ROOT/n) for n in ['scripts/m2_real_readers.py','scripts/real_reader_oracle.py','scripts/test_m2_real_readers.py','baseline/real-corpus-manifest.json']}
def catalog(inputs,manifest=None):
    inputs=inputs.resolve();require(inputs.is_dir(),'Selected input directory does not exist');path=manifest or ROOT/'baseline/real-corpus-manifest.json';require(path.stat().st_size<=256*1024,'Selection manifest exceeds 256 KiB');value=json.loads(path.read_text());require(set(value)=={'cases'} and 0<len(value['cases'])<=16,'Select 1..16 dictionary cases');result=[];seen=set()
    for c in value['cases']:
        cid=c['id'];require(isinstance(cid,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}',cid) and cid not in seen,'Require distinct bounded case IDs');seen.add(cid);relative=Path(c['path']) if manifest else Path(c['path']).name;source=(inputs/relative).resolve();require(source.is_relative_to(inputs),'Selected file escapes input directory');kind=source.suffix.lower().removeprefix('.');require(kind in ['mdx','mdd'],'Only selected MDX/MDD inputs supported');queries=c.get('lookup_keys',[]);require(isinstance(queries,list) and len(queries)<=8 and all(isinstance(q,str) and 0<len(q.encode())<=4096 and '\0' not in q for q in queries),'At most eight bounded raw lookup keys');result.append({'id':cid,'source':source,'kind':kind,'queries':queries})
    return result
def wait_reader(c,session,job):
    deadline=time.monotonic()+300
    while True:
        value=c.call('job',session=session,job=job)
        if value['state'] in ['succeeded','failed','cancelled']:return value
        require(time.monotonic()<deadline,'Real reader job exceeded 300 seconds');time.sleep(0.1)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--manifest',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-real-readers-out'),'Use an m2-real-readers-out prefix so private outputs stay excluded from packages');out.mkdir(exist_ok=False)
    report={'status':'m2_real_readers_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','scope':'first selected real unencrypted v2 plain/zlib MDX/MDD: complete independent scan, raw-exact cache/session pages and safe MDD extraction; no real converter or whole-dictionary rebuild claim','steps':[],'checks':[]};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK);cases=catalog(a.inputs,a.manifest);report['selection']=[{'id':c['id'],'file':c['source'].name,'kind':c['kind'],'exists':c['source'].is_file()} for c in cases];require(all(c['source'].is_file() for c in cases),'Selected dictionary missing; see selection list');cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac');system=platform.system();require(system in ['Darwin','Linux'],'Process measurement requires the supported Unix diagnostic runner');outputs=out/'outputs';outputs.mkdir();scratch=out/'private-rust';scratch.mkdir();oracle_scratch=out/'private-oracle';oracle_scratch.mkdir();env=dict(os.environ,TMPDIR=str(scratch))
        def build(name,command):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(command);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode};report['steps'].append(step)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        build('build-qualified-runtime',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-converter-runtime']);build('build-qualified-index',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine']);binary=ROOT/'m2/converter-runtime/target/debug/studio-converter-runtime';index_binary=binary.with_name('studio-indexed-engine');report['binary_sha256']=sha(binary);report['index_binary_sha256']=sha(index_binary)
        def indexed(name,request):
            q=out/(name+'-request.json');q.write_text(json.dumps(request,ensure_ascii=False));r=timed_run(['/usr/bin/time','-l' if system=='Darwin' else '-v',str(index_binary),str(q)],env);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode};report['steps'].append(step)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available');step['peak_RSS_bytes']=peak_rss(r.stderr,system);require(step['peak_RSS_bytes']<=RSS_TARGET,'Observed index process RSS exceeds provisional threshold');require(not list(scratch.iterdir()),'Index snapshot/sort residue');return json.loads(r.stdout),step['peak_RSS_bytes']
        for case in cases:
            cid=case['id'];source=case['source'];kind=case['kind'];report['stage']=cid;print(f'Qualifying selected real dictionary: {source.name}',flush=True);require(source.stat().st_size<=512*1024*1024,'Source exceeds qualified reader file cap');before=sha(source);case_dir=outputs/cid;case_dir.mkdir();query_set=case['queries']+['__MDICT_STUDIO_MISSING_PROBE__'];cache=case_dir/'dictionary.idx'
            with tempfile.TemporaryDirectory(dir=oracle_scratch) as private:
                db=sqlite3.connect(Path(private)/'queries.sqlite');db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA temp_store=FILE')
                try:
                    scan,queries,resources,frame=scan_to_database(source,kind,query_set,db,private);require(sha(source)==before,'Input changed during independent scan');header=attrs(source);base={'path':str(source),'kind':kind,'artifact':str(cache),'policy':'raw_exact','queries':[]};built,build_rss=indexed(cid+'-index-build',{**base,'action':'build'});require(built['status']=='published' and built['receipt']['manifest']['source_sha256']==before and built['receipt']['manifest']['records']==scan['records'],'Index receipt source/count differs');verified,verify_rss=indexed(cid+'-verified-scan',{**base,'action':'query'});require(verified['status']=='queried' and verified['scan']==scan and verified['manifest']['source_sha256']==before,'Complete independent/native ordinal/key/payload scan differs');require(verified['memory']['locator']==0 and verified['memory']['peak']<=verified['memory']['budget']==64*1024*1024,'Reader locator/parser budget differs');cache_hash=sha(cache)
                    active=Controller(binary,scratch,out/(cid+'-controller.json'));c=active;opened=c.call('open',request={'source':str(source),'artifact':str(cache),'kind':kind,'policy':'raw_exact'});sid=opened['session'];require(wait_reader(c,sid,opened['job'])['state']=='succeeded','Real managed reader failed');manifest=c.call('take',session=sid,job=opened['job']);require(manifest['operation']=='opened' and manifest['value']['source_sha256']==before and manifest['value']['records']==scan['records'] and manifest['value']['policy']=='raw_exact','Real session identity/profile differs');c.call('forget',session=sid,job=opened['job']);opened_admission=c.call('admission');admission(opened_admission,1,0);pages=[]
                    for query in queries:
                        for offset,limit in [(0,1 if kind=='mdd' else 2),(1,1),(2**64-1,0)]:
                            expected=page(db,query,offset,limit,kind)
                            if len(json.dumps(expected,ensure_ascii=False).encode())>1500000:limit=0;expected=page(db,query,offset,limit,kind)
                            req={'query':query,'offset':offset,'limit':limit};jid=c.call('submit',session=sid,request=req)['job'];require(wait_reader(c,sid,jid)['state']=='succeeded','Real indexed page failed');reply=c.call('take',session=sid,job=jid);raw_slot=c.transcript[-1]['reply'];raw_slot['ok']={'operation':'page','redacted':'pending validation'};redacted={'operation':'page','value':redact_page(reply['value'])};raw_slot['ok']=redacted;require(reply=={'operation':'page','value':expected},'Real page payload/duplicate ordinal/count differs');pages.append({'request':req,'reply':redacted});c.call('forget',session=sid,job=jid)
                    extraction=None
                    if kind=='mdd':
                        target=case_dir/'resources';j=c.call('publish',request={'kind':'extraction','request':{'source':str(source),'destination':str(target)}})['job'];observations=[];status=wait(c,j,observations);require(status['state']=='succeeded','Real MDD extraction failed');response=c.call('publish_take',job=j);receipt=response['receipt'];require(response['kind']=='extraction' and receipt['source_sha256']==before and receipt['resources']==scan['records'] and receipt['payload_bytes']==scan['payload_bytes'] and receipt['framed_resources_sha256']==frame,'Complete real MDD extraction receipt differs');actual={str(p.relative_to(target)).replace(os.sep,'/'):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in target.rglob('*') if p.is_file()};require(actual==resources,'Real resource file paths/bytes/hashes differ');require(c.call('publish_take',job=j) is None and c.call('publish_cancel',job=j)=='already_finished','Extraction transfer/late cancel differs');c.call('publish_forget',job=j);extraction={'receipt':receipt,'files':actual,'active_admission_observations':observations}
                    c.call('close',session=sid);require(c.call('wait_closed',session=sid)['closed'],'Real reader close barrier failed');c.call('release',session=sid);idle=c.call('admission');admission(idle,0,0);require(idle['shared']['active_operations']==0 and idle['readers']['retained_reply_bytes']==idle['readers']['retained_session_handles']==0,'Real reader/shared retention leaked');c.call('shutdown');final=c.call('admission');admission(final,0,0);runtime_rss=c.stop();active=None;require(runtime_rss<=RSS_TARGET,'Observed real runtime RSS exceeds provisional threshold');require(sha(source)==before and sha(cache)==cache_hash and not list(scratch.iterdir()),'Input/cache changed or private native residue');report['checks'].append({'case':cid,'file':source.name,'kind':kind,'status':'real_scan_index_session_and_optional_extraction_passed','source_sha256':before,'source_bytes':source.stat().st_size,'lookup_policy':'raw_exact','independent_scan':scan,'oracle_framed_sha256':frame,'index_receipt':built['receipt'],'index_sha256':cache_hash,'parser_memory':verified['memory'],'opened_manifest':manifest,'pages':pages,'extraction':extraction,'opened_admission':opened_admission,'final_admission':final,'peak_RSS_bytes':{'index_build':build_rss,'index_verify':verify_rss,'runtime':runtime_rss},'controller_transcript':c.transcript})
                finally:db.close()
            require(not list(oracle_scratch.iterdir()),'Private oracle spool/database residue')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'] and sha(ROOT/LOCK)==report['dependency_lock_sha256'],'Sources/lock changed during real-reader qualification');check_lock();report['stage']='complete';report['status']='m2_selected_real_reader_index_session_gate_passed_real_converters_and_closeout_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-real-readers-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_real_readers_failed')
if __name__=='__main__':raise SystemExit(main())
