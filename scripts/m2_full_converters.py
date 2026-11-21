"""Shared background integration of six qualified full converter profiles.

This compares composition against accepted standalone native outputs; it does
not rerun the Python output oracle or qualify real dictionary packing. It adds
an independent complete Concise row-normalization comparison.
"""
import argparse
import json
import os
import platform
import shutil
import time
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,RSS_TARGET,CommandTimeout,peak_rss
from m2_sessions import Controller
from m2_official_mini_idioms import extract_sources
from full_converter_runtime_lock import MANIFEST,LOCK,check_lock
REFERENCE='docs/evidence/full-converter-runtime-plan/reference.json'
CONCISE_ROWS='docs/evidence/full-converter-runtime-plan/concise-rows-reference.json'
PROFILES={'cc_cedict':'cc','moe_concise':'concise','moe_mini':'small_moe','moe_idioms':'small_moe','moe_revised':'grouped_moe','moe_revised_wfg':'grouped_moe'}
def request(kind,source,destination,worksheet=None,**options):
    inner={'converter':kind,'input':str(source),'destination':str(destination),**options}
    if worksheet is not None:inner['worksheet']=worksheet
    return {'kind':'conversion','request':{'profile':PROFILES[kind],'request':inner}}
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-revised-render-user-run/m2-revised-render-report.json').read_text());p={**r['protected_source_sha256'],**r['source_sha256']}
    require(len(p)==265,'Protected inventory changed')
    for n,h in p.items():require(sha(ROOT/n)==h,'Qualified source changed: '+n)
    return p
def fingerprints():
    files=[p for p in (ROOT/'m2/full-converter-runtime').rglob('*') if p.is_file() and 'target' not in p.parts]
    files += [ROOT/n for n in ['scripts/m2_full_converters.py','scripts/full_converter_runtime_lock.py','scripts/test_full_converters.py',REFERENCE,CONCISE_ROWS]]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}
def admission(value):
    s=value['shared'];r=value['readers'];unit=1024*1024
    require(s['max_operations']==2 and s['memory_cap']==384*unit and s['temporary_cap']==4096*unit,'Shared ceilings differ')
    weights={'readers':(96,768),'packings':(192,768),'exports':(96,768),'extractions':(96,3072),'conversions':(384,768)}
    require(all(type(s[k]) is int and s[k]>=0 for k in weights),'Invalid reservation counters')
    count=sum(s[k] for k in weights);memory=sum(s[k]*w[0]*unit for k,w in weights.items());temporary=sum(s[k]*w[1]*unit for k,w in weights.items())
    require(s['active_operations']==count<=2 and s['reserved_memory_bytes']==memory<=384*unit and s['reserved_temporary_bytes']==temporary<=4096*unit,'Shared ledger differs or overlaps exclusive conversion')
    require(0<=r['retained_reply_bytes']<=r['retained_reply_cap']==8*unit,'Reader reply retention differs')
    return value
def wait(c,jid,observations=None):
    deadline=time.monotonic()+300
    while True:
        status=c.call('publish_job',job=jid)
        value=admission(c.call('admission'))
        if observations is not None and (not observations or observations[-1]!=value):observations.append(value)
        if status['state'] in ['succeeded','failed','cancelled']:return status
        require(time.monotonic()<deadline,'Converter job exceeded 300 seconds');time.sleep(.05)
def runtime_receipt(spec):
    receipt=dict(spec['receipt'])
    if spec['converter']=='moe_concise':receipt['profile']='moe-concise-disk-groups-txt-v1'
    return {'kind':'conversion','receipt':{'profile':spec['profile'],'receipt':receipt}}
