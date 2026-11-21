"""Unicode edge qualification for existing export profiles; no locale guessing."""
import argparse
import importlib.metadata
import json
import locale
from pathlib import Path
import shutil
import sys
import unicodedata
from patched_interop import ROOT,require,verify_candidate_source,read_python
from fresh_pack import ordered
from real_rebuild import run
from real_corpus import file_hash
from v2_audit import audit


def words():
    return ['ΟΣ','ος','οσ','ΟΣΑ','οσα','AΣ','aς','aσ','AΣA','aΣ-b',
        'İ','i\u0307','I','i','ı','ß','ẞ','ss','SS','ſ','s','Σ','σ','ς',
        'µ','μ','×','÷','\ue000','Ａ','𐐀','𐐨','𠀀','😀','é','e\u0301',
        'a\\b','a-b','ab','a b','a\u00a0b','a\u3000b','中，文','中文','مرحبا']


def scalar_lower(text):return ''.join(c.lower() for c in text)


def lookup(rows,query):
    exact=[r for r in rows if r['key']==query]
    return exact or [r for r in rows if scalar_lower(r['key'])==scalar_lower(query)]


def mapping_differences(rust):
    require(rust['scalars_scanned']==0x110000-0x800,'Rust did not enumerate all Unicode scalar values')
    pairs=rust['changed_scalar_mappings'];table=dict(pairs)
    require(len(table)==len(pairs),'Repeated Rust scalar mapping')
    require(all(isinstance(n,int) and 0<=n<=0x10ffff and not 0xd800<=n<=0xdfff and isinstance(v,str) and v!=chr(n) for n,v in pairs),'Invalid Rust scalar mapping')
    differences=[];changed=0
    for n in range(0x110000):
        if 0xd800<=n<=0xdfff:continue
        char=chr(n);python=char.lower();changed+=python!=char;actual=table.get(n,char)
        if python!=actual:differences.append({'codepoint':f'U+{n:04X}','input':char,'python':python,'rust':actual})
    return changed,differences


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=600);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','checks':{},'native_readers':'NOT_RUN','not_proven':['native_unicode_lookup','official_MdxBuilder_Wide_or_Narrow','full_Unicode_context_conformance','legacy_native_export','M1_completion']}
    try:
        require(args.timeout>0,'Timeout must be positive');locale.setlocale(locale.LC_COLLATE,'C')
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Expected mdict-utils==1.3.14')
        report['environment']={'python':sys.version,'mdict-utils':importlib.metadata.version('mdict-utils'),'collation':'C'}
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
        report['source_sha256']={str(path.relative_to(ROOT)):file_hash(path) for path in [ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/unicode.rs',ROOT/'experiments/real-rebuild/src/policy.rs',ROOT/'experiments/real-rebuild/src/strict.rs',ROOT/'experiments/real-rebuild/Cargo.lock',vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',Path(__file__).resolve()]}
        spec=out/'unicode-spec.json';spec.write_text(json.dumps({'words':words()},ensure_ascii=False)+'\n',encoding='utf-8')
        rust=json.loads(run([binary,'unicode-probe',spec],out/'unicode-probe.log',args.timeout))
        require([c['word'] for c in rust['contexts']]==words(),'Incomplete contextual observations')
        changed,differences=mapping_differences(rust)
        report['lowercase_mapping']={'scalars_compared':rust['scalars_scanned'],'python_unicode_version':unicodedata.unidata_version,'rust_unicode_version':rust['rust_unicode_version'],
            'python_changed_scalars':changed,'rust_changed_scalars':len(rust['changed_scalar_mappings']),'differences':differences,'scope':'Exhaustive single-scalar lowercase comparison; not all Unicode strings'}
        contexts=[]
        for c in rust['contexts']:
            word=c['word'];contexts.append({**c,'python_string_lower':word.lower(),'python_scalar_lower':scalar_lower(word)})
        report['contexts']=contexts
        require(not differences,'Compiler/Python Unicode scalar mappings differ; inspect report before selecting a frozen policy')
        require(all(c['string_lower']==c['python_string_lower'] and c['scalar_lower']==c['python_scalar_lower'] for c in contexts),'Contextual lowercase differs on the selected words')
        # Payload identity remains distinguishable even where normalized keys tie.
        entries=[{'key':w,'text':f'<p>UNICODE_{i:02d}</p>'} for i,w in enumerate(words(),1)]
        queries=words()+['Ος','οΣ','aΣ','ssS','E\u0301','missing-unicode']
        native={};checklist=[]
        for name,profile,encoding in [('literal-utf8','literal','utf8'),('literal-utf16','literal','utf16'),('legacy-mdict-utils','mdict-utils','utf8'),('legacy-mdxbuilder','mdxbuilder','utf8')]:
            case={'entries':entries,'queries':queries,'profile':profile,'encoding':encoding,'title':'08-unicode-'+name}
            case_spec=out/f'{name}.json';case_spec.write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            result=json.loads(run([binary,'policy-build',case_spec,out/name],out/f'{name}.log',args.timeout));path=out/name/'policy.mdx'
            expected=sorted(entries,key=lambda e:e['key'].lower()) if profile=='literal' else [{'key':k,'text':v} for k,v in ordered([(r['key'],r['text']) for r in entries],profile)]
            require(result['rows']==expected,'Physical order or payload differs from the selected Python profile')
            require(read_python(path,'mdx')==[(r['key'],r['text']) for r in expected],'Independent Python rows differ')
            require(result['key_blocks']>2 and result['record_blocks']>1,'Unicode fixtures did not cross block boundaries')
            require([q['query'] for q in result['lookups']]==queries,'Incomplete Unicode lookup inventory')
            for q in result['lookups']:
                exact=[r for r in expected if r['key']==q['query']]
                if profile=='literal':require(q['rows']==lookup(expected,q['query']),f"Literal lookup differs: {q['query']!r}")
                elif exact:require(q['rows']==exact,'Legacy exact lookup lost physical records')
            wire=audit(path);require(wire['status']=='structural_audit_passed' and wire['records_without_terminal_null']==0,'Unicode wire audit failed')
            report['checks'][name]={'status':'passed','profile':profile,'encoding':encoding,'records':len(expected),'queries':len(queries),'key_blocks':result['key_blocks'],
                'sha256':file_hash(path),'attributes':result['attributes'],'physical_keys':[r['key'] for r in expected],'lookups':result['lookups'],
                'native_qualified':False,'scope':'physical order and all exact queries; literal also checks every scalar-lower fallback'}
            if profile=='literal':
                native[f'08-unicode-{encoding}.mdx']=path
                for r in entries:checklist.append({'file':f'08-unicode-{encoding}.mdx','query':r['key'],'payload_marker':r['text']})
        report['ordering_example']={'keys':['Ａ','𐐀'],'scalar_order':sorted(['Ａ','𐐀'],key=str.lower),
            'utf16_unit_order':sorted(['Ａ','𐐀'],key=lambda s:list(int.from_bytes(s.lower().encode('utf-16le')[i:i+2],'little') for i in range(0,len(s.lower().encode('utf-16le')),2))),
            'note':'Comparison-unit illustration only; this is not the official builder mapping'}
        dest=out/'native-candidates';dest.mkdir()
        for name,path in native.items():shutil.copyfile(path,dest/name)
        report['native_candidates']={name:file_hash(dest/name) for name in native}
        (out/'native-checklist.json').write_text(json.dumps(checklist,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report['status']='unicode_lowercase_and_profile_subset_passed_native_pending_M1_open'
    except Exception as error:report['status']='failed_unicode_profile_qualification';report['error']=str(error)
    (out/'unicode-profile-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {out/'unicode-profile-report.json'}")
    return 0 if report['status']=='unicode_lowercase_and_profile_subset_passed_native_pending_M1_open' else 1


if __name__=='__main__':raise SystemExit(main())
