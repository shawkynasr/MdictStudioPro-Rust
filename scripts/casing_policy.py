"""Qualify explicit Python16 and Rust17 lowercase policies, without MDX writes."""
import argparse
import json
from pathlib import Path
import platform
import random
import sys
import unicodedata
from patched_interop import ROOT,require,verify_candidate_source
from real_rebuild import run
from real_corpus import file_hash
from unicode_profiles import words,mapping_differences

PROFILE='python-unicode-16-root-lower-v1'


def property_flags(char):
    cased=char.islower() or char.isupper() or char.istitle()
    # Derive Case_Ignorable from the exact target implementation's Final_Sigma
    # behavior. Position 1 stays one scalar even if the following char expands.
    # Combining these probes distinguishes ignorable from cased and uncased.
    ignored=('AΣ'+char).lower()[1]=='ς' and ('AΣ'+char+'A').lower()[1]=='σ'
    return cased,ignored


def intervals(values):
    result=[]
    for n in values:
        if result and n==result[-1][1]+1:result[-1][1]=n
        else:result.append([n,n])
    return result


def generate_policy():
    require(platform.python_implementation()=='CPython' and unicodedata.unidata_version=='16.0.0','Generate this policy with CPython Unicode16; use your existing .venv Python')
    mapping=[];cased=[];ignored=[]
    for n in range(0x110000):
        if 0xd800<=n<=0xdfff:continue
        char=chr(n);lower=char.lower()
        if lower!=char:mapping.append([n,lower])
        a,b=property_flags(char)
        if a:cased.append(n)
        if b:ignored.append(n)
    return {'profile':PROFILE,'unicode_version':'16.0.0','lower_mappings':mapping,'cased_ranges':intervals(cased),'case_ignorable_ranges':intervals(ignored)}


def contexts(differences):
    selected=words()+['AΣ\u0345','\u0345Σ','A\u0345Σ','AΣ\u0301A',"AΣ'A",'AΣ\u200dA']
    for row in differences:
        char=row['input'];selected.extend([char,char+'Σ',char+'ΣA','AΣ'+char,'AΣ'+char+'A','A'+char+'Σ'])
    pool=['A','B','a','Σ','σ','ς',"'",'\u0345','\u0301','\u200d','-','İ','ß',' ']+[r['input'] for r in differences]
    rng=random.Random(160017)
    selected.extend(''.join(rng.choice(pool) for _ in range(rng.randrange(1,10))) for _ in range(2048))
    return list(dict.fromkeys(selected))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--timeout',type=float,default=600);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','profiles':[PROFILE,'rust-unicode-17-root-lower-v1'],'engine_integrated':False,'native_readers':'NOT_RUN_NO_NEW_DICTIONARIES',
        'not_proven':['frozen_policy_integrated_in_writer_and_lookup','all_possible_Unicode_strings','official_MdxBuilder_mapping','native_Unicode_lookup','M1_completion']}
    try:
        require(args.timeout>0,'Timeout must be positive')
        reference=ROOT/'docs/evidence/unicode-version-user-run/unicode-profile-report.json'
        prior=json.loads(reference.read_text(encoding='utf-8'));differences=prior['lowercase_mapping']['differences']
        require(prior['lowercase_mapping']['python_unicode_version']=='16.0.0' and prior['lowercase_mapping']['rust_unicode_version']==[17,0,0] and len(differences)==28,'Unexpected prior Unicode finding')
        table=generate_policy();policy=out/'unicode16-casing.json'
        policy.write_text(json.dumps(table,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
        require(len(table['lower_mappings'])==1460,'Target Python16 mapping count differs from received evidence')
        selected=contexts(differences);spec=out/'casing-spec.json'
        spec.write_text(json.dumps({'policy_path':str(policy),'words':selected},ensure_ascii=False)+'\n',encoding='utf-8')
        report['environment']={'python':sys.version,'python_unicode_version':unicodedata.unidata_version}
        report['policy']={'file':policy.name,'sha256':file_hash(policy),'profile':PROFILE,'lower_mappings':len(table['lower_mappings']),
            'cased_ranges':len(table['cased_ranges']),'case_ignorable_ranges':len(table['case_ignorable_ranges']),
            'provenance':'Derived from CPython16 lowercase and casing predicates; Case_Ignorable inferred through Final_Sigma behavior, not copied from official UCD files',
            'status':'candidate_data_upload_for_review_and_hash_freeze'}
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
        report['source_sha256']={str(path.relative_to(ROOT)):file_hash(path) for path in [ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/casing.rs',ROOT/'experiments/real-rebuild/Cargo.lock',Path(__file__).resolve(),reference]}
        result=json.loads(run([binary,'casing-probe',spec],out/'casing-probe.log',args.timeout))
        require(result['profiles']==report['profiles'] and result['engine_integrated'] is False,'Wrong declared casing profiles')
        legacy_count,legacy_diff=mapping_differences({'scalars_scanned':result['scalars_scanned'],'changed_scalar_mappings':result['legacy_changed_mappings']})
        _,modern_diff=mapping_differences({'scalars_scanned':result['scalars_scanned'],'changed_scalar_mappings':result['modern_changed_mappings']})
        require(not legacy_diff and legacy_count==1460,'Frozen Unicode16 scalar output differs from Python oracle')
        require(modern_diff==differences,'Unicode17 differences changed; refusing implicit modern policy drift')
        require([r['word'] for r in result['contexts']]==selected,'Incomplete context observations')
        context_failures=[r for r in result['contexts'] if r['legacy16']!=r['word'].lower()]
        report['legacy_context_failures']=context_failures
        require(not context_failures,'Versioned Unicode16 contextual output differs from Python')
        report['scalar_checks']={'scalars_compared':result['scalars_scanned'],'legacy16_differences':0,'modern17_differences':modern_diff}
        report['context_checks']={'words_checked':len(selected),'legacy16_differences':0,
            'examples_of_intentional_policy_differences':[r for r in result['contexts'] if r['legacy16']!=r['modern17']][:24],
            'scope':'selected edge words and deterministic generated words; not all possible strings'}
        require(file_hash(policy)==report['policy']['sha256'],'Policy table changed during qualification')
        report['status']='versioned_casing_candidate_passed_engine_integration_pending_M1_open'
    except Exception as error:report['status']='failed_versioned_casing_qualification';report['error']=str(error)
    (out/'casing-policy-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {out/'casing-policy-report.json'}")
    return 0 if report['status']=='versioned_casing_candidate_passed_engine_integration_pending_M1_open' else 1


if __name__=='__main__':raise SystemExit(main())
