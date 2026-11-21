"""Persistent indexed application sessions and bounded background page jobs."""
import argparse
import json
import os
from pathlib import Path
import platform
import queue
import shutil
import signal
import subprocess
import threading
import traceback
import unicodedata
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,RSS_TARGET,CommandTimeout
from session_lock import MANIFEST,LOCK,check_lock
from index_fixtures import make,expected_page
from bounded_fixtures import write,rows as generated_rows

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-index-user-run/m2-index-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previous qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/sessions';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['session_lock.py','m2_sessions.py','test_m2_sessions.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
class Controller:
    def __init__(self,binary,scratch,log):
        self.log=log;self.transcript=[];self.stderr=log.with_suffix('.stderr');self.err=self.stderr.open('w');env=dict(os.environ);env.update(TMPDIR=str(scratch),LC_ALL='C')
        self.process=subprocess.Popen(['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v',str(binary)],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,encoding='utf-8',start_new_session=True)
        self.lines=queue.Queue()
        def read():
            try:
                for line in self.process.stdout:self.lines.put(line)
            finally:self.lines.put(None)
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
    def call(self,op,expect=None,**args):
        command={'op':op,**args};line=json.dumps(command,ensure_ascii=False)+'\n';require(len(line.encode())<=65536,'Controller request too large');self.process.stdin.write(line);self.process.stdin.flush()
        try:line=self.lines.get(timeout=60)
        except queue.Empty:raise AssertionError('Session command exceeded 60 seconds')
        require(line is not None,'Session controller exited before replying');require(len(line.encode())<=2*1024*1024+65536,'Controller response exceeds diagnostic envelope cap');reply=json.loads(line);self.transcript.append({'command':command,'reply':reply})
        if expect:require(reply.get('error',{}).get('code')==expect,f'{op}: expected {expect}, got {reply}');return reply['error']
        require('ok' in reply,f'{op} failed: {reply}');return reply['ok']
    def stop(self):
        self.process.stdin.close()
        try:code=self.process.wait(timeout=60)
        except subprocess.TimeoutExpired:self.abort();raise AssertionError('Session shutdown exceeded 60 seconds')
        self.reader.join(timeout=1);self.err.close();self.log.write_text(json.dumps(self.transcript,ensure_ascii=False,indent=2)+'\n');require(code==0,'Controller failed during shutdown; return stderr log');require(not self.reader.is_alive(),'Controller output did not reach EOF');remaining=[]
        while not self.lines.empty():remaining.append(self.lines.get_nowait())
        require(all(line is None for line in remaining),'Unexpected extra protocol output');return peak_rss(self.stderr.read_text(),platform.system())
    def abort(self):
        if self.process.poll() is None:
            try:os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            self.process.wait(timeout=10)
        if not self.err.closed:self.err.close()
        self.log.write_text(json.dumps(self.transcript,ensure_ascii=False,indent=2)+'\n')