def concise_rows_probe(cargo,out,sources,report):
    from xlsx_spool_oracle import inspect
    ref=json.loads((ROOT/CONCISE_ROWS).read_text());source=sources['dict_concised_2014_20260929.xlsx'];report['stage']='concise-independent-row-normalization';print('Checking all Concise normalized rows against captured Python',flush=True)
    actual=inspect(source,ref['worksheet']);actual['source_sha256']=sha(source);require(actual==ref,'Complete Concise Python row normalization changed')
    private=out/'concise-row-private';private.mkdir();request=out/'concise-row-request.json';request.write_text(json.dumps({'source':str(source),'worksheet':ref['worksheet'],'tighten':{'rows':50000,'cells':750000,'part_bytes':32*1024*1024,'normalized_bytes':32*1024*1024}})+'\n')
    binary=ROOT/'m2/full-converter-runtime/target/release/studio-xlsx-spool';env=dict(os.environ);env.update(TMPDIR=str(private),LC_ALL='C');result=timed_run(['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v',str(binary),str(request)],env=env)
    (out/'concise-row.stdout').write_text(result.stdout);(out/'concise-row.stderr').write_text(result.stderr);reply=json.loads(result.stdout);rss=peak_rss(result.stderr,platform.system());report['concise_row_normalization']={'reply':reply,'returncode':result.returncode,'peak_RSS_bytes':rss,'python_reference':actual,'binary_sha256':sha(binary)}
    require(result.returncode==0 and reply['status']=='succeeded' and reply['private_cleanup'],'Concise disk row reader failed')
    require(all(reply['receipt'][k]==v for k,v in ref.items()),'Full native Concise rows differ from independent Python')
    require(rss<=192*1024*1024 and not list(private.iterdir()),'Concise row reader RSS/cleanup failed')
