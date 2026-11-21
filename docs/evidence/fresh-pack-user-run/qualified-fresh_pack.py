"""Fresh packing parity after original TXT/XLSX conversion; no native apps.

This qualifies Rust packing, not Rust XLSX conversion. No real corpus is needed.
"""
import argparse
from collections import defaultdict,deque
import importlib.metadata
import json
import locale
from pathlib import Path
import sys
from patched_interop import ROOT,require,verify_candidate_source,legacy_fixture_records,custom_writer_class,read_python,inspect_header
from real_corpus import file_hash
from real_rebuild import run
from v2_audit import audit

sys.path.insert(0,str(ROOT/'baseline'))
import capture


def ordered(rows,profile,is_mdd=False):
    buckets=defaultdict(deque)
    for key,body in rows:buckets[key].append(body)
    keys=capture.sort_oracle([k for k,v in rows],profile,is_mdd)
    return [(k,buckets[k].popleft()) for k in keys]


def boundary_source():
    keys=['a-b','ab','a b','Apple','apple','APPLE','apple','a!b','a.b','Äpfel','äpfel','字','和','مرحبا','𠀀']
    return ''.join(f'{key}\n<p>entry {i}: {key}</p>\n\nlast line\n</>\n' for i,key in enumerate(keys))+'redirect\n@@@LINK=和\n</>\n'


def check_rows(expected,observed):
    require(expected==observed,'Ordered key/payload rows differ; no normalization is permitted')


