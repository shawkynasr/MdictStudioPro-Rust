"""Explicit strict checksums for MDX/MDD: small mutation matrix and real scans.

No native apps, no engine-version upgrade and no repeat of the large stress run.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from patched_interop import ROOT,require,verify_candidate_source
from real_corpus import file_hash
from real_rebuild import run,stop
from v2_audit import audit,block


def geometry(data,is_mdd=False):
    require(len(data)<=8*1024*1024 and len(data)>=52,'Only bounded generated fixtures can be mutated')
    size=struct.unpack_from('>I',data)[0];pos=size+8
    require(2<=size<=1024*1024 and pos+44<=len(data),'Invalid fixture header')
    xml=data[4:4+size].decode('utf-16le')
    unit=2 if is_mdd or 'Encoding="UTF-16"' in xml else 1
    blocks,count,raw_info,packed_info,key_total=struct.unpack_from('>5Q',data,pos)
    info_start=pos+44;info=block(data[info_start:info_start+packed_info],raw_info)
    cursor=0;key_cursor=info_start+packed_info;keys=[];key_entries=0
    for _ in range(blocks):
        n=struct.unpack_from('>Q',info,cursor)[0];cursor+=8;key_entries+=n
        for _ in range(2):
            units=struct.unpack_from('>H',info,cursor)[0];cursor+=2+(units+1)*unit
        packed,unpacked=struct.unpack_from('>QQ',info,cursor);cursor+=16
        require(packed>=8 and key_cursor+packed<=len(data),'Invalid key block range')
        keys.append((key_cursor,packed));key_cursor+=packed
    require(cursor==len(info) and key_entries==count and key_cursor==info_start+packed_info+key_total,'Invalid key index geometry')
    n,entries,info_size,total=struct.unpack_from('>4Q',data,key_cursor)
    require(n>0 and entries==count and info_size==n*16,'Invalid record index geometry')
    record_cursor=key_cursor+32+info_size;records=[]
    for index in range(n):
        packed,unpacked=struct.unpack_from('>QQ',data,key_cursor+32+index*16)
        require(packed>=8 and record_cursor+packed<=len(data),'Invalid record block range')
        records.append((record_cursor,packed));record_cursor+=packed
    require(record_cursor==len(data) and sum(p for o,p in records)==total,'Trailing/truncated record sections')
    require(len(keys)>1 and len(records)>1,'Checksum matrix needs multiple key and record blocks')
    for offset,length in keys+records:require(data[offset:offset+4]==b'\x02\0\0\0','Matrix currently requires generated zlib blocks')
    return {'xml_checksum':4+size,'key_header_checksum':pos+40,'key_info_checksum':info_start+4,
        'first_key_checksum':keys[0][0]+4,'last_key_checksum':keys[-1][0]+4,
        'first_record_checksum':records[0][0]+4,'last_record_checksum':records[-1][0]+4,
        'last_record_zlib_trailer':records[-1][0]+records[-1][1]-1}


def mutate(data,site,offsets):
    require(site in offsets,'Unknown checksum site')
    result=bytearray(data);result[offsets[site]]^=1
    require(sum(a!=b for a,b in zip(data,result))==1,'Mutation changed more than one checksum byte')
    return bytes(result)


def invoke(binary,mode,path,prefix,timeout):
    process=subprocess.Popen([str(binary),'checksum-inspect',mode,str(path)],cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
    try:stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop(process);stdout,stderr=process.communicate()
        Path(str(prefix)+'.stderr').write_bytes(stderr)
        raise RuntimeError(f'Checksum scan timed out: {prefix.name}')
    Path(str(prefix)+'.stdout').write_bytes(stdout);Path(str(prefix)+'.stderr').write_bytes(stderr)
    require(process.returncode in {0,1},'Checksum scan panicked or terminated by signal')
    result=json.loads(stdout)
    require(result.get('checksum_policy')==('Verify' if mode=='verify' else 'Skip'),'Wrong reader checksum mode')
    require((process.returncode==0)==(result.get('status')=='validated'),'Reader exit/status disagreement')
    return process.returncode,result


def check_rejection(site,result):
    require(result.get('status')=='rejected','Strict policy accepted corrupted input')
    if site=='last_record_zlib_trailer':
        require(result.get('error_kind') in {'ChecksumMismatch','InvalidData'},'Unexpected zlib-trailer rejection kind')
    else:require(result.get('error_kind')=='ChecksumMismatch','Expected a typed checksum mismatch, not an unrelated failure')
    if site in {'first_record_checksum','last_record_checksum','last_record_zlib_trailer'}:
        require(result.get('phase')=='records','Record corruption was not reached through lazy payload validation')


def comparable(result):
    return {k:result[k] for k in ['records','payload_bytes','diagnostic_fingerprint_fnv1a64']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,help='Optional existing real corpus manifest; read-only full strict scan')
    parser.add_argument('--timeout',type=float,default=600)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','engine_revision':6,'checksum_policy':'Verify','native_readers':'NOT_RUN_DO_NOT_IMPORT',
        'checks':{},'real_cases':[],'not_proven':['fresh_TXT_XLSX_pack_parity','general_metadata_sort_policy',
            'encrypted_and_v1_checksum_matrix','persistent_key_index_checksum_policy','all_import_paths_integrated','M1_completion']}
    originals={}
    try:
        require(args.timeout>0,'Timeout must be positive')
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        report['source_sha256']={str(p.relative_to(ROOT)):file_hash(p) for p in
            [vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',ROOT/'experiments/real-rebuild/src/main.rs',
             ROOT/'experiments/real-rebuild/src/strict.rs',ROOT/'experiments/real-rebuild/Cargo.lock',Path(__file__).resolve()]}
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        executables={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)]
            if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(executables)==1,'Cannot identify Rust executable');binary=Path(executables.pop())
        spec=out/'seed-spec.json';spec.write_text(json.dumps({'entries':128,'body_bytes':512,'resources':16,'resource_bytes':4096})+'\n')
        run([binary,'stress-build',spec,out/'valid'],out/'seed-build.log',args.timeout)
        matrix=out/'mutated';matrix.mkdir()
        for extension,expected in [('mdx',128),('mdd',16)]:
            source=out/'valid'/f'stress.{extension}';originals[str(source)]=file_hash(source)
            strict_rc,clean=invoke(binary,'verify',source,out/f'{extension}-valid-verify',args.timeout)
            skip_rc,skip=invoke(binary,'skip',source,out/f'{extension}-valid-skip',args.timeout)
            require(strict_rc==skip_rc==0 and clean['records']==expected and comparable(clean)==comparable(skip),'Valid file disagrees across policies')
            require(audit(source)['status']=='structural_audit_passed','Independent valid fixture audit failed')
            report['checks'][f'{extension}-valid']={'status':'passed','verify':clean,'skip':skip}
            data=source.read_bytes();offsets=geometry(data,extension=='mdd')
            for site in offsets:
                path=matrix/f'{extension}-{site}.{extension}';path.write_bytes(mutate(data,site,offsets))
                name=f'{extension}-{site}'
                rc,rejected=invoke(binary,'verify',path,out/(name+'-verify'),args.timeout)
                require(rc==1,'Strict validation unexpectedly accepted mutation');check_rejection(site,rejected)
                observed_rc,observed=invoke(binary,'skip',path,out/(name+'-skip'),args.timeout)
                if observed_rc==0:require(comparable(observed)==comparable(clean),'Checksum-only mutation changed decoded content')
                independently=audit(path);require(independently['status']=='failed','Independent auditor accepted checksum mutation')
                report['checks'][name]={'status':'passed_strict_rejection','mutated_offset':offsets[site],
                    'verify':rejected,'skip':observed,'independent_error':independently.get('error')}
            require(report['checks'][f'{extension}-first_key_checksum']['skip']['status']=='validated','Diagnostic Skip mode no longer reproduces the prior checksum acceptance observation')
            rebuilt=out/f'clean-rebuild-{extension}'
            result=json.loads(run([binary,source,rebuilt],out/f'{extension}-clean-rebuild.log',args.timeout))
            require(result.get('source_checksum_policy')=='Verify' and result.get('output_full_checksum_validation')=='passed_before_publication','Rebuild path did not enforce strict source/output policy')
            corrupted=matrix/f'{extension}-last_record_checksum.{extension}'
            refused=out/f'corrupt-rebuild-{extension}'
            process=subprocess.Popen([str(binary),str(corrupted),str(refused)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
            try:stdout,stderr=process.communicate(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                stop(process);process.communicate();raise RuntimeError('Corrupted rebuild timed out')
            (out/f'{extension}-corrupt-rebuild.log').write_bytes(stdout+b'\nSTDERR:\n'+stderr)
            text=stderr.decode('utf-8',errors='replace').lower()
            require(process.returncode==1 and not refused.exists() and ('checksum' in text or 'adler' in text),'Corrupt rebuild did not reject checksum failure without publishing output')
            report['checks'][f'{extension}-strict-rebuild-integration']={'status':'passed','clean_source_and_output_verified':True,'corrupted_source_refused_without_publication':True}
        if args.manifest is not None:
            manifest=args.manifest.resolve();selected=json.loads(manifest.read_text(encoding='utf-8'))['cases'];require(selected,'Empty real manifest')
            for index,case in enumerate(selected):
                path=Path(case['path']).expanduser()
                if not path.is_absolute():path=manifest.parent/path
                path=path.resolve();require(path.is_file() and path.suffix.lower() in {'.mdx','.mdd'},'Missing selected real dictionary')
                require(path.stat().st_size<=64*1024*1024,'This real checksum qualification preset accepts files up to 64 MiB')
                originals[str(path)]=file_hash(path)
                rc,result=invoke(binary,'verify',path,out/f'real-{index:03d}',args.timeout)
                item={'id':case['id'],'path':str(path),'source_sha256':originals[str(path)],'result':result};report['real_cases'].append(item)
                require(rc==0,'Strict scan rejected a selected real dictionary; review its typed error')
        report['status']='strict_checksum_matrix_and_real_scans_passed_M1_open' if args.manifest is not None else 'strict_checksum_matrix_passed_real_corpus_not_run'
    except Exception as error:
        if report['checks']:report['status']='failed_strict_checksum_qualification'
        report['error']=str(error)
    finally:
        report['input_integrity']={name:{'before':sha,'after':file_hash(Path(name)) if Path(name).is_file() else None} for name,sha in originals.items()}
        if any(c['before']!=c['after'] for c in report['input_integrity'].values()):report['status']='failed_input_integrity'
        (out/'checksum-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"{report['status']}: {out/'checksum-report.json'}")
    return 0 if report['status'] in {'strict_checksum_matrix_and_real_scans_passed_M1_open','strict_checksum_matrix_passed_real_corpus_not_run'} else 1


if __name__=='__main__':raise SystemExit(main())
