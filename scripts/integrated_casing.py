"""Pin reviewed data and qualify shared casing in real MDX adapter operations."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import unicodedata
from patched_interop import ROOT,require,verify_candidate_source,read_python
from real_corpus import file_hash
from real_rebuild import run,stop
from header_lookup import rewrite_header
from unicode_profiles import words
from v2_audit import audit

SHA16='f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071'
LEGACY='unicode16-literal-v1'
MODERN='unicode17-literal-comparison-v1'


def fixture(differences):
    keys=list(words())
    for d in differences:
        upper=d['input'];lower=d['rust'];keys.extend([upper,lower,'A'+upper+'Σ',upper+'Σ'])
    keys=list(dict.fromkeys(keys))
    rows=[{'key':k,'text':f'<p>PINNED_{i:03d}</p>'} for i,k in enumerate(keys)]
    rows.append({'key':'ΟΣ','text':'<p>SIGMA_DUPLICATE</p>'})
    rows.extend({'key':'duplicate','text':f'<p>DUP_{i:02d}</p>'} for i in range(1,9))
    queries=list(dict.fromkeys([r['key'] for r in rows]+['οΣ','Ος','aΣ','DUPLICATE','a?b','missing-policy']+
        ['a'+d['rust']+'Σ' for d in differences]))
    return rows,queries


def expected_lookup(rows,query,normalized):
    exact=[r for r in rows if r['key']==query]
    return exact or [r for r in rows if normalized[r['key']]==normalized[query]]


def assert_refusal(binary,spec,path,log,timeout,reason):
    import os
    process=subprocess.Popen([str(binary),'integrated-inspect',str(spec),str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
    try:stdout,stderr=process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:stop(process);process.communicate();raise RuntimeError(f'Policy refusal timed out: {log.name}')
    log.write_bytes(stdout+b'\nSTDERR:\n'+stderr)
    require(process.returncode==1 and not stdout.strip() and reason.encode() in stderr,f'Policy refusal failed; see {log.name}')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=600);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','checks':{},'adapter_integrated':True,'engine_builtin_locator_changed':False,'native_readers':'NOT_RUN_DO_NOT_IMPORT',
        'not_proven':['native_readers_honor_custom_policy','production_import_paths_and_index_limits','official_MdxBuilder_comparator','all_string_Unicode_conformance','M1_completion']}
    try:
        require(args.timeout>0,'Timeout must be positive')
        require(unicodedata.unidata_version=='16.0.0','Python reference must use Unicode16; use the same .venv')
        policy=ROOT/'baseline/unicode/unicode16-casing.json';require(file_hash(policy)==SHA16,'Reviewed Unicode16 policy hash differs; refusing build')
        prior=json.loads((ROOT/'docs/evidence/unicode-version-user-run/unicode-profile-report.json').read_text(encoding='utf-8'))
        rows,queries=fixture(prior['lowercase_mapping']['differences'])
        report['pinned_policy']={'file':str(policy.relative_to(ROOT)),'sha256':SHA16,'storage':'compiled embedded data; hash enforced by qualification driver and package checks'}
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
        report['source_sha256']={str(path.relative_to(ROOT)):file_hash(path) for path in [ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/casing.rs',ROOT/'experiments/real-rebuild/src/integrated.rs',ROOT/'experiments/real-rebuild/src/strict.rs',ROOT/'experiments/real-rebuild/Cargo.lock',vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',Path(__file__).resolve(),policy]}
        all_words=list(dict.fromkeys([r['key'] for r in rows]+queries))
        reference=out/'reference-spec.json';reference.write_text(json.dumps({'policy_path':str(policy),'words':all_words,'skip_scalar_scan':True},ensure_ascii=False)+'\n',encoding='utf-8')
        oracle=json.loads(run([binary,'casing-probe',reference],out/'reference.log',args.timeout))
        require(oracle['scalar_scan_skipped'] is True and oracle['scalars_scanned']==0 and [r['word'] for r in oracle['contexts']]==all_words,'Unexpected normalization reference scope')
        norms={LEGACY:{r['word']:r['legacy16'] for r in oracle['contexts']},MODERN:{r['word']:r['modern17'] for r in oracle['contexts']}}
        require(all(value==key.lower() for key,value in norms[LEGACY].items()),'Integrated fixture reference differs from Python16')
        paths={};specs={};observations={}
        for profile in [LEGACY,MODERN]:
            for encoding in ['utf8','utf16']:
                name=f'{profile}-{encoding}';spec={'profile':profile,'encoding':encoding,'entries':rows,'queries':queries,'title':'09-'+name}
                spec_path=out/f'{name}.json';spec_path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');specs[name]=spec_path
                observed=json.loads(run([binary,'integrated-build',spec_path,out/name],out/f'{name}-build.log',args.timeout))
                path=out/name/'integrated.mdx';paths[name]=path;before=file_hash(path)
                # A separate process reconstructs the adapter index from the file
                # and persisted policy tag, not a retained build-time index.
                reopened=json.loads(run([binary,'integrated-inspect',spec_path,path],out/f'{name}-reopen.log',args.timeout))
                expected=sorted(rows,key=lambda r:norms[profile][r['key']])
                require(observed['rows']==reopened['rows']==expected,'Versioned physical order/duplicates/payload differs')
                require(read_python(path,'mdx')==[(r['key'],r['text']) for r in expected],'Independent Python physical rows differ')
                for result in [observed,reopened]:
                    require(result['profile']==profile and result['checksum_policy']=='Verify','Wrong integrated policy/checksum mode')
                    require([q['query'] for q in result['lookups']]==queries,'Incomplete integrated lookup inventory')
                    for q in result['lookups']:require(q['rows']==expected_lookup(expected,q['query'],norms[profile]),f"Versioned lookup differs: {q['query']!r}")
                attrs=reopened['attributes'];require(attrs['StudioCasingPolicy']==profile and attrs['StripKey']=='No' and attrs['KeyCaseSensitive']=='No','Persisted policy metadata differs')
                if profile==LEGACY:require(attrs['StudioCasingDataSha256']==SHA16,'Persisted data identity differs')
                wire=audit(path);require(wire['status']=='structural_audit_passed' and wire['records_without_terminal_null']==0,'Integrated wire audit failed')
                require(observed['key_blocks']>2 and observed['record_blocks']>1,'Integrated case did not cross blocks')
                require(file_hash(path)==before,'Reopen changed dictionary bytes')
                builtin=[{'query':a['query'],'adapter':a['rows'],'builtin':b['rows']} for a,b in zip(reopened['lookups'],reopened['builtin_engine_lookups']) if a['rows']!=b['rows']]
                report['checks'][name]={'status':'passed','records':len(expected),'queries':len(queries),'key_blocks':observed['key_blocks'],'record_blocks':observed['record_blocks'],
                    'sha256':before,'persisted_profile':profile,'reopened_in_separate_process':True,'physical_and_lookup_order_exact':True,
                    'builtin_locator_difference_count':len(builtin),'builtin_locator_difference_examples':builtin[:4]}
                observations[name]=reopened
        old=f'{LEGACY}-utf8';modern=f'{MODERN}-utf8'
        profile_diffs=[a['query'] for a,b in zip(observations[old]['lookups'],observations[modern]['lookups']) if a['rows']!=b['rows']]
        require(profile_diffs,'Fixture did not distinguish declared casing policies')
        require(report['checks'][old]['builtin_locator_difference_count']>0,'Fixture did not distinguish pinned adapter from unmodified built-in locator')
        report['policy_difference_queries']=profile_diffs
        assert_refusal(binary,specs[modern],paths[old],out/'wrong-profile.log',args.timeout,'Dictionary casing policy does not match requested policy')
        unknown=out/'unknown-policy.mdx';unknown.write_bytes(rewrite_header(paths[old].read_bytes(),[(f' StudioCasingPolicy="{LEGACY}"',' StudioCasingPolicy="unknown-v999"')]))
        assert_refusal(binary,specs[old],unknown,out/'unknown-policy.log',args.timeout,'Dictionary casing policy does not match requested policy')
        bad_hash=out/'wrong-policy-hash.mdx';bad_hash.write_bytes(rewrite_header(paths[old].read_bytes(),[(f' StudioCasingDataSha256="{SHA16}"',' StudioCasingDataSha256="wrong"')]))
        assert_refusal(binary,specs[old],bad_hash,out/'wrong-policy-hash.log',args.timeout,'Unrecognized Unicode16 casing data identity')
        report['negative_checks']={'wrong_requested_policy':'rejected','unknown_persisted_policy':'rejected','wrong_persisted_data_identity':'rejected'}
        require(file_hash(policy)==SHA16,'Pinned data changed during qualification')
        report['status']='versioned_adapter_sort_lookup_roundtrip_passed_native_and_production_pending_M1_open'
    except Exception as error:report['status']='failed_integrated_casing_qualification';report['error']=str(error)
    (out/'integrated-casing-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {out/'integrated-casing-report.json'}")
    return 0 if report['status']=='versioned_adapter_sort_lookup_roundtrip_passed_native_and_production_pending_M1_open' else 1


if __name__=='__main__':raise SystemExit(main())
