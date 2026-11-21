"""Qualify content-bound frozen-policy disk indexes and complete bounded pages."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import traceback
import unicodedata
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,CommandTimeout,RSS_TARGET
from index_engine_lock import MANIFEST,LOCK,check_lock
from index_fixtures import make,expected_page,corrupt
from bounded_fixtures import write,rows as generated_rows
from v2_import_fixtures import rewrite,read_legacy_physical
from v2_audit import audit

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-sizing-user-run/m2-sizing-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Prior qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/indexed-engine';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['index_engine_lock.py','index_fixtures.py','m2_index.py','test_m2_index.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def compare(actual,fixture,queries,policy):
    require(actual['status']=='queried' and actual['revision']=='studio-disk-index-v1-frozen16','Wrong index response identity')
    require(actual['manifest']['source_sha256']==sha(fixture['path']) and actual['manifest']['policy']==policy,'Source/policy binding differs')
    require(actual['memory']['locator']==0 and actual['memory']['peak']<=actual['memory']['budget']<=64*1024*1024,'Index reader allocated locator or exceeded parser accounting')
    require(len(actual['results'])==len(queries),'Missing page response')
    for result,q in zip(actual['results'],queries):
        want=expected_page(fixture['rows'],q['query'],q['offset'],q['limit'],policy,fixture.get('sensitive',False),fixture.get('strip',False),fixture['kind'])
        require(result['query']==q['query'] and result['page']==want,f'Incorrect complete page: {q}')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_index_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'platform':platform.platform(),'unicode_version':unicodedata.unidata_version,'scope':'isolated Studio disk index v1, source SHA-256 binding, frozen16 exact-first paged lookup; full open/attach validation remains linear'}
    try:
        require(unicodedata.unidata_version=='16.0.0','Use existing Python 3.14 venv with Unicode16 for independent normalization oracle')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Require Rust-enabled Mac')
        def command(name,cmd):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(cmd);(out/(name+'.log')).write_text(r.stdout+'\nSTDERR:\n'+r.stderr);s={'name':name,'returncode':r.returncode};report['steps'].append(s)
            if r.returncode:s['failure_log_tail']=(r.stdout+'\n'+r.stderr)[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log available')
        command('refresh-index-artifacts',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-indexed-engine'])
        try:command('index-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        command('build-index-cli',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-indexed-engine'])
        binary=ROOT/'m2/indexed-engine/target/debug/studio-indexed-engine';report['binary_sha256']=sha(binary)
        inputs=out/'inputs';inputs.mkdir();caches=out/'caches';caches.mkdir();scratch=out/'private-scratch';scratch.mkdir();env=dict(os.environ);env.update(TMPDIR=str(scratch),LC_ALL='C');time=['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v']
        def invoke(name,fixture,artifact,policy='header_ascii_v1',action='query',queries=None,refusal=None,**extra):
            report['stage']=name;request={'path':str(fixture['path']),'kind':fixture['kind'],'artifact':str(artifact),'policy':policy,'action':action,'queries':queries or [],**extra};path=out/(name+'-request.json');path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n');before_source=sha(fixture['path']);before_cache=sha(artifact) if artifact.exists() else None;prior_cache_files={x.name for x in caches.iterdir()}
            print(f'Checking {name}',flush=True);r=timed_run(time+[str(binary),str(path)],env);(out/(name+'.log')).write_text(r.stdout+'\nSTDERR:\n'+r.stderr);rss=peak_rss(r.stderr,platform.system());step={'name':name,'returncode':r.returncode,'peak_RSS_bytes':rss};report['steps'].append(step)
            require(0<rss<=RSS_TARGET,'Observed reader RSS exceeds provisional 384 MiB threshold');require(sha(fixture['path'])==before_source,'Source changed');require(not list(scratch.iterdir()),'Private snapshot residue');require({x.name for x in caches.iterdir()}==prior_cache_files|({artifact.name} if action=='build' and not refusal else set()),'Cache build scratch residue or unexpected publication')
            if refusal:
                errors=[json.loads(line)['error'] for line in r.stderr.splitlines() if line.startswith('{')];require(r.returncode==1 and not r.stdout.strip() and len(errors)==1 and errors[0]['code']==refusal,f'{name}: expected {refusal}, got {r.stderr[:2000]}')
                require((sha(artifact) if artifact.exists() else None)==before_cache,'Failed request modified or published cache')
                report['checks'].append({'case':name,'status':'expected_refusal','error':errors[0],'source_sha256':before_source,'peak_RSS_bytes':rss});return None
            if r.returncode:step['failure_log_tail']=(r.stdout+'\n'+r.stderr)[-64000:]
            require(r.returncode==0,f'{name} failed; return log');actual=json.loads(r.stdout)
            if action=='build':
                require(actual['status']=='published' and actual['receipt']['manifest']['source_sha256']==before_source and actual['receipt']['manifest']['policy']==policy,'Published receipt/source binding differs')
                require(actual['receipt']['bytes']==artifact.stat().st_size and actual['receipt']['initial_runs']>=2,'Published bytes/run count differs')
            else:
                compare(actual,fixture,queries,policy);require(sha(artifact)==before_cache,'Read-only query changed cache')
            report['checks'].append({'case':name,'status':'published' if action=='build' else 'pages_passed','source_sha256':before_source,'artifact_sha256':sha(artifact),'peak_RSS_bytes':rss,'actual':actual});return actual
        fixtures=[]
        for encoding in ['utf8','utf16']:
            for strip in [False,True]:
                for sensitive in [False,True]:
                    name=f'{encoding}-strip{int(strip)}-case{int(sensitive)}';f=make(inputs/(name+'.mdx'),encoding,strip,sensitive);fixtures.append(f)
                    require(audit(f['path'])['status']=='structural_audit_passed','Independent fixture wire audit failed');physical=read_legacy_physical(f['path'],'mdx');require(physical==f['rows'],'Independent legacy physical records differ')
                    cache=caches/(name+'.idx');invoke(name+'-build',f,cache,action='build',run_records=32)
                    queries=[{'query':q,'offset':0,'limit':4} for q in ['apple','Apple','APPLE','a?b','A B','ΣΟΣ','σος','i\u0307','مرحبا','字','𠀀','\U00010d70','alias','absent']]
                    invoke(name+'-lookup',f,cache,queries=queries)
                    pages=[{'query':'duplicate','offset':o,'limit':128} for o in [0,128,256,384,400,2**64-1]]+[{'query':'duplicate','offset':0,'limit':0}]
                    invoke(name+'-reopen-pages',f,cache,queries=pages)
        f=fixtures[0];base=caches/'utf8-strip0-case0.idx'
        raw=caches/'raw.idx';invoke('raw-build',f,raw,'raw_exact',action='build');invoke('raw-query',f,raw,'raw_exact',queries=[{'query':'APPLE','offset':0,'limit':10}])
        # Regenerated layouts test index construction and attachment at larger size.
        for name,count,kind in [('larger-mdx',65536,'mdx'),('larger-mdd',65536,'mdd')]:
            large=write(inputs/(name+'.'+kind),count,kind);large['rows']=list(generated_rows(count,kind));cache=caches/(name+'.idx');policy='raw_exact' if kind=='mdd' else 'header_ascii_v1';invoke(name+'-build',large,cache,policy,action='build')
            invoke(name+'-query',large,cache,policy,queries=[{'query':q,'offset':0,'limit':3} for q in ['row00000000','ROW00000000','字','𠀀','absent']]);del large['rows']
        mdd=write(inputs/'small.mdd',100,'mdd');mdd['rows']=list(generated_rows(100,'mdd'));mc=caches/'small-mdd.idx';invoke('mdd-build',mdd,mc,'raw_exact',action='build');invoke('mdd-query',mdd,mc,'raw_exact',queries=[{'query':'𠀀','offset':0,'limit':2}]);invoke('mdd-policy',mdd,mc,refusal='invalid_input')
        invoke('wrong-policy',f,base,'raw_exact',refusal='integrity')
        stale=inputs/'stale.mdx';stale.write_bytes(rewrite(f['path'].read_bytes(),{'Title':'Bounded fixturf'}));stat=f['path'].stat();os.utime(stale,ns=(stat.st_atime_ns,stat.st_mtime_ns));invoke('stale-same-mtime',{**f,'path':stale},base,refusal='integrity')
        for mode in ['checksum','truncated','revision','ordinal','token','extent','duplicate-ordinal']:
            bad=corrupt(base,caches/(mode+'.idx'),mode);invoke('bad-'+mode,f,bad,refusal='integrity')
        invoke('page-count-cap',f,base,queries=[{'query':'duplicate','offset':0,'limit':129}],refusal='limit_exceeded')
        invoke('page-byte-cap',f,base,queries=[{'query':'apple','offset':0,'limit':2}],page_bytes=1,refusal='limit_exceeded')
        invoke('empty-normalized',f,caches/'utf8-strip1-case0.idx',queries=[{'query':'???','offset':0,'limit':1}],refusal='integrity')
        stripped=fixtures[2];invoke('empty-normalized-query',stripped,caches/'utf8-strip1-case0.idx',queries=[{'query':'???','offset':0,'limit':1}],refusal='invalid_input')
        invoke('existing-destination',f,base,action='build',refusal='destination_exists')
        invoke('missing-cache',f,caches/'missing.idx',refusal='io')
        invoke('run-byte-cap',f,caches/'tiny-run.idx',action='build',run_bytes=1,refusal='limit_exceeded')
        for phase in ['index_runs','index_merge','index_verify','index_publish']:
            invoke('cancel-'+phase,f,caches/(phase+'.idx'),action='build',run_records=32,cancel_phase=phase,refusal='cancelled')
        for phase in ['index_snapshot','index_lookup']:
            invoke('cancel-'+phase,f,base,queries=[{'query':'apple','offset':0,'limit':2}],cancel_phase=phase,refusal='cancelled')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during qualification');check_lock();report['stage']='complete';report['status']='m2_disk_index_paged_lookup_passed_larger_integration_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
    path=out/'m2-index-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_index_failed')
if __name__=='__main__':raise SystemExit(main())
