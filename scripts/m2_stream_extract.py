"""Qualify bounded span-based MDD extraction, staged bytes and exclusive publication."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import traceback
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,RSS_TARGET,CommandTimeout
from stream_extract_lock import MANIFEST,LOCK,check_lock
from stream_mdd_fixtures import write
from bounded_fixtures import mutate
from v2_import_fixtures import rewrite
from v2_audit import audit

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-sessions-user-run/m2-sessions-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previous qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    d=ROOT/'m2/stream-extract';paths=[p for p in d.rglob('*') if p.is_file() and 'target' not in p.relative_to(d).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['stream_extract_lock.py','stream_mdd_fixtures.py','m2_stream_extract.py','test_m2_stream_extract.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def tree(path):
    files={};directories=set()
    for p in path.rglob('*'):
        require(not p.is_symlink(),'Extraction contains a symlink');relative=p.relative_to(path).as_posix()
        if p.is_file():files[relative]={'bytes':p.stat().st_size,'sha256':sha(p)}
        elif p.is_dir():directories.add(relative)
        else:raise AssertionError('Unexpected filesystem object')
    return files,directories
def compare(receipt,fixture,destination):
    require(receipt['profile']=='mdd-stream-extract-v1' and receipt['source_sha256']==sha(fixture['path']),'Extraction source/profile binding differs')
    for field in ['resources','payload_bytes','largest_resource_bytes','framed_resources_sha256']:require(receipt[field]==fixture[field],f'Extraction {field} differs')
    require(receipt['locator_bytes']==0 and receipt['materialized_record_limit']==0 and receipt['parser_peak_bytes']<=receipt['parser_budget_bytes']<=64*1024*1024,'Extractor materialized a record, allocated a locator or exceeded parser accounting')
    require(receipt['plan_charge']<=16*1024*1024 and receipt['planned_nodes']<=200000,'Extraction path-plan limits exceeded')
    expected={r['relative']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in fixture['expected']};files,dirs=tree(destination);wantdirs=set()
    for name in expected:
        parent=Path(name).parent
        while str(parent)!='.':wantdirs.add(parent.as_posix());parent=parent.parent
    require(files==expected and dirs==wantdirs,'Published paths, file hashes, empty files or directory set differs')
    return files
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_stream_extract_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'native_readers':'NOT_REQUESTED','platform':platform.platform(),'steps':[],'checks':[],'scope':'standalone unencrypted v2 MDD span extraction; no full resource materialization; first bounded staged-output gate'}
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Require Rust-enabled Mac')
        def run(name,cmd):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(cmd);step={'name':name,'returncode':r.returncode};report['steps'].append(step);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        run('refresh-extract-artifacts',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-stream-extract'])
        try:run('stream-extract-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        run('build-stream-extract',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-stream-extract']);binary=ROOT/'m2/stream-extract/target/debug/studio-stream-extract';report['binary_sha256']=sha(binary)
        inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();scratch=out/'private-scratch';scratch.mkdir();env=dict(os.environ);env.update(TMPDIR=str(scratch),LC_ALL='C');cases=[]
        for name,size,compressed in [('cross-block',200000,True),('large-resource',32*1024*1024+7,True),('plain-blocks',8*1024*1024+3,False)]:
            print(f'Preparing {name}',flush=True);f=write(inputs/(name+'.mdd'),[{'key':'\\assets\\prefix.bin','bytes':17,'seed':11},{'key':'assets/字-مرحبا-𠀀.bin','bytes':size,'seed':37},{'key':'empty.bin','bytes':0}],compressed);a=audit(f['path']);require(a['status']=='structural_audit_passed','Independent streaming fixture audit failed');require([(r['path'],r['bytes'],r['sha256']) for r in a['resources']]==[(r['key'],r['bytes'],r['sha256']) for r in f['expected']],'Independent fixture resource hashes differ');cases.append({'name':name,'fixture':f})
        many=write(inputs/'many.mdd',[{'key':f'files/r{i:05d}.bin','bytes':256,'seed':i} for i in range(4096)]);require(audit(many['path'])['status']=='structural_audit_passed','Many-file fixture audit failed');cases.append({'name':'many-files','fixture':many});small=cases[0]['fixture'];large=cases[1]['fixture']
        for name,keys,code in [('traversal',['../escape.bin'],'unsafe_path'),('device',['CON.txt'],'unsafe_path'),('case-alias',['a.bin','A.bin'],'path_collision'),('duplicate',['a','a'],'path_collision'),('prefix-conflict',['a','a/b'],'path_collision'),('unc',['//server/share'],'unsafe_path')]:
            f=write(inputs/(name+'.mdd'),[{'key':k,'bytes':3} for k in keys]);cases.append({'name':name,'fixture':f,'refusal':code})
        for name,tighten in [('count-cap',{'resources':1}),('per-resource-cap',{'resource_bytes':100}),('output-cap',{'output_bytes':100}),('plan-cap',{'plan_charge':1}),('node-cap',{'nodes':1}),('file-cap',{'file_bytes':1}),('working-cap',{'working_memory':1}),('block-cap',{'decoded_block':1})]:cases.append({'name':name,'fixture':small,'tighten':tighten,'refusal':'limit_exceeded'})
        for phase,after in [('snapshot',0),('plan_paths',1),('copy_resource',65536),('verify_file',65536),('publish_directory',0)]:cases.append({'name':'cancel-'+phase,'fixture':large,'cancel_phase':phase,'cancel_after':after,'refusal':'cancelled'})
        for mode in ['key_block_checksum','record_block_checksum','record_declared_decoded','truncated']:
            bad=mutate(small['path'],inputs/('bad-'+mode+'.mdd'),mode);cases.append({'name':'bad-'+mode,'fixture':{**small,'path':bad},'refusal':'integrity' if mode.endswith('checksum') else ['limit_exceeded','engine','io','integrity']})
        for name,attributes in [('v3',{'GeneratedByEngineVersion':'3.0','RequiredEngineVersion':'3.0'}),('encrypted',{'Encrypted':'2'})]:
            bad=inputs/(name+'.mdd');bad.write_bytes(rewrite(small['path'].read_bytes(),attributes));cases.append({'name':name,'fixture':{**small,'path':bad},'refusal':'unsupported_policy'})
        cases.append({'name':'existing-destination','fixture':small,'existing':True,'refusal':'destination_exists'})
        for case in cases:
            name=case['name'];report['stage']=name;print(f'Checking {name}',flush=True);f=case['fixture'];destination=outputs/name
            if case.get('existing'):destination.mkdir();(destination/'sentinel').write_bytes(b'keep')
            baseline_tree=tree(destination) if destination.exists() else None;before=set(outputs.iterdir());source_hash=sha(f['path']);request={'source':str(f['path']),'destination':str(destination),'tighten':case.get('tighten',{}),'cancel_phase':case.get('cancel_phase'),'cancel_after':case.get('cancel_after',0)};request_path=out/(name+'-request.json');request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
            r=timed_run(['/usr/bin/time','-l' if platform.system()=='Darwin' else '-v',str(binary),str(request_path)],env);(out/(name+'.log')).write_text(r.stdout+'\nSTDERR:\n'+r.stderr);rss=peak_rss(r.stderr,platform.system());step={'name':name,'returncode':r.returncode,'peak_RSS_bytes':rss};report['steps'].append(step);require(0<rss<=RSS_TARGET,'Observed extractor RSS exceeds provisional threshold');require(not list(scratch.iterdir()),'Source snapshot residue remains');require(sha(f['path'])==source_hash,'Extractor changed input file')
            if case.get('refusal'):
                errors=[json.loads(line)['error'] for line in r.stderr.splitlines() if line.startswith('{')];codes=case['refusal'] if isinstance(case['refusal'],list) else [case['refusal']];require(r.returncode==1 and not r.stdout.strip() and len(errors)==1 and errors[0]['code'] in codes,f'{name}: expected refusal, got {r.stderr[:3000]}');require(set(outputs.iterdir())==before,'Failed extraction left staging or destination');require((tree(destination) if destination.exists() else None)==baseline_tree,'Failed extraction changed pre-existing output');report['checks'].append({'case':name,'status':'expected_refusal','error':errors[0],'source_sha256':source_hash,'peak_RSS_bytes':rss})
            else:
                if r.returncode:step['failure_log_tail']=(r.stdout+'\n'+r.stderr)[-64000:]
                require(r.returncode==0,f'{name} extraction failed; return log');actual=json.loads(r.stdout);require(actual['status']=='published','Extraction did not report publication');files=compare(actual['receipt'],f,destination);require(set(outputs.iterdir())==before|{destination},'Unexpected sibling output/stage residue');report['checks'].append({'case':name,'status':'streamed_files_verified','source_sha256':source_hash,'actual':actual,'files':files,'peak_RSS_bytes':rss,'record_blocks':f['record_blocks']})
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during extraction qualification');check_lock();report['stage']='complete';report['status']='m2_streaming_MDD_extraction_passed_larger_integration_pending'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
    path=out/'m2-stream-extract-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_stream_extract_failed')
if __name__=='__main__':raise SystemExit(main())
