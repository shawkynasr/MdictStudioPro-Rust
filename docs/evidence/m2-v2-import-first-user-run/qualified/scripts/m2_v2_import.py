"""Qualify bounded ordinary v2 import, explicit lookup and redirects."""
import argparse
import hashlib
import importlib.metadata
import json
import locale
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from v2_import_lock import ROOT,MANIFEST,LOCK,check_lock
from v2_import_fixtures import generate,QUERIES,REDIRECTS,lookup,resolve
from v2_audit import audit

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise AssertionError(message)
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-dictionary-jobs-user-run/m2-dictionary-jobs-report.json').read_text())
    expected={**r['protected_source_sha256'],**r['source_sha256']}
    for name,digest in expected.items():require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return expected
def fingerprints(include_lock=True):
    paths=[p for p in (ROOT/'m2/v2-import').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/v2-import').parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts/m2_v2_import.py',ROOT/'scripts/v2_import_lock.py',ROOT/'scripts/v2_import_fixtures.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def compare_header(actual,path):
    data=path.read_bytes();n=struct.unpack_from('>I',data)[0];raw=data[4:4+n];xml=raw.decode('utf-16le').removeprefix('\ufeff').removesuffix('\0')
    require(actual['raw_utf16le']==list(raw) and actual['raw_xml']==xml,'Raw header bytes/XML changed')
    attrs=dict(ET.fromstring(xml).attrib)
    known=['GeneratedByEngineVersion','RequiredEngineVersion','Encrypted','Encoding','Format','KeyCaseSensitive','StripKey','Title','Description','StyleSheet','Compact','Compat']
    attrs={next((k for k in known if k.lower()==name.lower()),name):value for name,value in attrs.items()}
    require(actual['attributes']==attrs,'Header attribute decoding changed')
    require(not any(k.startswith('Studio') for k in attrs),'Fixture unexpectedly requires Studio tags')
def compare_query(actual,action):
    try:expected=action()
    except ValueError as e:
        require('error' in actual and actual['error']['detail']==str(e),'Wrong all-or-error lookup/redirect result');return 'expected_query_error'
    field='entries' if 'entries' in actual else 'results'
    require('error' not in actual and actual.get(field)==expected,'Query lost/reordered duplicates, changed content or redirect chain');return 'exact_query_result'
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_v2_import_failed','M1':'complete_unchanged','M2_complete':False,'v2_import_runtime_qualified':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded ordinary unencrypted UTF8/UTF16 v2 MDX/MDD import, explicit exact/header-ASCII lookup, physical duplicate identity and redirect resolution','native_readers':'NOT_REQUESTED'}
    def run(label,command,parse=False,refusal=None):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True);r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict');combined=r.stdout+'\nSTDERR:\n'+r.stderr
        log.write_text(combined,encoding='utf-8');step={'name':label,'returncode':r.returncode,'log':log.name};report['steps'].append(step)
        if refusal:
            require(r.returncode==1 and not r.stdout.strip(),f'{label}: wrong refusal; return {log.name}')
            e=json.loads(r.stderr.strip().splitlines()[-1]);require(e['error']['code']==refusal,f'{label}: wrong refusal code; return {log.name}');step['expected_refusal']=refusal;return None
        if r.returncode!=0:step['failure_log_tail']=combined[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded output or {log.name}');return json.loads(r.stdout) if parse else None
    try:
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing .venv mdict-utils==1.3.14');locale.setlocale(locale.LC_COLLATE,'C')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock()
        cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        # Only this new workspace may canonicalize path/development edges.
        # Offline resolution uses the seeded graph; registry identities are
        # checked immediately, and the complete resulting lock is returned.
        try:run('import-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:
            report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        require({k:v for k,v in fingerprints().items() if k!=LOCK}=={k:v for k,v in report['source_sha256'].items() if k!=LOCK},'Non-lock source changed during compilation')
        command=[cargo,'run','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-v2-import','--']
        for case in generate(out/'inputs'):
            source=case['path'];before=sha(source);request={'kind':case['kind'],'path':str(source),'policy':case.get('policy'),'queries':QUERIES if case['kind']=='mdx' else ['\\data\\dup.bin','empty.bin','../raw.bin','missing'],
                'resolve':REDIRECTS if case['kind']=='mdx' else [],'max_results':case.get('max_results'),'max_hops':case.get('max_hops'),'max_entries':case.get('max_entries')}
            path=out/(case['name']+'-request.json');path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
            actual=run(case['name'],command+[str(path)],True,case.get('refusal'))
            if case.get('refusal'):report['checks'].append({'case':case['name'],'status':'expected_refusal','code':case['refusal'],'input_sha256':before})
            else:
                (out/(case['name']+'-actual.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n');compare_header(actual['header'],source)
                wire=audit(source);require(wire['status']=='structural_audit_passed','Foreign fixture failed independent wire audit')
                query_counts={'exact_query_result':0,'expected_query_error':0}
                if case['kind']=='mdx':
                    require(actual['entries']==case['rows'],'Physical MDX rows differ from independent Python reader')
                    require(actual['policy']==('raw-exact-v1' if case['policy']=='raw_exact' else 'header-ascii-strip-unicode16-v1'),'Lookup policy identity changed')
                    require([q['query'] for q in actual['queries']]==QUERIES and [q['query'] for q in actual['resolutions']]==REDIRECTS,'Missing/reordered query requests')
                    for q in actual['queries']:
                        result=compare_query(q,lambda q=q:lookup(case['rows'],q['query'],case['policy'],case['case_sensitive'],case['strip'],case.get('max_results',256)));query_counts[result]+=1
                    require(len(actual['queries'])==len(QUERIES) and len(actual['resolutions'])==len(REDIRECTS),'Missing requested queries')
                    for q in actual['resolutions']:
                        result=compare_query(q,lambda q=q:resolve(case['rows'],q['query'],case['policy'],case['case_sensitive'],case['strip'],case.get('max_hops',16),case.get('max_results',256)));query_counts[result]+=1
                    records=len(case['rows'])
                else:
                    require(actual['resources']==case['resources'],'Physical resource bytes/duplicates differ')
                    require(actual['policy']=='resource-raw-exact-v1' and [q['query'] for q in actual['queries']]==request['queries'],'MDD query/policy identity changed')
                    for q in actual['queries']:require(q.get('resources')==[r for r in case['resources'] if r['key']==q['query']],'Resource exact lookup changed duplicate identity')
                    records=len(case['resources'])
                report['checks'].append({'case':case['name'],'status':'physical_rows_header_queries_and_wire_passed','records':records,'query_checks':query_counts,'input_sha256':before})
            require(sha(source)==before,'Importer or oracle changed source bytes')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Qualified/import sources changed during verification');check_lock()
        report['v2_import_runtime_qualified']=True;report['status']='m2_ordinary_v2_import_lookup_passed_application_routing_pending'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}'
    path=out/'m2-v2-import-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}",flush=True);return 0 if report['v2_import_runtime_qualified'] else 1
if __name__=='__main__':raise SystemExit(main())
