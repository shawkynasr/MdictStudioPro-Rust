"""Background larger packing/export plus shared reader/extraction admission."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import traceback
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller,review_page
from m2_large_io import METADATA
from large_io_oracle import row,ordered,digest,json_line,wire_rows,attrs,compare_export
from publication_runtime_lock import MANIFEST,LOCK,check_lock
from index_fixtures import make
from stream_mdd_fixtures import write
from m2_stream_extract import compare
from v2_audit import audit

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-large-io-user-run/m2-large-io-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previous qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/publication-runtime';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['publication_runtime_lock.py','m2_publication_runtime.py','test_m2_publication_runtime.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def admission(value,readers=None,packing=None,export=None,extraction=None):
    s=value['shared'];r=value['readers'];counts=[s[k] for k in ['readers','packings','exports','extractions']];require(all(isinstance(n,int) and n>=0 for n in counts),'Invalid shared counts');require(s['active_operations']==sum(counts)<=s['max_operations']<=2,'Shared operation accounting differs');require(s['packings']+s['exports']+s['extractions']<=1,'Publisher queue ran concurrent mutations')
    require(s['reserved_memory_bytes']==96*1024*1024*(s['readers']+s['exports']+s['extractions']+2*s['packings'])<=s['memory_cap']<=384*1024*1024,'Shared memory accounting differs');require(s['reserved_temporary_bytes']==768*1024*1024*(s['readers']+s['packings']+s['exports']+4*s['extractions'])<=s['temporary_cap']<=4*1024*1024*1024,'Shared temporary accounting differs')
    for key,want in [('readers',readers),('packings',packing),('exports',export),('extractions',extraction)]:
        if want is not None:require(s[key]==want,f'Shared {key} lease count differs')
    require(r['live_sessions']<=2 and r['retained_reply_bytes']<=r['retained_reply_cap']==8*1024*1024,'Internal reader budget differs')
def wait(c,jid,observations=None):
    deadline=time.monotonic()+300
    while True:
        status=c.call('publish_job',job=jid)
        if status['state'] in ['succeeded','failed','cancelled']:return status
        if observations is not None:
            value=c.call('admission');admission(value)
            if not observations or observations[-1]!=value:observations.append(value)
        require(time.monotonic()<deadline,'Publication job exceeded 300 seconds');time.sleep(0.05)
def dictionary(request):return {'kind':'dictionary','request':{k:str(v) if isinstance(v,Path) else v for k,v in request.items()}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_publication_runtime_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','scope':'one serial publication queue for accepted larger IO and streaming extraction, sharing logical active reservations with persistent readers; converter/index-build admission remains separate','steps':[],'checks':[]};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        def build(name,command):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(command);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode};report['steps'].append(step)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        build('refresh-publication-runtime',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-publication-runtime'])
        try:build('publication-runtime-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        build('build-publication-runtime',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-publication-runtime']);build('build-reader-seed',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine'])
        binary=ROOT/'m2/publication-runtime/target/debug/studio-publication-runtime';builder=binary.with_name('studio-indexed-engine');report['binary_sha256']=sha(binary);report['index_builder_binary_sha256']=sha(builder);inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();scratch=out/'private-scratch';scratch.mkdir();resources=inputs/'resources';resources.mkdir();data=bytes(range(256));(resources/'data.bin').write_bytes(data);(resources/'empty.bin').write_bytes(b'');reader=make(inputs/'reader.mdx',strip=True);cache=inputs/'reader.idx';seed=out/'seed.json';seed.write_text(json.dumps({'path':str(reader['path']),'kind':'mdx','artifact':str(cache),'policy':'header_ascii_v1','action':'build','queries':[]}));build('seed-reader-index',[str(builder),str(seed)]);spec={'source':str(reader['path']),'artifact':str(cache),'kind':'mdx','policy':'header_ascii_v1'}
        count=65536;manifest=inputs/'mdx.jsonl'
        with manifest.open('wb') as f:
            for i in range(count):f.write(json_line(*row(i,'mdx')))
        mdd_manifest=inputs/'mdd.jsonl'
        with mdd_manifest.open('w',encoding='utf-8',newline='\n') as f:
            for i in range(count):f.write(json.dumps({'key':f'files/r{i:05d}.bin','file':'data.bin' if i else 'empty.bin'})+'\n')
        extraction=write(inputs/'extract.mdd',[{'key':'assets/data.bin','bytes':200000,'seed':37},{'key':'empty.bin','bytes':0}]);malformed=inputs/'bad.jsonl';malformed.write_bytes(b'{\n');input_hashes={str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()};expected=ordered(count,'mdx');want=digest(expected)
        for encoding in ['utf8','utf16']:
            report['stage']=encoding;print(f'Checking shared runtime: {encoding}',flush=True);active=Controller(binary,scratch,out/(encoding+'-controller.json'));c=active;published=[];failures=[];observations=[];pages=[]
            def open_reader():
                v=c.call('open',request=spec);require(c.call('wait',session=v['session'],job=v['job'])['state']=='succeeded','Managed reader failed');require(c.call('take',session=v['session'],job=v['job'])['operation']=='opened','Missing reader manifest');c.call('forget',session=v['session'],job=v['job']);return v['session']
            def submit(request):return c.call('publish',request=request)['job']
            def fail(request,code):
                dst=Path(request['request']['destination']);before=set(outputs.iterdir());old=sha(dst) if dst.is_file() else None;j=submit(request);s=wait(c,j);require(s['state']=='failed' and s['error']['code']==code and not s['error']['publication_uncertain'],'Typed publication failure differs');require(c.call('publish_take',job=j) is None,'Failure retained success');c.call('publish_forget',job=j);require(set(outputs.iterdir())==before and (sha(dst) if dst.is_file() else None)==old,'Failure overwrote output or left stage');failures.append(s)
            def success(request):
                dst=Path(request['request']['destination']);before=set(outputs.iterdir());j=submit(request);s=wait(c,j,observations);require(s['state']=='succeeded' and s['result_available'],'Background publication failed');receipt=c.call('publish_take',job=j);require(c.call('publish_take',job=j) is None,'Publication result transferred twice');require(c.call('publish_cancel',job=j)=='already_finished','Late cancel changed committed state');c.call('publish_forget',job=j);require(set(outputs.iterdir())==before|{dst},'Publication stage residue');idle=c.call('admission');admission(idle,1,0,0,0);published.append({'request':request,'snapshot':s,'response':receipt,'admission_after':idle});return receipt['receipt']
            def pack(destination,source=manifest):return dictionary({'operation':'pack_mdx','source':source,'destination':destination,'encoding':encoding,'metadata':METADATA})
            a=open_reader();b=open_reader();full=c.call('admission');admission(full,2,0,0,0);fail(pack(outputs/(encoding+'-blocked.mdx')),'limit_exceeded');require(failures[-1]['error']['detail']=='resource_admission','Two readers did not block packing before execution')
            c.call('close',session=b);require(c.call('wait_closed',session=b)['closed'],'Reader cleanup acknowledgement failed');c.call('release',session=b);freed=c.call('admission');admission(freed,1,0,0,0)
            path=outputs/(encoding+'.mdx');request=pack(path);j=submit(request);page=c.call('submit',session=a,request={'query':'apple','offset':1,'limit':1})['job'];require(c.call('wait',session=a,job=page)['state']=='succeeded','Reader page failed while packing');reply=c.call('take',session=a,job=page);review_page(reply,reader,'apple',1,1,'header_ascii_v1');pages.append(reply);c.call('forget',session=a,job=page);s=wait(c,j,observations);require(s['state']=='succeeded','Larger background pack failed');response=c.call('publish_take',job=j);require(response['kind']=='dictionary','Wrong tagged packing response');summary=response['receipt'];require(all(summary[k]==v for k,v in want.items()),'Packed receipt digest differs');require(digest(wire_rows(path,'mdx'))==want and attrs(path)==summary['metadata'],'Independent complete packed wire/metadata differs');structural=audit(path);require(structural['status']=='structural_audit_passed','Packed file structural audit failed');require(summary['source_sha256']==sha(manifest),'Packing manifest identity differs');require(c.call('publish_take',job=j) is None and c.call('publish_cancel',job=j)=='already_finished','Single-transfer/late-cancel packing contract differs');c.call('publish_forget',job=j);published.append({'request':request,'snapshot':s,'response':response,'file_sha256':sha(path),'wire_record_digest':want,'structural_audit':structural})
            for txt in [False,True]:
                destination=outputs/(encoding+('.txt' if txt else '.jsonl'));req=dictionary({'operation':'export_txt' if txt else 'export_jsonl','source':path,'destination':destination});summary=success(req);require(all(summary[k]==v for k,v in want.items()) and summary['source_sha256']==sha(path) and summary['metadata']==attrs(path),'Export digest/source/metadata differs');published[-1]['file_check']=compare_export(destination,expected,txt)
            # Exercise extraction in the same queue after file publications.
            dest=outputs/(encoding+'-resources');req={'kind':'extraction','request':{'source':str(extraction['path']),'destination':str(dest)}};receipt=success(req);published[-1]['files']=compare(receipt,extraction,dest)
            if encoding=='utf8':
                path_mdd=outputs/'packed.mdd';req=dictionary({'operation':'pack_mdd','source':mdd_manifest,'resource_root':resources,'destination':path_mdd,'metadata':{**METADATA,'stylesheet':''}});receipt=success(req);expected_mdd=digest((f'files/r{i:05d}.bin',data if i else b'') for i in range(count));require(all(receipt[k]==v for k,v in expected_mdd.items()) and digest(wire_rows(path_mdd,'mdd'))==expected_mdd,'Background MDD packing differs');require(attrs(path_mdd)==receipt['metadata'],'MDD metadata differs');published[-1].update(wire_record_digest=expected_mdd,file_sha256=sha(path_mdd))
            fail(pack(outputs/(encoding+'-malformed.mdx'),malformed),'invalid_input');fail(pack(path),'destination_exists');fail(dictionary({'operation':'export_jsonl','source':inputs/'absent.mdx','destination':outputs/(encoding+'-absent.jsonl')}),'io')
            held=[]
            for i in range(8):
                req=pack(outputs/(encoding+f'-pre-cancel-{i}'));j=c.call('publish',request=req,pre_cancel=True)['job'];s=wait(c,j);require(s['state']=='cancelled' and s['cancel_requested'] and not s['error']['publication_uncertain'],'Precancelled publication executed');require(c.call('publish_take',job=j) is None,'Cancelled job retained result');held.append(j)
            c.call('publish',request=pack(outputs/(encoding+'-retention')),expect='retention_full');events=c.call('publish_events');require(len(events)<=8,'Publication event mailbox unbounded')
            for j in held:c.call('publish_forget',job=j)
            c.call('close',session=a);require(c.call('wait_closed',session=a)['closed'],'Last reader cleanup failed');c.call('release',session=a);idle=c.call('admission');admission(idle,0,0,0,0);require(idle['readers']['retained_reply_bytes']==idle['readers']['retained_session_handles']==0,'Reader metadata/replies retained');c.call('shutdown');c.call('publish',request=pack(outputs/(encoding+'-closed')),expect='closed');c.call('open',request=spec,expect='closed');final=c.call('admission');admission(final,0,0,0,0);require(final['shared']['closed'],'Admission not closed');rss=c.stop();active=None;require(rss<=RSS_TARGET,'Runtime observed RSS exceeded provisional threshold');require(not list(scratch.iterdir()),'Private snapshot/spool residue');require({str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()}==input_hashes,'Runtime changed source/cache/resource inputs');report['checks'].append({'case':encoding,'status':'publication_runtime_and_shared_admission_passed','publications':published,'typed_failures':failures,'reader_page_replies':pages,'two_reader_admission':full,'after_reader_release':freed,'active_admission_observations':observations,'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during runtime qualification');check_lock();report['stage']='complete';report['status']='m2_shared_larger_publication_runtime_first_gate_passed_converter_sizing_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-publication-runtime-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_publication_runtime_failed')
if __name__=='__main__':raise SystemExit(main())
