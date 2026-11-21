"""Rebuild selected real v2 dictionaries without changing source metadata/order.

Qualification only: bounded in-memory writer, four independent scans, disk-backed
multiset comparison, exact header/sidecar preservation. Never opens native apps.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from patched_interop import ROOT, require, experiment_command, verify_candidate_source
from reference_builder import header_details
from real_corpus import file_hash, connect, record, differences, payload
from v2_audit import audit


def stop(process):
    try:
        if os.name == 'posix': os.killpg(process.pid,signal.SIGKILL)
        elif process.poll() is None: process.kill()
    except ProcessLookupError: pass


def run(command, log, timeout):
    process = subprocess.Popen(list(map(str,command)),cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
    try:
        stdout,stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop(process); stdout,stderr = process.communicate()
        log.write_bytes(stdout+b'\nSTDERR:\n'+stderr)
        raise RuntimeError(f'Command timed out; see {log.name}')
    log.write_bytes(stdout+b'\nSTDERR:\n'+stderr)
    require(process.returncode==0,f'Command failed; see {log.name}')
    return stdout.decode('utf-8')


def scan(command,db,engine,kind,log,timeout):
    start=time.monotonic(); digest=hashlib.sha256(); header=None; ended=False; count=0
    with log.open('wb') as stderr:
        process=subprocess.Popen(list(map(str,command)),cwd=ROOT,stdout=subprocess.PIPE,stderr=stderr,start_new_session=os.name=='posix')
        timer=threading.Timer(timeout,lambda:stop(process));timer.daemon=True;timer.start()
        try:
            for raw in process.stdout:
                row=json.loads(raw);require(not ended,'Output after end marker')
                if row['type']=='header':
                    require(header is None and count==0 and row['kind']==kind,'Invalid reader header')
                    header=row['attributes']
                elif row['type']=='row':
                    require(header is not None,'Record before header')
                    body=payload(row,kind);key=row['key'].encode('utf-8')
                    require(count<500_000,'Qualification row budget exceeded')
                    record(db,engine,row['key'],body);count+=1
                    digest.update(len(key).to_bytes(8,'big'));digest.update(key);digest.update(hashlib.sha256(body).digest())
                elif row['type']=='end':
                    require(header is not None and row['records']==count,'Incomplete stream count');ended=True
                else: raise ValueError('Unknown stream message')
            require(ended,'Reader stream truncated')
            require(process.wait()==0,f'Reader failed; see {log.name}')
            db.commit()
            return {'records':count,'attributes':header,'ordered_key_payload_sha256':digest.hexdigest(),
                    'elapsed_seconds':round(time.monotonic()-start,3)}
        finally:
            timer.cancel()
            if process.poll() is None:stop(process)
            process.wait();process.stdout.close()


def plan(manifest):
    spec=json.loads(manifest.read_text(encoding='utf-8'))
    require(isinstance(spec.get('cases'),list) and spec['cases'],'Manifest needs dictionary cases')
    items=[];names=set();identities=set();paths=set()
    for case in spec['cases']:
        path=Path(case['path']).expanduser()
        if not path.is_absolute():path=manifest.resolve().parent/path
        path=path.resolve();identity=case['id']
        require(identity not in identities and path not in paths,'Duplicate case ID or input path')
        require(path.is_file() and path.suffix.lower() in {'.mdx','.mdd'},f'Missing or unsupported dictionary: {path}')
        require(path.name.casefold() not in names,'Output basename collision; select inputs with unique names')
        require(path.stat().st_size<=32*1024*1024,'Preset input limit is 32 MiB per file')
        attrs=header_details(path)['attributes']
        require(attrs.get('Encrypted','No').lower() in {'no','0',''},'Preset refuses encrypted rebuild inputs')
        if path.suffix.lower()=='.mdx':require(attrs.get('Encoding','').upper()=='UTF-8','Preset supports UTF-8 MDX only')
        names.add(path.name.casefold());identities.add(identity);paths.add(path)
        companions=[]
        for value in case.get('companions',[]):
            companion=Path(value).expanduser()
            if not companion.is_absolute():companion=manifest.resolve().parent/companion
            companion=companion.resolve()
            require(companion.is_relative_to(path.parent),'Declared companion escapes its dictionary directory')
            companions.append(companion)
        items.append({**case,'source':path,'companions_resolved':companions})
    return items


def cross_differences(db,rebuilt_db):
    db.execute('ATTACH DATABASE ? AS rebuilt',(str(rebuilt_db),))
    try:
        left=db.execute('SELECT count(*) FROM (SELECT k,h,p FROM main.records EXCEPT SELECT k,h,p FROM rebuilt.records)').fetchone()[0]
        right=db.execute('SELECT count(*) FROM (SELECT k,h,p FROM rebuilt.records EXCEPT SELECT k,h,p FROM main.records)').fetchone()[0]
        return left+right
    finally:db.execute('DETACH DATABASE rebuilt')


def copy_companions(items,destination,amiri):
    dictionary_paths={item['source'] for item in items}
    results=[];copied={}
    for item in items:
        for declared in item['companions_resolved']:
            relative=declared.relative_to(item['source'].parent)
            detail={'declared':str(declared),'relative_output':relative.as_posix()}
            if declared in dictionary_paths:
                detail.update(status='rebuilt_dictionary_companion',sha256=file_hash(destination/declared.name));results.append(detail);continue
            if declared.suffix.lower() in {'.mdx','.mdd'}:
                detail['status']='missing_rebuild_case_for_dictionary_companion';results.append(detail);continue
            source=amiri if amiri is not None and relative.as_posix()=='fonts/amiri-regular.ttf' else declared
            if not source.is_file():detail['status']='missing';results.append(detail);continue
            target=destination/relative
            require(target.resolve().is_relative_to(destination.resolve()),'Unsafe companion output')
            checksum=file_hash(source)
            if target.exists():
                require(target in copied and copied[target]==checksum,'Companion collision with dictionary or different companion')
            else:
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            require(file_hash(target)==checksum and file_hash(source)==checksum,'Companion copy changed bytes')
            copied[target]=checksum
            detail.update(status='copied_exact_bytes',source=str(source),sha256=checksum);results.append(detail)
    return results


def qualify(manifest,out,timeout,amiri):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','engine_revision':6,'cases':[],'native_readers':'NOT_RUN_DO_NOT_IMPORT',
        'scope':'unchanged raw header, physical order and decoded records; no new sort or metadata policy',
        'limits':'32 MiB input; 500k records; 256 MiB decoded key+payload; in-memory builder; not production resource limits',
        'not_proven':['native_real_rebuilt_rendering','native_Amiri_font_loading','new_dictionary_authoring_metadata_policy',
                      'fresh_source_TXT_or_XLSX_pack_parity','large_files','production_limits','M1_completion']}
    before={};original_paths={};work=out/'work';work.mkdir();dictionaries=work/'dictionaries';dictionaries.mkdir()
    try:
        require(timeout>0,'Timeout must be positive')
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Expected mdict-utils 1.3.14')
        items=plan(manifest)
        for item in items:
            for p in [item['source'],*item['companions_resolved']]:
                if p.is_file():before[str(p)]=file_hash(p);original_paths[str(p)]=p
        if amiri is not None:
            amiri=amiri.expanduser().resolve();require(amiri.is_file(),'Selected Amiri file does not exist')
            before[str(amiri)]=file_hash(amiri);original_paths[str(amiri)]=amiri
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        report['source_sha256']={str(p.relative_to(ROOT)):file_hash(p) for p in
            [vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',ROOT/'experiments/real-rebuild/src/main.rs',
             ROOT/'experiments/real-rebuild/Cargo.lock',Path(__file__).resolve()]}
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rebuild-tests.log',timeout)
        for index,item in enumerate(items,1):
            source=item['source'];kind=source.suffix[1:].lower()
            case={'id':item['id'],'source':str(source),'status':'failed','source_sha256':before[str(source)]};report['cases'].append(case)
            source_db=connect(out/f'case-{index:03d}-source.sqlite');rebuilt_db=connect(out/f'case-{index:03d}-rebuilt.sqlite')
            try:
                result=json.loads(run(['cargo','run','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--',
                    source,work/f'build-{index:03d}'],out/f'case-{index:03d}-build.log',timeout))
                generated=work/f'build-{index:03d}'/result['file']
                require(generated.name==f'rebuilt.{kind}','Unexpected rebuild output')
                target=dictionaries/source.name;generated.rename(target)
                case['builder']=result;case['output_name']=target.name
                def pair(path,db,label):
                    values={}
                    for engine,command in [('r',experiment_command(6,'dump-rows',path)),
                        ('p',[sys.executable,ROOT/'scripts/real_corpus.py','python-rows',path])]:
                        values[engine]=scan(command,db,engine,kind,out/f'case-{index:03d}-{label}-{engine}.log',timeout)
                    require(differences(db)==0 and values['r']['attributes']==values['p']['attributes'],'Rust/Python record or metadata disagreement')
                    require(values['r']['ordered_key_payload_sha256']==values['p']['ordered_key_payload_sha256'],'Rust/Python physical order differs')
                    return values
                case['source_scans']=pair(source,source_db,'source')
                case['rebuilt_scans']=pair(target,rebuilt_db,'rebuilt')
                case['different_key_payload_counts']=cross_differences(source_db,out/f'case-{index:03d}-rebuilt.sqlite')
                require(case['different_key_payload_counts']==0,'Source/rebuilt exact key-payload multiplicities differ')
                require(case['source_scans']['p']['ordered_key_payload_sha256']==case['rebuilt_scans']['p']['ordered_key_payload_sha256'],'Source/rebuilt physical order differs')
                require(case['source_scans']['p']['attributes']==case['rebuilt_scans']['p']['attributes'],'Rebuilt metadata changed')
                case['structural_audit']=audit(target)
                require(case['structural_audit']['status']=='structural_audit_passed' and
                        case['structural_audit']['records']==case['source_scans']['p']['records'],'Rebuilt independent structural audit failed')
                if kind=='mdx':require(case['structural_audit']['records_without_terminal_null']==0,'Rebuilt MDX record terminator missing')
                require(header_details(source)==header_details(target),'Rebuilt header details changed')
                # Prefix equality is stronger than attribute-map equality, including aliases and line endings.
                header_size=header_details(source)['header_bytes']+8
                with source.open('rb') as a,target.open('rb') as b:require(a.read(header_size)==b.read(header_size),'Raw header prefix changed')
                keys=list(dict.fromkeys(item.get('lookup_keys',[])+[r[0].decode('utf-8') for r in source_db.execute('SELECT DISTINCT k FROM records ORDER BY k LIMIT 8')]))
                case['lookups']={}
                for key in keys:
                    result=json.loads(run(experiment_command(6,'lookup-json',target,key),out/f'case-{index:03d}-lookup-{len(case["lookups"]):02d}.log',timeout))
                    actual={}
                    for row in result['rows']:
                        digest=hashlib.sha256(payload(row,kind)).digest();actual[digest]=actual.get(digest,0)+1
                    expected=dict(source_db.execute('SELECT h,p FROM records WHERE k=? AND p>0',(key.encode('utf-8'),)))
                    require(expected and actual==expected,'Rebuilt lookup differs from source Python inventory')
                    case['lookups'][key]={'status':'passed','records':sum(actual.values())}
                case.update(status='passed_rebuild_records_metadata_and_order',output_sha256=file_hash(target))
            finally:source_db.close();rebuilt_db.close()
        report['companions']=copy_companions(items,dictionaries,amiri)
        pending=[c for c in report['companions'] if c['status'] not in {'copied_exact_bytes','rebuilt_dictionary_companion'}]
        if pending:report['status']='rebuild_records_passed_companions_pending'
        else:
            dictionaries.rename(out/'verified-dictionaries')
            report['status']='real_rebuild_offline_passed_native_untested';report['native_readers']='NOT_RUN_READY_FOR_STAGED_MANUAL_TEST'
            with (out/'reader-results.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['reader','dictionary','key','result','notes']);writer.writeheader()
                for case in report['cases']:
                    if case['output_name'].lower().endswith('.mdx'):
                        for reader in ['GoldenDict','MDict']:
                            for key in case['lookups']:writer.writerow({'reader':reader,'dictionary':case['output_name'],'key':key,'result':'NOT_RUN'})
    except Exception as error:
        report.update(status='failed_rebuild_qualification',native_readers='NOT_RUN_DO_NOT_IMPORT',error=str(error))
        verified=out/'verified-dictionaries'
        if verified.exists():verified.rename(work/'withheld-dictionaries')
    finally:
        report['input_integrity']={name:{'before':checksum,'after':file_hash(p) if p.is_file() else None} for name,checksum in before.items() for p in [original_paths[name]]}
        if any(v['before']!=v['after'] for v in report['input_integrity'].values()):
            report['status']='failed_input_integrity';report['native_readers']='NOT_RUN_DO_NOT_IMPORT'
            verified=out/'verified-dictionaries'
            if verified.exists():verified.rename(work/'withheld-dictionaries')
        (out/'real-rebuild-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"{report['status']}: {out/'real-rebuild-report.json'}")
    return 0 if report['status']=='real_rebuild_offline_passed_native_untested' else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=ROOT/'baseline/real-corpus-manifest.json')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--timeout',type=float,default=1800)
    parser.add_argument('--amiri-font',type=Path,help='Optional original Amiri TTF to copy to fonts/amiri-regular.ttf in output only')
    args=parser.parse_args();return qualify(args.manifest,args.output,args.timeout,args.amiri_font)


if __name__=='__main__':raise SystemExit(main())