def legacy_worker(spec_path,out):
    # This worker uses file results, not stdout as a protocol. User/library prints
    # and warnings are captured by the parent's per-case log.
    from mdict_utils.writer import pack_mdx_txt
    locale.setlocale(locale.LC_COLLATE,'C')
    spec=json.loads(spec_path.read_text(encoding='utf-8'));out.mkdir(exist_ok=False)
    writer=custom_writer_class();observed={}
    for kind in ['mdx','mdd']:
        if kind=='mdx':data=pack_mdx_txt(spec['source'],encoding='utf-8')
        else:
            if not spec['resources']:continue
            data=[]
            for index,resource in enumerate(spec['resources']):
                path=out/f'resource-{index}.bin';path.write_bytes(bytes(resource['bytes']))
                data.append({'key':resource['key'],'path':str(path),'size':path.stat().st_size,'pos':0})
        path=out/f'legacy.{kind}'
        engine=writer(data,title=spec['title'],description=spec['description'],encoding='utf-8',is_mdd=kind=='mdd',sort_style=spec['profile'],key_size=64,record_size=128)
        with path.open('wb') as stream:engine.write(stream)
        rows=read_python(path,kind)
        observed[kind]={'rows':[{'key':k,('text' if kind=='mdx' else 'bytes'):v if kind=='mdx' else list(v)} for k,v in rows],
            'attributes':inspect_header(path)['attributes']}
    (out/'observations.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def rows(value,kind):
    return [(r['key'],r['text'] if kind=='mdx' else bytes(r['bytes'])) for r in value['rows']]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=600);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','checks':{},'scope':'original six converters -> UTF8 LF TXT -> fresh Rust/Python MDX; two legacy C-locale sort profiles; diagnostic MDD',
        'native_readers':'NOT_RUN_DO_NOT_IMPORT','not_proven':['Rust_XLSX_or_plugin_conversion','UTF16_BOM_CRLF_fresh_source_matrix','general_metadata_stylesheet_sort_policy','native_rendering_of_these_files','production_memory_limits','M1_completion']}
    originals={}
    try:
        require(args.timeout>0,'Timeout must be positive')
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Expected mdict-utils==1.3.14')
        require(importlib.metadata.version('openpyxl')=='3.1.5','Expected openpyxl==3.1.5 for frozen converter baseline')
        locale.setlocale(locale.LC_COLLATE,'C')
        # Regenerate from fresh synthetic workbook / CEDICT inputs; run.py checks
        # all nine golden artifacts byte for byte, without updating the goldens.
        run([sys.executable,ROOT/'baseline/run.py','check'],out/'baseline.log',args.timeout)
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
        report['source_sha256']={str(p.relative_to(ROOT)):file_hash(p) for p in [ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/fresh.rs',ROOT/'experiments/real-rebuild/src/strict.rs',ROOT/'experiments/real-rebuild/Cargo.lock',vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',Path(__file__).resolve()]}
        report['environment']={'mdict-utils':importlib.metadata.version('mdict-utils'),'openpyxl':importlib.metadata.version('openpyxl'),'python':sys.version,'collation':'C'}
        inputs=out/'inputs';inputs.mkdir()
        sources={name:ROOT/'baseline/expected'/f'{name}.txt' for name in capture.PLUGINS}
        sources['boundaries']=inputs/'boundaries.txt';sources['boundaries'].write_text(boundary_source(),encoding='utf-8',newline='')
        resources=[{'key':'\\data\\A.bin','bytes':[0,255,128,1]}, {'key':'\\data\\a.bin','bytes':[42,0,13,10]},
            {'key':'\\字\\note.txt','bytes':list('字 مرحبا'.encode('utf-8'))}, {'key':'\\empty.bin','bytes':[]}]
        for name,source in sources.items():
            originals[str(source)]=file_hash(source)
            expected=legacy_fixture_records(source.read_bytes().decode('utf-8'))
            for profile in ['mdict-utils','mdxbuilder']:
                case=f'{name}-{profile}';report['active_case']=case
                spec={'source':str(source),'profile':profile,'title':f'Fresh {name} 字 مرحبا','description':'Fresh pack <test> & exact payloads','resources':resources if name=='boundaries' else []}
                spec_path=out/f'{case}.json';spec_path.write_text(json.dumps(spec,ensure_ascii=False)+'\n',encoding='utf-8')
                rust_dir=out/f'{case}-rust';legacy_dir=out/f'{case}-python'
                observed=json.loads(run([binary,'fresh-pack',spec_path,rust_dir],out/f'{case}-rust.log',args.timeout))
                run([sys.executable,Path(__file__).resolve(),'--legacy-worker',spec_path,legacy_dir],out/f'{case}-python.log',args.timeout)
                legacy=json.loads((legacy_dir/'observations.json').read_text(encoding='utf-8'))
                detail={}
                for kind in ['mdx','mdd']:
                    if kind=='mdd' and not spec['resources']:continue
                    expected_rows=ordered(expected,profile) if kind=='mdx' else ordered([(r['key'],bytes(r['bytes'])) for r in resources],profile,True)
                    value=observed if kind=='mdx' else observed['mdd']
                    check_rows(expected_rows,rows(value,kind));check_rows(expected_rows,rows(legacy[kind],kind))
                    path=rust_dir/f'fresh.{kind}'
                    # Independent Python read of the fresh Rust output, with
                    # complete payload and duplicate-preserving physical order.
                    check_rows(expected_rows,read_python(path,kind))
                    for key in ['title','description']:
                        for attrs in [value['attributes'],legacy[kind]['attributes']]:require(attrs.get(key.title())==spec[key],f'{case}: {key} metadata differs')
                    audit_result=audit(path);require(audit_result['status']=='structural_audit_passed','Fresh Rust independent audit failed')
                    # Strict full scan of the Python output provides the reverse
                    # reader direction, including every lazy record block.
                    strict=json.loads(run([binary,'fresh-inspect',legacy_dir/f'legacy.{kind}'],out/f'{case}-{kind}-strict.log',args.timeout))
                    require(strict['checksum_policy']=='Verify','Reverse read did not use Verify')
                    check_rows(expected_rows,rows(strict,kind))
                    detail[kind]={'records':len(expected_rows),'comparison':'ordered_exact_with_duplicates_and_final_LF','rust_sha256':file_hash(path),'python_sha256':file_hash(legacy_dir/f'legacy.{kind}'),'independent_audit':'passed','legacy_full_strict_scan':'passed',
                        'rust_attributes':value['attributes'],'python_attributes':legacy[kind]['attributes'],'metadata_compared':['Title','Description']}
                report['checks'][case]={'status':'passed','detail':detail}
        require(len(report['checks'])==14,'Incomplete fresh-source matrix')
        report.pop('active_case',None)
        report['status']='fresh_source_pack_subset_passed_M1_open'
    except Exception as error:
        report['status']='failed_fresh_source_pack_qualification';report['error']=str(error)
    finally:
        report['input_integrity']={name:{'before':sha,'after':file_hash(Path(name)) if Path(name).is_file() else None} for name,sha in originals.items()}
        if any(c['before']!=c['after'] for c in report['input_integrity'].values()):report['status']='failed_input_integrity'
        (out/'fresh-pack-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"{report['status']}: {out/'fresh-pack-report.json'}")
    return 0 if report['status']=='fresh_source_pack_subset_passed_M1_open' else 1


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--legacy-worker':legacy_worker(Path(sys.argv[2]),Path(sys.argv[3]))
    else:raise SystemExit(main())
