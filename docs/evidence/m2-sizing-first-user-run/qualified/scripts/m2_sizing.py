"""First production-sizing gate: explicit engine caps and lazy streaming reads."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import signal
import shutil
import subprocess
import sys
import traceback
from m2_v2_import import ROOT,require
from bounded_engine_lock import MANIFEST,LOCK,check_lock
from bounded_fixtures import write,mutate
from v2_audit import audit
from v2_import_fixtures import read_legacy_physical

RSS_TARGET=384*1024*1024
class CommandTimeout(RuntimeError):
    def __init__(self,stdout,stderr):
        super().__init__('Sizing command exceeded 300 seconds; its process group was terminated')
        self.output_tail=(stdout+'\nSTDERR:\n'+stderr)[-64000:]
def timed_run(command,env=None):
    process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',start_new_session=os.name=='posix')
    try:stdout,stderr=process.communicate(timeout=300)
    except (subprocess.TimeoutExpired,KeyboardInterrupt) as interruption:
        if os.name=='posix':
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        else:process.kill()
        stdout,stderr=process.communicate()
        if isinstance(interruption,KeyboardInterrupt):raise
        raise CommandTimeout(stdout,stderr)
    return subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(65536):h.update(data)
    return h.hexdigest()
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-metadata-jobs-user-run/m2-metadata-jobs-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for name,digest in expected.items():require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return expected
def fingerprints(include_lock=True):
    paths=[p for p in (ROOT/'m2/bounded-engine').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/bounded-engine').parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/name for name in ['bounded_engine_lock.py','bounded_fixtures.py','m2_sizing.py','test_m2_sizing.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def peak_rss(stderr,system):
    if system=='Darwin':
        match=re.search(r'^\s*(\d+)\s+maximum resident set size\s*$',stderr,re.M)
        if not match:raise AssertionError('macOS /usr/bin/time -l RSS measurement missing')
        return int(match[1])
    match=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',stderr)
    if not match:raise AssertionError('time -v RSS measurement missing')
    return int(match[1])*1024
def compare_success(actual,fixture,query_error=False):
    require(actual['profile']=='bounded-lazy-scan-v1' and actual['lookup_policy']=='raw-exact-bounded-scan-v1','Wrong bounded lookup profile')
    require(actual['scan']==fixture['scan'],'Streamed count/bytes/framed payload fingerprint differ')
    memory=actual['memory'];require(memory['locator']==0 and memory['peak']<=memory['budget']<=64*1024*1024,'Locator allocated or parser accounting cap exceeded')
    require([q['query'] for q in actual['queries']]==list(fixture['queries']),'Missing or reordered queries')
    for q in actual['queries']:
        if query_error and q['query']=='row00000000':require(q.get('error',{}).get('code')=='limit_exceeded' and 'rows' not in q,'Result cap returned partial duplicate set')
        else:require(q.get('rows')==fixture['queries'][q['query']] and 'error' not in q,'Raw-exact lookup changed physical order/payload or used implicit fallback')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_sizing_failed','M1':'complete_unchanged','M2_complete':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'first isolated bounded-reader sizing gate; complete streaming v2 validation, explicit parser caps, raw-exact bounded scan lookup, no locator/global owned entry vector',
        'production_readiness':False,'RSS_observation_target_bytes':RSS_TARGET,'RSS_is_OS_limit':False,'native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False):
        print(f'Running {label}',flush=True);r=timed_run(command);combined=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(label+'.log')).write_text(combined)
        step={'name':label,'returncode':r.returncode};report['steps'].append(step)
        if r.returncode:step['failure_log_tail']=combined[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded log tail');return json.loads(r.stdout) if parse else None
    try:
        report['stage']='preflight';require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing .venv mdict-utils==1.3.14');report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac');require(Path('/usr/bin/time').is_file(),'Require /usr/bin/time for process RSS measurement')
        report['stage']='rust_tests';run('refresh-bounded-artifacts',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-bounded-engine'])
        try:run('bounded-reader-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        require({k:v for k,v in fingerprints().items() if k!=LOCK}=={k:v for k,v in report['source_sha256'].items() if k!=LOCK},'Non-lock source changed during compilation')
        run('build-bounded-reader',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-bounded-engine'])
        binary=ROOT/'m2/bounded-engine/target/debug/studio-bounded-engine';binary=binary.with_suffix('.exe') if os.name=='nt' else binary;report['binary_sha256']=sha(binary)
        inputs=out/'inputs';inputs.mkdir();fixtures=[];report['stage']='fixture_generation'
        for name,count,kind,encoding,size,compressed in [
            ('small-utf8',100,'mdx','utf8',128,True),('small-utf16',100,'mdx','utf16',128,True),('small-mdd',100,'mdd','utf8',128,True),
            ('plain-blocks',100,'mdx','utf8',128,False),('medium-utf16',65536,'mdx','utf16',256,True),('large-utf8',262144,'mdx','utf8',256,True),('medium-mdd',65536,'mdd','utf8',256,True)]:
            print(f'Preparing {name}: {count} records',flush=True);f=write(inputs/(name+'.'+kind),count,kind,encoding,size,compression=compressed);f['name']=name;fixtures.append(f)
            if count<=100:
                require(audit(f['path'])['status']=='structural_audit_passed','Stdlib fixture failed independent wire audit')
                rows=read_legacy_physical(f['path'],kind);require(len(rows)==count,'Small fixture Python reader count differs')
                for query,expected in f['queries'].items():require([(r['key'],r.get('text',bytes(r.get('bytes',[])))) for r in expected]==[(k,v) for k,v in rows if k==query],'Small fixture query oracle differs from Python')
        cases=[{'name':f['name'],'fixture':f} for f in fixtures];small=fixtures[0]
        cases += [
            {'name':'query-result-count','fixture':small,'tighten':{'max_matches':1},'query_error':True},
            {'name':'tiny-working-budget','fixture':small,'tighten':{'working_memory':1},'refuse':['limit_exceeded']},
            {'name':'tiny-key-index','fixture':small,'tighten':{'key_index':1},'refuse':['limit_exceeded']},
            {'name':'tiny-record-index','fixture':small,'tighten':{'record_index':1},'refuse':['limit_exceeded']},
            {'name':'tiny-compressed-block','fixture':small,'tighten':{'compressed_block':1},'refuse':['limit_exceeded']},
            {'name':'tiny-decoded-block','fixture':small,'tighten':{'decoded_block':1},'refuse':['limit_exceeded']},
            {'name':'tiny-materialization','fixture':small,'tighten':{'materialized_record':1},'refuse':['limit_exceeded']},
            {'name':'tiny-application-count','fixture':small,'tighten':{'max_rows':1},'refuse':['limit_exceeded']},
            {'name':'tiny-scan-bytes','fixture':small,'tighten':{'scan_bytes':1},'refuse':['limit_exceeded']},
            {'name':'tiny-file-cap','fixture':small,'tighten':{'file_bytes':1},'refuse':['limit_exceeded']},
            {'name':'cancel-snapshot','fixture':small,'cancel_phase':'snapshot','refuse':['cancelled']},
            {'name':'cancel-scan','fixture':small,'cancel_phase':'bounded_scan','refuse':['cancelled']},
            {'name':'cancel-lookup','fixture':small,'cancel_phase':'bounded_lookup','refuse':['cancelled']},
        ]
        for mode in ['header_length','key_info_packed','key_info_decoded','key_block_entries','record_declared_decoded','key_block_checksum','record_block_checksum','truncated']:
            path=mutate(small['path'],inputs/('bad-'+mode+'.mdx'),mode)
            codes=['integrity'] if mode.endswith('checksum') else ['limit_exceeded','engine','integrity','io']
            cases.append({'name':'bad-'+mode,'fixture':{**small,'path':path},'refuse':codes})
        # A genuine oversized record, not just an impossible declared extent.
        huge=write(inputs/'oversized-record.mdx',1,payload_size=3*1024*1024);cases.append({'name':'oversized-record','fixture':huge,'refuse':['limit_exceeded']})
        scratch=out/'private-scratch';scratch.mkdir();system=platform.system();time_args=['/usr/bin/time','-l' if system=='Darwin' else '-v'];env=dict(os.environ);env['TMPDIR']=str(scratch);env['LC_ALL']='C'
        for case in cases:
            report['stage']=case['name'];f=case['fixture'];path=out/(case['name']+'-request.json');request={'path':str(f['path']),'kind':f['kind'],'queries':list(f['queries']),'tighten':case.get('tighten',{}),'cancel_phase':case.get('cancel_phase')};path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n');before=sha(f['path'])
            print(f'Measuring {case["name"]}',flush=True);r=timed_run(time_args+[str(binary),str(path)],env)
            (out/(case['name']+'.log')).write_text(r.stdout+'\nSTDERR:\n'+r.stderr);rss=peak_rss(r.stderr,system);step={'name':case['name'],'returncode':r.returncode,'peak_RSS_bytes':rss};report['steps'].append(step)
            require(rss<=RSS_TARGET,f'{case["name"]} exceeded provisional observed-RSS target: {rss}');require(not list(scratch.iterdir()),'Private snapshot residue remains after reader exit');require(sha(f['path'])==before,'Reader changed input file')
            if case.get('refuse'):
                errors=[json.loads(line) for line in r.stderr.splitlines() if line.startswith('{')];require(r.returncode==1 and not r.stdout.strip() and len(errors)==1,'Expected complete typed refusal, with no partial stdout')
                error=errors[0]['error'];require(error['code'] in case['refuse'],f'{case["name"]}: unexpected failure {error}')
                report['checks'].append({'case':case['name'],'status':'expected_refusal','error':error,'input_sha256':before,'peak_RSS_bytes':rss})
            else:
                if r.returncode:step['failure_log_tail']=r.stderr[-64000:]
                require(r.returncode==0,f'{case["name"]} failed; return log');actual=json.loads(r.stdout);(out/(case['name']+'-actual.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n');compare_success(actual,f,case.get('query_error',False))
                report['checks'].append({'case':case['name'],'status':'stream_scan_queries_memory_passed','input_sha256':before,'file_bytes':f['path'].stat().st_size,'scan':actual['scan'],'parser_memory':actual['memory'],'peak_RSS_bytes':rss,'query_result_cap_checked':case.get('query_error',False)})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Source identities changed during sizing');check_lock();report['status']='m2_bounded_reader_first_sizing_gate_passed_larger_path_integration_pending';report['stage']='complete'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
    path=out/'m2-sizing-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_sizing_failed')
if __name__=='__main__':raise SystemExit(main())