def review_page(response,fixture,q,offset,limit,policy):
    want=expected_page(fixture['rows'],q,offset,limit,policy,fixture.get('sensitive',False),fixture.get('strip',False),fixture['kind'])
    require(response=={'operation':'page','value':want},'Persistent session page changed physical identity/order/payload')
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_sessions_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','platform':platform.platform(),'steps':[],'checks':[],'scope':'persistent read-only application sessions and per-session background open/page jobs; existing index construction and packing workers remain separate'};active=None
    try:
        require(unicodedata.unidata_version=='16.0.0','Use existing Python 3.14 Unicode16 venv');report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Require Rust-enabled Mac')
        def run(name,cmd):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(cmd);step={'name':name,'returncode':r.returncode};report['steps'].append(step);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available');return r
        run('refresh-session-artifacts',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-sessions'])
        try:run('session-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        run('build-session-cli',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-sessions','--bin','studio-sessions'])
        run('build-index-tool',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine'])
        binary=ROOT/'m2/sessions/target/debug/studio-sessions';index_binary=ROOT/'m2/sessions/target/debug/studio-indexed-engine';report['binary_sha256']=sha(binary);report['index_builder_binary_sha256']=sha(index_binary)
        inputs=out/'inputs';inputs.mkdir();caches=out/'caches';caches.mkdir();scratch=out/'private-scratch';scratch.mkdir()
        fixtures=[]
        for encoding in ['utf8','utf16']:
            f=make(inputs/(encoding+'.mdx'),encoding,strip=True);f['label']=encoding;fixtures.append(f)
        for label,kind,count in [('binary','mdd',100),('larger-mdx','mdx',65536),('larger-mdd','mdd',65536)]:
            print(f'Preparing {label}',flush=True);f=write(inputs/(label+'.'+kind),count,kind);f.update(rows=list(generated_rows(count,kind)),label=label);fixtures.append(f)
        for f in fixtures:
            report['stage']=f['label'];policy='raw_exact' if f['kind']=='mdd' else 'header_ascii_v1';artifact=caches/(f['label']+'.idx');request=out/(f['label']+'-build.json');request.write_text(json.dumps({'path':str(f['path']),'kind':f['kind'],'artifact':str(artifact),'policy':policy,'action':'build','queries':[]}))
            run(f['label']+'-seed-index',[str(index_binary),str(request)]);source_hash=sha(f['path']);cache_hash=sha(artifact);active=Controller(binary,scratch,out/(f['label']+'-session.json'));c=active;spec={'source':str(f['path']),'artifact':str(artifact),'kind':f['kind'],'policy':policy}
            opened=c.call('open',request=spec);sid=opened['session'];job=opened['job'];state=c.call('wait',session=sid,job=job);require(state['state']=='succeeded','Session open failed');require(c.call('snapshot',session=sid)['state']=='ready','Open completion published before Ready');metadata=c.call('take',session=sid,job=job);require(metadata['operation']=='opened' and metadata['value']['source_sha256']==source_hash,'Session bound to wrong source');require(c.call('take',session=sid,job=job) is None,'Open reply transferred twice');c.call('forget',session=sid,job=job)
            snapshots=[];pages=[];queries=[('apple',0,1),('apple',1,1),('APPLE',0,4),('a?b',0,4),('duplicate',384,128),('duplicate',0,0),('absent',2**64-1,2)] if f['label'] in ['utf8','utf16'] else [('row00000000',0,1),('row00000000',1,1),('ROW00000000',0,4),('字',0,2),('𠀀',0,2),('absent',0,0)]
            for q,offset,limit in queries:
                page_request={'query':q,'offset':offset,'limit':limit};jid=c.call('submit',session=sid,request=page_request)['job'];status=c.call('wait',session=sid,job=jid);require(status['state']=='succeeded','Page background job failed');response=c.call('take',session=sid,job=jid);review_page(response,f,q,offset,limit,policy);pages.append({'request':page_request,'response':response});snapshots.append(status);require(c.call('take',session=sid,job=jid) is None,'Page transferred twice');require(c.call('cancel',session=sid,job=jid)=='already_finished','Late cancel changed committed result');c.call('forget',session=sid,job=jid)
            jid=c.call('submit',session=sid,request={'query':queries[0][0],'offset':0,'limit':1},pre_cancel=True)['job'];require(c.call('wait',session=sid,job=jid)['state']=='cancelled','Precancelled page ran');require(c.call('take',session=sid,job=jid) is None,'Cancelled page retained reply');c.call('forget',session=sid,job=jid)
            c.call('submit',session=sid,request={'query':'x','offset':0,'limit':129},expect='invalid_input');require(c.call('admission')['retained_reply_bytes']==0,'Transferred replies still reserved')
            # Controlled scratch fixtures only: test that existing session owns
            # private snapshots after public files are replaced, then restore.
            saved_source=f['path'].with_suffix('.saved-source');saved_cache=artifact.with_suffix('.saved-cache');f['path'].rename(saved_source);artifact.rename(saved_cache)
            try:
                f['path'].write_bytes(b'replaced source');artifact.write_bytes(b'replaced cache');q,offset,limit=queries[0];jid=c.call('submit',session=sid,request={'query':q,'offset':offset,'limit':limit})['job'];require(c.call('wait',session=sid,job=jid)['state']=='succeeded','Public replacement broke snapshot session');response=c.call('take',session=sid,job=jid);review_page(response,f,q,offset,limit,policy);c.call('forget',session=sid,job=jid)
            finally:
                f['path'].unlink(missing_ok=True);artifact.unlink(missing_ok=True);saved_source.rename(f['path']);saved_cache.rename(artifact)
            # Session admission counts live readers, including open/closing work.
            second=c.call('open',request=spec);require(c.call('wait',session=second['session'],job=second['job'])['state']=='succeeded','Second open failed');c.call('open',request=spec,expect='resource_limit');c.call('close',session=second['session']);require(c.call('wait_closed',session=second['session'])['closed'],'Close not acknowledged');c.call('release',session=second['session'])
            # Retained job slots include consumed results until explicit forget.
            held=[]
            for _ in range(8):
                jid=c.call('submit',session=sid,request={'query':'absent','offset':0,'limit':0})['job'];require(c.call('wait',session=sid,job=jid)['state']=='succeeded','Retention seed failed');held.append(jid)
            c.call('submit',session=sid,request={'query':'absent','offset':0,'limit':0},expect='retention_full')
            for jid in held:c.call('forget',session=sid,job=jid)
            require(c.call('admission')['retained_reply_bytes']==0,'Forgotten replies still reserved');events=c.call('events',session=sid);require(len(events)<=8,'Unbounded event history');c.call('close',session=sid);require(c.call('wait_closed',session=sid)['closed'],'Close failed');require(c.call('admission')['live_sessions']==0,'Closed session still consumes reader reservation');c.call('submit',session=sid,request={'query':'x','offset':0,'limit':1},expect='closed');c.call('release',session=sid)
            cancelled=c.call('open',request=spec,pre_cancel=True);require(c.call('wait_closed',session=cancelled['session'])['closed'],'Cancelled open did not terminate');require(c.call('job',session=cancelled['session'],job=cancelled['job'])['state']=='cancelled','Precancelled open succeeded');c.call('release',session=cancelled['session']);c.call('shutdown');c.call('open',request=spec,expect='closed');final=c.call('admission');require(final['live_sessions']==0 and final['retained_session_handles']==0 and final['retained_reply_bytes']==0,'Shutdown leaked logical reservations')
            rss=c.stop();active=None;require(rss<=RSS_TARGET,'Session process exceeded provisional RSS threshold');require(not list(scratch.iterdir()),'Normal-exit private snapshot residue');require(sha(f['path'])==source_hash and sha(artifact)==cache_hash,'Fixture restore or readonly cache changed bytes')
            report['checks'].append({'case':f['label'],'status':'persistent_session_matrix_passed','source_sha256':source_hash,'artifact_sha256':cache_hash,'open_manifest':metadata['value'],'pages':pages,'page_job_snapshots':snapshots,'snapshot_replacement_page':response,'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during session qualification');check_lock();report['stage']='complete';report['status']='m2_persistent_sessions_background_pages_passed_larger_paths_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-sessions-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_sessions_failed')
if __name__=='__main__':raise SystemExit(main())
