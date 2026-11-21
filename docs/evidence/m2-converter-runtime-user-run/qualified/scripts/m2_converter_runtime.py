"""Larger six-converter parity and shared runtime admission qualification."""
import argparse
import json
from pathlib import Path
import shutil
import time
import traceback
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout
from m2_sessions import Controller,review_page
from index_fixtures import make
from converter_runtime_lock import MANIFEST,LOCK,check_lock
from converter_runtime_fixtures import generate,original,compare_output,record_digest,workbook

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-publication-runtime-user-run/m2-publication-runtime-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previously qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/converter-runtime';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['converter_runtime_lock.py','converter_runtime_fixtures.py','m2_converter_runtime.py','test_m2_converter_runtime.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def admission(value,readers=None,conversions=None):
    s=value['shared'];counts=[s[k] for k in ['readers','packings','exports','extractions','conversions']];require(all(type(n)==int and n>=0 for n in counts),'Invalid shared counts');require(s['active_operations']==sum(counts)<=s['max_operations']<=2,'Operation count differs');require(sum(counts[1:])<=1,'Multiple publication jobs active')
    require(s['reserved_memory_bytes']==1024*1024*(96*(s['readers']+s['exports']+s['extractions'])+192*s['packings']+256*s['conversions'])<=s['memory_cap']<=384*1024*1024,'Conversion/shared memory charge differs');require(s['reserved_temporary_bytes']==768*1024*1024*(sum(counts)+3*s['extractions'])<=s['temporary_cap']<=4*1024*1024*1024,'Temporary charge differs')
    if readers is not None:require(s['readers']==readers,'Reader reservation count differs')
    if conversions is not None:require(s['conversions']==conversions,'Conversion reservation count differs')
    r=value['readers'];require(r['live_sessions']<=2 and r['retained_reply_bytes']<=r['retained_reply_cap']==8*1024*1024,'Reader retention exceeds cap')
def wait(c,jid,observations=None):
    deadline=time.monotonic()+300
    while True:
        value=c.call('publish_job',job=jid)
        if value['state'] in ['succeeded','failed','cancelled']:return value
        if observations is not None:
            a=c.call('admission');admission(a)
            if not observations or observations[-1]!=a:observations.append(a)
        require(time.monotonic()<deadline,'Conversion exceeded 300 seconds');time.sleep(0.05)
