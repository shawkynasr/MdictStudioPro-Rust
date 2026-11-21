"""Measure supported real-dictionary work and verify current database size boundaries."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import traceback
from m2_closeout import inventory
from m3_shell import ROOT,sources,ADAPTER
from verify_mdx_database import check as check_import
from m4_database_preflight import inspect_mdx,choose_mdx,sha
from verify_database_entry import inspect
from verify_database_jsonl import check as check_export

FILE_CAP=128*1024*1024
DECODED_CAP=32*1024*1024


def synthetic(path,count=100000,body_bytes=308):
    with path.open('w',encoding='utf-8',newline='\n') as f:
        for i in range(count):
            key='duplicate' if i in (0,count//2,count-1) else f'entry-{i:06d}'
            body=(f'SIZING_BODY {i:06d} '+'x'*body_bytes)[:body_bytes]
            f.write(json.dumps({'key':key,'text':body},ensure_ascii=False,separators=(',',':'))+'\n')


def profile_issue(rows):
    if not rows:return 'empty dictionary'
    if len(rows)>100000:return 'record count'
    if any(len(k.encode())>4096 or len(t.encode())>1024*1024 for k,t in rows):return 'key/body size'
    if sum(len(k.encode())+len(t.encode()) for k,t in rows)>DECODED_CAP:return 'decoded text'
    return None


def queries(rows,limit):
    key=next(k for k,_ in rows if k and '\0' not in k and len(k.encode())<=4096)
    return [{'label':name,'request':{'query':q,'prefix':prefix,'definition':definition,'offset':offset,'limit':limit}}
            for name,q,prefix,definition,offset in [
                ('browse-first',None,False,False,0),('browse-last',None,False,False,max(0,len(rows)-limit)),
                ('exact',key,False,False,0),('prefix',key[:1],True,False,0),('definition','a',False,True,0)]]


def verify_queries(rows,specs,result):
    assert result['info']['operation']=='opened'
    assert result['info']['value']['records']==len(rows)
    assert len(result['queries'])==5*len(specs)
    measurements=defaultdict(list)
    for spec in specs:
        q=spec['request'];query=q['query']
        matches=[{'rowid':str(i+1),'key':k,'text':t} for i,(k,t) in enumerate(rows)
                 if query is None or (query in t if q['definition'] else k.startswith(query) if q['prefix'] else k==query)]
        samples=[r for r in result['queries'] if r['label']==spec['label']]
        assert [r['repeat'] for r in samples]==list(range(5))
        for sample in samples:
            assert sample['reply']['operation']=='page'
            page=sample['reply']['value'];offset,limit=q['offset'],q['limit']
            assert page['rows']==matches[offset:offset+limit], 'Lookup row identity/body/order differs'
            assert page['total']==len(matches) and page['offset']==offset
            assert page['next_offset']==(offset+limit if offset+limit<len(matches) else None)
            assert page['source_sha256']==result['info']['value']['source_sha256']
            ms=sample['elapsed_ms'];assert isinstance(ms,(int,float)) and math.isfinite(ms) and ms>=0
            measurements[spec['label']].append(ms)
    assert result['admission_after_close']['active_operations']==0
    return {name:{'samples':len(v),'first_ms':v[0],'warm_median_ms':statistics.median(v[1:]),
                  'min_ms':min(v),'p95_ms':sorted(v)[math.ceil(.95*len(v))-1],'max_ms':max(v)}
            for name,v in measurements.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('m4-database-out-sizing'))
    p.add_argument('--mdx',type=Path,help='Real dictionary; omit for the macOS file picker')
    a=p.parse_args();out=a.output.resolve()
    if not out.name.startswith('m4-database-out'):p.error('Use a fresh m4-database-out-prefixed directory')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-m4-database-sizing-v2','status':'failed','native_tests_executed':False,
            'native_jobs_executed':False,'steps':[],'checks':[],
            'measurement_scope':'Adapter import, validated snapshot open, query round trip and JSONL export wall time. No GUI paint, OS cache control or RSS measurement; no universal speed threshold.',
            'machine':{'os':platform.system(),'release':platform.release(),'architecture':platform.machine()}}
    protected=current=lock_before=None;lock=ROOT/'m4/database/Cargo.lock'
    def source_hashes():return {n:h for n,h in sources().items() if '__pycache__' not in Path(n).parts and Path(n).name!='.DS_Store'}
    def run(name,command):
        report['stage']=name;print(name,flush=True)
        done=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=3600)
        (out/(name+'.log')).write_text(done.stdout+'\nSTDERR:\n'+done.stderr,encoding='utf-8')
        report['steps'].append({'name':name,'command':command,'returncode':done.returncode})
        assert done.returncode==0,f'{name} failed; see {out/(name+".log")}'
    try:
        protected,current,lock_before=inventory(),source_hashes(),lock.read_bytes()
        report.update(protected_source_sha256=protected,source_sha256=current,lock_sha256=sha(lock))
        source=(a.mdx if a.mdx is not None else choose_mdx()).expanduser().absolute()
        assert source.suffix.lower()=='.mdx' and source.is_file() and not source.is_symlink(),'Choose a regular MDX file'
        print('real-dictionary-preflight',flush=True)
        preflight,real_rows,attrs=inspect_mdx(source,retain_rows=True)
        report['preflight']=preflight;report['real_source']=preflight['source'];original_hash=preflight['source']['sha256']
        if preflight['status']!='fits_size_profile':
            report.update(status='preflight_rejected_choose_supported_dictionary',stage='preflight')
            print(json.dumps(preflight,ensure_ascii=False,indent=2),flush=True)
            return 1
        cargo=shutil.which('cargo')
        if not cargo:raise RuntimeError('Run on the Rust-enabled Mac; native jobs did not run here')
        shell=out/'m3-shell-out';run('desktop-gate',[sys.executable,'scripts/m3_shell.py','--output',str(shell)])
        gate=json.loads((shell/'m3-shell-report.json').read_text())
        assert gate['status']=='adapter_tests_and_shell_compile_passed_native_launch_pending' and gate['native_tests_executed'] and all(s['returncode']==0 for s in gate['steps'])
        report.update(native_tests_executed=True,shell_report=str(shell/'m3-shell-report.json'))
        run('adapter-metadata',[cargo,'metadata','--offline','--locked','--format-version','1','--manifest-path',ADAPTER])
        metadata=json.loads((out/'adapter-metadata.log').read_text().split('\nSTDERR:\n')[0]);binary=Path(metadata['target_directory'])/'debug/examples/sqlite_sizing'
        run('sizing-build',[cargo,'build','--offline','--locked','--manifest-path',ADAPTER,'--example','sqlite_sizing'])
        if sys.platform=='win32':binary=binary.with_suffix('.exe')
        def exercise(name,path,operation,rows=None,attrs=None,expected_error=None):
            before=sha(path);native=out/name;specs=queries(rows,32 if name=='near-limit' else 1) if rows else []
            config={'source':str(path),'operation':operation,'queries':specs,'expected_error':expected_error}
            request=out/(name+'.json');request.write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
            run(name,[str(binary),str(request),str(native)])
            result=json.loads((native/'result.json').read_text());assert sha(path)==before,'Input source changed'
            report['native_jobs_executed']=True
            if expected_error:
                assert result['controlled_refusal'] and result['import']['error']['code']==expected_error
                assert set(p.name for p in native.iterdir())=={'result.json'}
                report['checks'].append({'case':name,'status':'controlled_refusal_verified','code':expected_error,'source_unchanged':True,'no_partial_output':True,'elapsed_ms':result['import']['elapsed_ms']});return
            assert result['import']['state']=='succeeded' and result['export']['state']=='succeeded'
            db=native/'dictionary.db';found,meta,stored_attrs=inspect(db)
            assert [(k,t) for _,k,t in found]==rows and meta['source_sha256']==before
            assert result['info']['value']['source_sha256']==sha(db)
            if attrs is not None:check_import(db,rows,attrs,before)
            else:assert stored_attrs is None
            for name_,count,hash_ in [('import',len(rows),before),('export',len(rows),sha(db))]:
                value=result[name_]['receipt']['receipt']['value'];assert value['records']==count and value['source_sha256']==hash_
            lookup=verify_queries(rows,specs,result);export=check_export(db,native/'export.jsonl')
            assert sha(path)==before
            report['checks'].append({'case':name,'status':'passed','records':len(rows),'decoded_bytes':sum(len(k.encode())+len(t.encode()) for k,t in rows),
                                     'source_sha256':before,'database_sha256':sha(db),'database_bytes':db.stat().st_size,
                                     'import_ms':result['import']['elapsed_ms'],'validated_open_ms':result['open_ms'],
                                     'export_ms':result['export']['elapsed_ms'],'lookups':lookup,'export_oracle':export,
                                     'source_unchanged':True,'all_lookup_samples_verified':True})
        from verify_database_jsonl import read_jsonl
        near=out/'near-limit.jsonl';synthetic(near);near_rows=read_jsonl(near);assert len(near_rows)==100000 and sum(len(k.encode())+len(t.encode()) for k,t in near_rows)>.95*DECODED_CAP
        exercise('near-limit',near,'jsonl_to_db',near_rows);del near_rows
        over=out/'over-count.jsonl';synthetic(over,count=100001,body_bytes=0);exercise('over-count',over,'jsonl_to_db',expected_error='limit_exceeded')
        over=out/'over-decoded.jsonl'
        with over.open('w',encoding='utf-8',newline='\n') as f:
            for i in range(32):f.write(json.dumps({'key':str(i),'text':'x'*(1024*1024)},separators=(',',':'))+'\n')
        exercise('over-decoded',over,'jsonl_to_db',expected_error='limit_exceeded')
        exercise('real',source,'mdx_to_db',real_rows,attrs)
        report['status']='database_sizing_native_and_oracle_passed'
        assert sha(source)==original_hash;report['stage']='complete'
    except (Exception,KeyboardInterrupt) as error:report.update(status='failed',error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        try:
            if protected is not None:assert inventory()==protected,'Protected M2 source changed'
            if current is not None:assert source_hashes()==current,'Qualification sources changed'
            if lock_before is not None:assert lock.read_bytes()==lock_before,'M4 lock changed'
        except Exception as error:report.update(status='failed',error=str(error))
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(report['status'],flush=True);print(out/'report.json',flush=True)
    return 0 if report['status']=='database_sizing_native_and_oracle_passed' else 1


if __name__=='__main__':raise SystemExit(main())
