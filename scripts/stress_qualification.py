"""Bounded offline stress, measured Rust RSS and staged-failure qualification.

POSIX wait4 measures the actual Rust executable, not cargo/compiler memory.
RSS sampling is a watchdog, not a guaranteed allocator or OS memory limit.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from patched_interop import ROOT, require, experiment_command, verify_candidate_source
from real_corpus import file_hash, connect, differences
from real_rebuild import run, scan
from v2_audit import audit

PRESETS = {
    'standard':{'entries':49152,'body_bytes':1024,'resources':128,'resource_bytes':131072},
    'quick':{'entries':2048,'body_bytes':512,'resources':16,'resource_bytes':4096},
}


def rss_bytes(value,platform):
    return int(value) if platform=='darwin' else int(value)*1024


def monitored(command,prefix,timeout,rss_limit,terminate_when=None):
    """Return per-child peak RSS and exit status, always reap the process."""
    require(hasattr(os,'wait4'),'Exact per-child RSS measurement requires POSIX wait4')
    start=time.monotonic();reason=None;sampled=0;usage=None;status=None
    with Path(str(prefix)+'.stdout').open('wb') as stdout,Path(str(prefix)+'.stderr').open('wb') as stderr:
        process=subprocess.Popen(list(map(str,command)),cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            while True:
                pid,state,detail=os.wait4(process.pid,os.WNOHANG)
                if pid:status=state;usage=detail;break
                if reason is None:
                    try:
                        reading=subprocess.run(['ps','-o','rss=','-p',str(process.pid)],capture_output=True,text=True,timeout=2)
                        if reading.returncode==0 and reading.stdout.strip():sampled=max(sampled,int(reading.stdout.strip())*1024)
                    except (OSError,ValueError,subprocess.TimeoutExpired):pass
                    if sampled>rss_limit:reason='rss_watchdog'
                    elif time.monotonic()-start>timeout:reason='timeout'
                    elif terminate_when is not None and terminate_when.is_file():reason='injected_termination'
                    if reason is not None:
                        try:os.killpg(process.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                time.sleep(0.05)
        finally:
            if usage is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                _,status,usage=os.wait4(process.pid,0)
            process.returncode=os.waitstatus_to_exitcode(status)
    peak=rss_bytes(usage.ru_maxrss,sys.platform)
    return {'returncode':process.returncode,'termination':reason,'peak_rss_bytes':peak,
            'sampled_peak_rss_bytes':sampled,'elapsed_seconds':round(time.monotonic()-start,3),
            'rss_within_budget':peak<=rss_limit,'stdout':Path(str(prefix)+'.stdout').name,
            'stderr':Path(str(prefix)+'.stderr').name}


def key_block_offset(data):
    size=struct.unpack_from('>I',data,0)[0];pos=size+8
    require(2<=size<=1024*1024 and pos+44<=len(data),'Bad diagnostic header geometry')
    blocks,count,raw_size,compressed_info,key_size=struct.unpack_from('>5Q',data,pos)
    offset=pos+44+compressed_info
    require(blocks>0 and count>0 and offset+8<=len(data) and key_size>=8,'Bad diagnostic key geometry')
    return pos,offset


def damaged_copy(source,destination,kind):
    data=bytearray(source.read_bytes())
    require(len(data)<8*1024*1024,'Fault mutation only accepts the small synthetic seed')
    pos,block=key_block_offset(data)
    if kind=='truncated':data=data[:-17]
    elif kind=='invalid_compression':data[block:block+4]=b'\xff'*4
    elif kind=='oversized_declaration':
        struct.pack_into('>QQQ',data,pos,2**64-1,2**64-1,2**64-1)
        struct.pack_into('>I',data,pos+40,zlib.adler32(data[pos:pos+40])&0xffffffff)
    elif kind=='checksum_only':data[block+4]^=1
    else:raise ValueError('Unknown synthetic damage')
    destination.write_bytes(data)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--profile',choices=PRESETS,default='standard')
    parser.add_argument('--rss-limit-mib',type=int,default=768)
    parser.add_argument('--timeout',type=float,default=600)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','profile':args.profile,'checks':{},'processes':{},'native_readers':'NOT_RUN_DO_NOT_IMPORT',
        'rss_limit_mib':args.rss_limit_mib,'build_profile':'debug; not a release-performance benchmark',
        'rss_scope':'Direct stress/fault Rust jobs only; excludes Cargo/compiler, separate dump-rows scans and Python readers',
        'not_proven':['production_allocator_limit','power_loss_recovery','every_corruption_class','Windows_memory_qualification',
                      'native_large_dictionary_rendering','production_checksum_policy','fresh_TXT_XLSX_pack_parity','general_metadata_sort_policy','M1_completion']}
    originals={}
    try:
        require(hasattr(os,'wait4') and os.name=='posix','This RSS qualification driver requires macOS/Linux POSIX wait4')
        require(128<=args.rss_limit_mib<=2048 and args.timeout>0,'Use RSS budget 128..2048 MiB and a positive timeout')
        require(shutil.disk_usage(out).free>=512*1024*1024,'At least 512 MiB free space is required for this bounded preset')
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Expected mdict-utils 1.3.14')
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        report['source_sha256']={str(p.relative_to(ROOT)):file_hash(p) for p in
            [vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',
             ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/stress.rs',
             ROOT/'experiments/real-rebuild/Cargo.lock',Path(__file__).resolve()]}
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        build_output=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'cargo-build.log',args.timeout)
        executables=[r['executable'] for line in build_output.splitlines() if line.startswith('{')
            for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')]
        require(len(set(executables))==1,'Cannot identify the built Rust executable');binary=Path(executables[0])
        report['binary_sha256']=file_hash(binary)
        def job(name,arguments,expected_success=True,terminate_when=None):
            detail=monitored([binary,*arguments],out/name,args.timeout,args.rss_limit_mib*1024*1024,terminate_when)
            report['processes'][name]=detail
            require(detail['rss_within_budget'] and detail['termination'] not in {'timeout','rss_watchdog'},f'{name} exceeded RSS/time budget')
            if expected_success:
                require(detail['returncode']==0 and detail['termination'] is None,f'{name} failed; see stderr')
                return json.loads((out/detail['stdout']).read_text(encoding='utf-8'))
            if terminate_when is None:require(detail['returncode']==1,f'{name} did not reject cleanly (panic/signal is not a pass)')
            else:require(detail['returncode']==-signal.SIGKILL,f'{name} did not terminate with the injected signal')
            return detail
        spec=out/'stress-spec.json';spec.write_text(json.dumps(PRESETS[args.profile])+'\n')
        report['preset']=PRESETS[args.profile]
        report['build']=job('stress-build',['stress-build',spec,out/'generated'])
        report['verification']=job('stress-verify',['stress-verify',spec,out/'generated'])
        for extension in ['mdx','mdd']:
            path=out/'generated'/f'stress.{extension}';originals[str(path)]=file_hash(path)
            observation=audit(path);require(observation['status']=='structural_audit_passed','Independent large-file structural audit failed')
            require(observation['key_blocks']>1 and observation['record_blocks']>1,'Stress fixture did not cross both block boundaries')
            db=connect(out/f'{extension}-comparison.sqlite')
            try:
                scans={}
                for reader,command in [('r',experiment_command(6,'dump-rows',path)),
                    ('p',[sys.executable,ROOT/'scripts/real_corpus.py','python-rows',path])]:
                    scans[reader]=scan(command,db,reader,extension,out/f'{extension}-{reader}.log',args.timeout)
                require(differences(db)==0 and scans['r']['attributes']==scans['p']['attributes'],'Stress Rust/Python multiset or metadata mismatch')
                require(scans['r']['ordered_key_payload_sha256']==scans['p']['ordered_key_payload_sha256'],'Stress physical order differs')
            finally:db.close()
            report['checks'][f'{extension}_full_comparison']={'status':'passed','structural_audit':observation,'scans':scans}
        full_size=(out/'generated/stress.mdx').stat().st_size
        report['mdx_file_bytes']=full_size
        if args.profile=='standard':require(full_size>32*1024*1024,'Standard fixture did not exceed the 32 MiB prior-rebuild file budget')
        # Small seed keeps all damage tests cheap and bounded.
        seed_spec=out/'seed-spec.json';seed_spec.write_text(json.dumps({'entries':128,'body_bytes':128,'resources':8,'resource_bytes':256})+'\n')
        job('seed-build',['stress-build',seed_spec,out/'seed'])
        seed=out/'seed/stress.mdx';originals[str(seed)]=file_hash(seed)
        faults=out/'faults';faults.mkdir()
        for kind in ['truncated','invalid_compression','oversized_declaration']:
            target=faults/(kind+'.mdx');damaged_copy(seed,target,kind)
            detail=job(kind,['stress-inspect',target],expected_success=False)
            report['checks'][kind]={'status':'passed_rejected','process':detail}
        checksum=faults/'checksum_only.mdx';damaged_copy(seed,checksum,'checksum_only')
        # Reader default policy is observed, not assumed to enforce all checksums.
        detail=monitored([binary,'stress-inspect',checksum],out/'checksum-default',args.timeout,args.rss_limit_mib*1024*1024)
        report['processes']['checksum-default']=detail
        require(detail['rss_within_budget'] and detail['termination'] is None,'Checksum observation exceeded budget')
        require(detail['returncode'] in {0,1},'Checksum observation panicked or crashed')
        checksum_audit=audit(checksum);error=checksum_audit.get('error','').lower()
        require(checksum_audit['status']=='failed' and ('checksum' in error or 'adler32' in error),'Independent auditor did not reject checksum mutation')
        report['checks']['checksum_policy']={'status':'auditor_rejected_reader_behavior_observed','reader_accepted':detail['returncode']==0,
            'auditor_error':checksum_audit.get('error'),'qualification':'Production checksum policy remains a separate decision'}
        failed=out/'failed-write';detail=job('injected-write',['stress-fail-write',failed],expected_success=False)
        require('injected write failure' in (out/detail['stderr']).read_text(encoding='utf-8').lower() and not failed.exists(),'Write-error cleanup/publication invariant failed')
        report['checks']['write_error_no_publication']={'status':'passed','simulation':'Injected I/O error; not a physically full disk'}
        existing=out/'overwrite-target';existing.mkdir();sentinel=existing/'keep';sentinel.write_bytes(b'preserve existing destination')
        before=file_hash(sentinel);job('refuse-overwrite',['stress-build',seed_spec,existing],expected_success=False)
        require(file_hash(sentinel)==before and set(p.name for p in existing.iterdir())=={'keep'},'Existing destination was modified')
        report['checks']['overwrite_refused']={'status':'passed'}
        with tempfile.TemporaryDirectory(prefix='owned-cancel-',dir=out) as temporary:
            owned=Path(temporary);destination=owned/'unpublished';ready=owned/'ready'
            detail=job('forced-termination',['stress-hold',destination,ready],expected_success=False,terminate_when=ready)
            require(detail['termination']=='injected_termination' and not destination.exists(),'Forced termination published partial output')
        require(not owned.exists(),'Controller did not clean its own abandoned staging workspace')
        report['checks']['forced_termination_cleanup']={'status':'passed','scope':'No published destination; controller cleans owned staging after killed child'}
        job('recovery-build',['stress-build',seed_spec,out/'recovery'])
        job('recovery-verify',['stress-verify',seed_spec,out/'recovery'])
        report['checks']['fresh_job_after_failures']={'status':'passed'}
        if args.profile=='standard':
            over=out/'oversize-rebuild';detail=job('rebuild-input-limit',[out/'generated/stress.mdx',over],expected_success=False)
            require('input limit' in (out/detail['stderr']).read_text(encoding='utf-8').lower() and not over.exists(),'32 MiB rebuild preset was not enforced')
            report['checks']['prior_rebuild_limit_enforced']={'status':'passed','note':'Larger engine I/O succeeds while the conservative real-rebuild preset still refuses >32 MiB'}
        report['status']='standard_stress_subset_passed_M1_open' if args.profile=='standard' else 'quick_smoke_passed_not_large_file_qualification'
    except Exception as error:
        if report['processes']:report['status']='failed_stress_qualification'
        report['error']=str(error)
    finally:
        report['generated_input_integrity']={name:{'before':checksum,'after':file_hash(Path(name)) if Path(name).is_file() else None} for name,checksum in originals.items()}
        if any(v['before']!=v['after'] for v in report['generated_input_integrity'].values()):report['status']='failed_generated_input_integrity'
        (out/'stress-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"{report['status']}: {out/'stress-report.json'}")
    return 0 if report['status'] in {'standard_stress_subset_passed_M1_open','quick_smoke_passed_not_large_file_qualification'} else 1


if __name__=='__main__':raise SystemExit(main())