def request(kind,source,destination,**options):return {'kind':'conversion','request':{'converter':kind,'input':str(source),'destination':str(destination),**options}}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_converter_runtime_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','scope':'first larger owned six-converter profile, private snapshots and thin publication receipts under shared reader/publication admission; no streaming XLSX converter or hard RSS claim','steps':[],'checks':[]};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();manifest=json.loads((ROOT/'baseline/source-manifest.json').read_text());names=['base_plugin.py','excel_utils.py']+[n for n in manifest['files'] if n.startswith('plugins/')];report['legacy_oracle_sha256']={}
        for n in names:require(sha(ROOT/'baseline/legacy'/n)==manifest['files'][n],'Captured Python oracle changed');report['legacy_oracle_sha256']['baseline/legacy/'+n]=manifest['files'][n]
        cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        def build(name,cmd):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(cmd);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode};report['steps'].append(step)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        build('refresh-converter-runtime',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-converter-runtime'])
        try:build('converter-runtime-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        build('build-converter-runtime',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-converter-runtime']);build('build-reader-seed',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-indexed-engine','--bin','studio-indexed-engine']);binary=ROOT/'m2/converter-runtime/target/debug/studio-converter-runtime';builder=binary.with_name('studio-indexed-engine');report['binary_sha256']=sha(binary);report['index_builder_binary_sha256']=sha(builder)
        inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();oracles=out/'python-oracles';oracles.mkdir();scratch=out/'private-scratch';scratch.mkdir();reader=make(inputs/'reader.mdx',strip=True);cache=inputs/'reader.idx';seed=out/'seed.json';seed.write_text(json.dumps({'path':str(reader['path']),'kind':'mdx','artifact':str(cache),'policy':'header_ascii_v1','action':'build','queries':[]}));build('seed-reader-index',[str(builder),str(seed)]);spec={'source':str(reader['path']),'artifact':str(cache),'kind':'mdx','policy':'header_ascii_v1'};report['stage']='fixture_generation';print('Preparing 12,000-row MOE and 16,000-line CC-CEDICT sources',flush=True);cases=generate(inputs);bad=inputs/'bad-utf8.txt';bad.write_bytes(b'\xff\n');missing_head=inputs/'missing-head.xlsx';workbook(missing_head,[{'irrelevant':'value'}]);bad_xlsx=inputs/'bad.xlsx';bad_xlsx.write_bytes(b'not a workbook');before_inputs={str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()}
        for case in cases:
            kind=case['kind'];source=case['source'];report['stage']=kind;print(f'Checking original Python parity and runtime: {kind}',flush=True);expected,metrics,comments=original(source,kind,oracles/(kind+'.txt'));want=record_digest(expected,kind);require(len(expected)>1000 and want['payload_bytes']+want['key_bytes']<=32*1024*1024,'Fixture must exceed old entry cap and fit new decoded cap');active=Controller(binary,scratch,out/(kind+'-controller.json'));c=active;observations=[];failures=[]
            def open_reader():
                v=c.call('open',request=spec);require(c.call('wait',session=v['session'],job=v['job'])['state']=='succeeded','Managed reader failed');c.call('take',session=v['session'],job=v['job']);c.call('forget',session=v['session'],job=v['job']);return v['session']
            def fail(req,code):
                dst=Path(req['request']['destination']);old=sha(dst) if dst.is_file() else None;before=set(outputs.iterdir());j=c.call('publish',request=req)['job'];s=wait(c,j);require(s['state']=='failed' and s['error']['code']==code and not s['error']['publication_uncertain'],'Typed converter failure differs');require(c.call('publish_take',job=j) is None,'Failure retained success');c.call('publish_forget',job=j);require(set(outputs.iterdir())==before and (sha(dst) if dst.is_file() else None)==old,'Failure changed destination or left stage');failures.append(s)
            first=open_reader();second=open_reader();full=c.call('admission');admission(full,2,0);fail(request(kind,source,outputs/(kind+'-blocked.txt')),'limit_exceeded');require(failures[-1]['error']['detail']=='resource_admission','Two readers did not block conversion before input I/O');c.call('close',session=second);require(c.call('wait_closed',session=second)['closed'],'Reader close barrier failed');c.call('release',session=second);freed=c.call('admission');admission(freed,1,0)
            destination=outputs/(kind+'.txt');before=set(outputs.iterdir());req=request(kind,source,destination);jid=c.call('publish',request=req)['job'];pj=c.call('submit',session=first,request={'query':'apple','offset':1,'limit':1})['job'];require(c.call('wait',session=first,job=pj)['state']=='succeeded','Reader page failed alongside conversion');page=c.call('take',session=first,job=pj);review_page(page,reader,'apple',1,1,'header_ascii_v1');c.call('forget',session=first,job=pj);status=wait(c,jid,observations);require(status['state']=='succeeded','Larger converter publication failed');response=c.call('publish_take',job=jid);require(response['kind']=='conversion','Wrong converter response tag');receipt=response['receipt'];require(receipt['profile']=='larger-owned-converters-v1' and receipt['converter']==kind and receipt['entries']==len(expected) and receipt['metrics']==metrics and receipt['comments_count']==comments and receipt['source_sha256']==sha(source) and receipt['file_bytes']==destination.stat().st_size,'Thin converter receipt differs from original-plugin oracle');actual=compare_output(destination,expected,kind);require(set(outputs.iterdir())==before|{destination},'Converter publication stage residue');require(c.call('publish_take',job=jid) is None and c.call('publish_cancel',job=jid)=='already_finished','Converter result transfer/late-cancel differs');c.call('publish_forget',job=jid);after=c.call('admission');admission(after,1,0)
            fail(request(kind,source,destination),'destination_exists');fail(request(kind,source,outputs/(kind+'-entries.txt'),tighten={'entries':1}),'limit_exceeded');fail(request(kind,source,outputs/(kind+'-input.txt'),tighten={'input_bytes':1}),'limit_exceeded')
            if kind=='cc_cedict':
                fail(request(kind,bad,outputs/'bad-utf8.txt'),'invalid_encoding');fail(request(kind,source,outputs/'grow.txt',tighten={'entries':100001}),'invalid_input');fail(request(kind,source,outputs/'decoded.txt',tighten={'decoded_bytes':16}),'limit_exceeded');fail(request(kind,source,outputs/'output.txt',tighten={'output_bytes':8}),'limit_exceeded');fail(request(kind,source,outputs/'worksheet.txt',worksheet='Sheet'),'invalid_input')
            if kind=='moe_revised':
                fail(request(kind,source,outputs/'rows.txt',tighten={'workbook_rows':10}),'limit_exceeded');fail(request(kind,source,outputs/'cells.txt',tighten={'workbook_cells':16}),'limit_exceeded');fail(request(kind,source,outputs/'workbook-decoded.txt',tighten={'workbook_decoded_bytes':1}),'limit_exceeded');fail(request(kind,missing_head,outputs/'missing-head.txt'),'malformed_source');fail(request(kind,bad_xlsx,outputs/'bad-xlsx.txt'),'malformed_workbook');fail(request(kind,source,outputs/'absent-sheet.txt',worksheet='Absent'),'sheet_not_found')
            held=[]
            for i in range(8):
                j=c.call('publish',request=request(kind,source,outputs/(kind+f'-cancel-{i}.txt')),pre_cancel=True)['job'];s=wait(c,j);require(s['state']=='cancelled' and s['cancel_requested'] and not s['error']['publication_uncertain'],'Precancelled converter executed');require(c.call('publish_take',job=j) is None,'Cancelled converter retained result');held.append(j)
            c.call('publish',request=request(kind,source,outputs/(kind+'-retention.txt')),expect='retention_full');require(len(c.call('publish_events'))<=8,'Unbounded event retention')
            for j in held:c.call('publish_forget',job=j)
            c.call('close',session=first);require(c.call('wait_closed',session=first)['closed'],'Last reader cleanup failed');c.call('release',session=first);idle=c.call('admission');admission(idle,0,0);require(idle['readers']['retained_session_handles']==idle['readers']['retained_reply_bytes']==0,'Reader handle/reply retention leaked');c.call('shutdown');c.call('publish',request=request(kind,source,outputs/(kind+'-closed.txt')),expect='closed');c.call('open',request=spec,expect='closed');final=c.call('admission');admission(final,0,0);require(final['shared']['closed'],'Admission not closed');rss=c.stop();active=None;require(rss<=RSS_TARGET,'Converter observed RSS exceeded provisional 384 MiB threshold');require(not list(scratch.iterdir()),'Private input snapshot residue');require({str(p.relative_to(inputs)):sha(p) for p in inputs.rglob('*') if p.is_file()}==before_inputs,'Conversion changed input/cache bytes');report['checks'].append({'case':kind,'status':'larger_converter_python_parity_and_shared_admission_passed','input_rows':case['input_rows'],'input_sha256':sha(source),'request':req,'receipt':receipt,'success_snapshot':status,'normalized_record_digest':actual,'rust_output_sha256':sha(destination),'python_output_sha256':sha(oracles/(kind+'.txt')),'raw_python_bytes_equal':destination.read_bytes()==(oracles/(kind+'.txt')).read_bytes(),'expected_metrics':metrics,'typed_failures':failures,'reader_page_reply':page,'two_reader_admission':full,'after_reader_release':freed,'after_publication':after,'active_admission_observations':observations,'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during converter qualification');check_lock();report['stage']='complete';report['status']='m2_larger_six_converter_shared_runtime_first_gate_passed_real_inputs_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-converter-runtime-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_converter_runtime_failed')
if __name__=='__main__':raise SystemExit(main())