def check_reference(ref):
    measured=json.loads((ROOT/'docs/evidence/official-converter-input-inspection/measurements.json').read_text())
    require(ref['archives']==measured['archives'],'Inspected archive identities differ')
    require(len(ref['cases'])==6 and {c['converter'] for c in ref['cases']}==set(PROFILES),'Missing or duplicated full converter case')
    for c in ref['cases']:
        r=json.loads((ROOT/c['accepted_report']).read_text());kind=c['converter']
        source=next(x for x in measured['legacy_output_measurements'] if x['converter']==kind)
        require(c['member']==source['input'] and c['worksheet']==source.get('worksheet'),'Inspected source selector differs')
        if c['profile']=='grouped_moe':
            old=next(x for x in r['checks'] if x['case']=='full-'+kind);receipt=dict(old['reply']['receipt']);rows=receipt.pop('row_source');receipt.pop('worksheet');receipt['pipeline_profile']=receipt.pop('profile');receipt.update(row_digest=rows['row_digest'],row_spool_bytes=rows['row_spool_bytes']);h=old['output_sha256']
        else:
            old=next(x for x in r['checks'] if x.get('receipt',{}).get('converter')==kind);receipt=old['receipt'];h=old['native_output_sha256']
        require(c['receipt']==receipt and c['native_output_sha256']==h and c['profile']==PROFILES[kind],'Accepted standalone reference differs: '+kind)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archives',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-full-converters-out'),'Use m2-full-converters-out prefix for private outputs');out.mkdir(exist_ok=False)
    report={'status':'m2_full_converters_failed','stage':'preflight','M2_complete':False,'comparison':'accepted standalone native output hashes; new independent Concise row oracle; previous Python output evidence retained','steps':[],'checks':[],'native_reader_contention':'deterministic synthetic Rust tests; no independent reader app check requested','RSS_is_OS_limit':False};active=None
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();ref=json.loads((ROOT/REFERENCE).read_text());check_reference(ref);report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        sources=extract_sources(a.archives.resolve(),out/'sources',ref['archives']);cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        for name,command in [('native-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('release-build',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-full-converter-runtime']),('release-row-reader',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'-p','studio-xlsx-spool','--bin','studio-xlsx-spool'])]:
            report['stage']=name;print(name,flush=True);result=timed_run(command);log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log);report['steps'].append({'name':name,'returncode':result.returncode,'log_tail':log[-64000:]});require(result.returncode==0,'Native command failed: '+name)
        concise_rows_probe(cargo,out,sources,report)
        binary=ROOT/'m2/full-converter-runtime/target/release/studio-full-converter-runtime';report['binary_sha256']=sha(binary);outputs=out/'outputs';outputs.mkdir()
        for spec in ref['cases']:
            kind=spec['converter'];report['stage']=kind;print('Full background conversion: '+kind,flush=True);scratch=out/(kind+'-private');scratch.mkdir();active=Controller(binary,scratch,out/(kind+'-controller.json'));c=active;source=sources[spec['member']];before=sha(source);destination=outputs/(kind+'.txt');req=request(kind,source,destination,spec['worksheet']);jid=c.call('publish',request=req)['job'];observations=[];status=wait(c,jid,observations)
            require(status['state']=='succeeded','Full native background conversion failed: '+json.dumps(status));response=c.call('publish_take',job=jid);require(response==runtime_receipt(spec),'Profile receipt differs from qualified standalone converter');require(len(json.dumps(response).encode())<=4096,'Receipt is not thin');require(sha(destination)==spec['native_output_sha256'],'Background output differs from accepted standalone bytes');require(c.call('publish_take',job=jid) is None and c.call('publish_cancel',job=jid)=='already_finished','One-transfer/late cancel differs');c.call('publish_forget',job=jid)
            def refuse(name,code,pre_cancel=False,**opts):
                target=destination if name=='overwrite' else outputs/(kind+'-'+name+'.txt');rid=c.call('publish',request=request(kind,source,target,spec['worksheet'],**opts),pre_cancel=pre_cancel)['job'];s=wait(c,rid);require(s['state']==('cancelled' if pre_cancel else 'failed') and s['error']['code']==code and not s['error']['publication_uncertain'],'Wrong refusal: '+name);require(c.call('publish_take',job=rid) is None,'Refusal retained result');c.call('publish_forget',job=rid)
                require(sha(destination)==spec['native_output_sha256'] if name=='overwrite' else not target.exists(),'Refused job changed/published output');return {'case':name,'snapshot':s}
            failures=[refuse('overwrite','destination_exists'),refuse('lowered-entries','limit_exceeded',tighten={'entries':1})]
            retained=[]
            for i in range(8):
                target=outputs/(kind+'-pre-cancel-'+str(i)+'.txt');rid=c.call('publish',request=request(kind,source,target,spec['worksheet']),pre_cancel=True)['job'];s=wait(c,rid);require(s['state']=='cancelled' and s['error']['code']=='cancelled' and not target.exists() and c.call('publish_take',job=rid) is None,'Pre-cancel publication/result leak');retained.append(rid)
            c.call('publish',request=req,pre_cancel=True,expect='retention_full');require(len(c.call('publish_events'))<=8,'Unbounded progress event retention')
            for rid in retained:c.call('publish_forget',job=rid)
            idle=admission(c.call('admission'));require(idle['shared']['active_operations']==0 and idle['readers']['live_sessions']==idle['readers']['retained_session_handles']==idle['readers']['retained_reply_bytes']==0,'Idle reservation/retention leak');c.call('shutdown');c.call('publish',request=req,expect='closed');final=admission(c.call('admission'));require(final['shared']['closed'] and final['shared']['active_operations']==0,'Shutdown ledger differs');rss=c.stop();active=None;report['active_case_observation']={'case':kind,'peak_RSS_bytes':rss,'snapshot':status,'receipt':response,'native_output_sha256':sha(destination),'final_admission':final,'controller_transcript':c.transcript};require(rss<=RSS_TARGET,'Observed RSS exceeds provisional 384 MiB threshold');require(sha(source)==before and not list(scratch.iterdir()),'Source changed or temporary files leaked')
            report['checks'].append({'case':kind,'snapshot':status,'receipt':response,'native_output_sha256':sha(destination),'accepted_output_sha256':spec['native_output_sha256'],'observations':observations,'expected_failures':failures,'pre_cancelled_retained_jobs':len(retained),'final_admission':final,'peak_RSS_bytes':rss,'controller_transcript':c.transcript});report.pop('active_case_observation',None)
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during run');check_lock();report['stage']='complete';report['status']='six_full_converters_shared_runtime_passed_M2_closeout_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
        if active is not None:
            active.abort();report['controller_transcript_on_failure']=active.transcript
            if active.stderr.exists():report['controller_stderr_tail']=active.stderr.read_text()[-64000:]
    path=out/'m2-full-converters-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_full_converters_failed')
if __name__=='__main__':raise SystemExit(main())
