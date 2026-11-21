"""Qualify metadata-aware new-entry packing and serial file publication."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import traceback
import unicodedata
from m2_v2_import import ROOT,require
from m2_metadata import header,source_record_oracle,DESCRIPTION
from v2_import_lock import MANIFEST,LOCK,check_lock
from v2_import_fixtures import ROWS,read_legacy_physical
from v2_audit import audit
from stylesheet_controls import specification,official_reference_stylesheet

MODULE='m2/v2-import/src/application/metadata.rs'
EXTENSION=b'\npub mod publication;\n'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def protected_sources():
    directory=ROOT/'docs/evidence/m2-metadata-user-run';r=json.loads((directory/'m2-metadata-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for name,digest in expected.items():
        if name==MODULE:
            old=(directory/'qualified'/name).read_bytes();require(hashlib.sha256(old).hexdigest()==digest,'Accepted metadata snapshot changed')
            require((ROOT/name).read_bytes()==old+EXTENSION,'Metadata implementation changed beyond publication module export')
        else:require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return {name:sha(ROOT/name) for name in expected}
def fingerprints():
    paths=[p for p in (ROOT/'m2/v2-import').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/v2-import').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_metadata_jobs.py',ROOT/'scripts/test_m2_metadata_jobs.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def metadata(style='1\n<span style="color:blue">\n</span>\n'):
    return {'title':'Packed metadata 字 العربية & "quoted"','description':DESCRIPTION,'stylesheet':style,'extra':{'ForeignExtension':'A\nB\r\nC\t<&amp;>','DataSourceFormat':'106'}}
def cases(directory):
    directory.mkdir();items=[]
    def add(name,request,refusal=None,native=False):items.append({'name':name,'request':request,'refusal':refusal,'native':native})
    def mdx(name,encoding='utf8',rows=ROWS,meta=None):return {'operation':'pack_mdx','destination':str(directory/(name+'.mdx')),'encoding':encoding,'metadata':copy.deepcopy(meta or metadata()),'entries':copy.deepcopy(rows)}
    def mdd(name):return {'operation':'pack_mdd','destination':str(directory/(name+'.mdd')),'metadata':metadata(''),'resources':[{'key':'data/all.bin','bytes':list(range(256))},{'key':'data/all.bin','bytes':[0,255,128]},{'key':'empty.bin','bytes':[]},{'key':'../raw.bin','bytes':[1,2,3]}]}
    for encoding in ['utf8','utf16']:add('pack-'+encoding,mdx('pack-'+encoding,encoding))
    for encoding in ['utf8','utf16']:add('plain-'+encoding,mdx('plain-'+encoding,encoding,[{'key':'empty','text':''},{'key':'字','text':'A\r\n\nB\n`literal`'}],metadata('')))
    resource=mdd('pack-mdd');add('pack-mdd',resource)
    source=Path(items[0]['request']['destination'])
    add('rebuild-mdx',{'operation':'rebuild','request':{'source':str(source),'destination':str(directory/'rebuild.mdx'),'kind':'mdx','edits':{'title':'Rebuilt title','description':'New\r\nmetadata\t&'}}})
    add('rebuild-mdd',{'operation':'rebuild','request':{'source':resource['destination'],'destination':str(directory/'rebuild.mdd'),'kind':'mdd','edits':{'description':'New\nresource metadata'}}})
    sentinel=directory/'existing.mdx';sentinel.write_bytes(b'KEEP_SENTINEL')
    existing=mdx('existing');existing['metadata']['title']='MUST NOT REPLACE';add('existing-destination',existing,'destination_exists')
    existing=mdx('pack-utf8');existing['metadata']['title']='MUST NOT REPLACE';add('existing-packed-destination',existing,'destination_exists')
    bad=mdx('structural-override');bad['metadata']['extra']['Stripkey']='Yes';add('structural-override',bad,'invalid_input')
    bad=mdx('namespace-override');bad['metadata']['extra']['xmlns']='urn:foreign';add('namespace-override',bad,'invalid_input')
    bad=mdx('xml-control');bad['metadata']['title']='bad\x01';add('xml-control',bad,'invalid_input')
    bad=mdx('missing-styles');bad['metadata']['stylesheet']='';add('missing-styles',bad,'invalid_input')
    bad=mdx('duplicate-styles');bad['metadata']['stylesheet']='1\n<b>\n</b>\n1\n<i>\n</i>\n';add('duplicate-styles',bad,'invalid_input')
    bad=mdx('missing-final-lf');bad['metadata']['stylesheet']='1\n<b>\n</b>';add('missing-final-lf',bad,'unsupported_policy')
    bad=mdx('crlf-styles');bad['metadata']['stylesheet']='1\r\n<b>\r\n</b>\r\n';add('crlf-styles',bad,'unsupported_policy')
    bad=mdd('mdd-styles');bad['metadata']['stylesheet']=metadata()['stylesheet'];add('mdd-styles',bad,'unsupported_policy')
    bad=mdx('empty-key');bad['entries'][0]['key']='';add('empty-key',bad,'invalid_input')
    bad=mdx('nul-definition');bad['entries'][0]['text']='bad\0';add('nul-definition',bad,'invalid_input')
    bad=mdx('oversized-definition');bad['entries'][0]['text']='x'*(1024*1024+1);add('oversized-definition',bad,'limit_exceeded')
    bad=mdx('oversized-key');bad['entries'][0]['key']='x'*4097;add('oversized-key',bad,'limit_exceeded')
    bad=mdx('too-many-entries');bad['entries']=[{'key':'x','text':'a'}]*1001;add('too-many-entries',bad,'limit_exceeded')
    bad=mdx('encoded-header-budget');bad['metadata']['description']='a'*40000;add('encoded-header-budget',bad,'limit_exceeded')
    add('missing-source',{'operation':'rebuild','request':{'source':str(directory/'missing.mdx'),'destination':str(directory/'missing-output.mdx'),'kind':'mdx','edits':{}}},'io')
    add('clear-live-styles',{'operation':'rebuild','request':{'source':str(source),'destination':str(directory/'clear-styles.mdx'),'kind':'mdx','edits':{'stylesheet':''}}},'invalid_input')
    add('recovery-pack',mdx('recovery-pack','utf8',[{'key':'recovered','text':'`1`RECOVERY_OK'}]))
    spec=specification()
    for encoding in ['utf8','utf16']:
        add('native-'+encoding,mdx('native-'+encoding,encoding,spec['cases'][0]['entries'],{'title':'Packed stylesheet '+encoding,'description':'New-entry packing\nMetadata retained','stylesheet':official_reference_stylesheet(),'extra':{}}),native=True)
    return items
def destination(request):return Path(request['destination'] if request['operation']!='rebuild' else request['request']['destination'])
def compare_job(actual,case,background):
    if case['refusal']:
        require(actual['state'] in {'failed','rejected'} and actual['response'] is None and actual['error']['code']==case['refusal'],'Wrong publication refusal or partial result')
        require(not actual['error'].get('publication_uncertain',actual.get('publication_uncertain',True)),'Ordinary refusal incorrectly reports uncertain publication')
    else:
        require(actual['state']=='succeeded' and actual['error'] is None and actual['response'] is not None,'Expected committed publication')
    if background and actual['state']!='rejected':
        terminal=actual['terminal'];require(terminal['state']==actual['state'] and terminal['result_available']==(actual['state']=='succeeded'),'Wrong terminal/summary availability')
        require(actual['taken_once'] and actual['forgotten'] and actual['late_cancel']=='already_finished' and not actual['collected']['result_available'],'Publication summary/lifecycle mismatch')
        require(len(actual['events'])==1 and actual['events'][0]['job_id']==terminal['job_id'],'Publication mailbox not coalesced')
        if terminal['latest_progress']:require(terminal['latest_progress']['job_id']==terminal['job_id'],'Progress job ID mismatch')
def compare_file(case,response):
    req=case['request'];path=destination(req);kind='mdd' if path.suffix=='.mdd' else 'mdx';data=path.read_bytes();n,raw,xml,attrs,element=header(data)
    require(response['destination']==str(path) and response['profile']=='mdict-v2-metadata-v1' and response['file_bytes']==len(data),'Publication summary differs from file')
    require(response['operation']=={'pack_mdx':'pack_metadata_mdx','pack_mdd':'pack_metadata_mdd','rebuild':'rebuild_metadata'}[req['operation']],'Wrong publication operation')
    if req['operation']=='rebuild':
        source=Path(req['request']['source']);original=source.read_bytes();m,_,_,expected,_=header(original)
        expected.update({{'title':'Title','description':'Description','stylesheet':'StyleSheet'}[k]:v for k,v in req['request']['edits'].items()})
        if expected.get('StyleSheet'):expected['Compact']='Yes'
        require(attrs==expected and original[m+8:]==data[n+8:],'Rebuild changed header semantics or binary sections')
        expected_rows=source_record_oracle(source,kind)
    else:
        meta=req['metadata'];wanted={'Title':meta['title'],'Description':meta['description'],'StyleSheet':meta['stylesheet'],**meta['extra']}
        require(all(attrs.get(k)==v for k,v in wanted.items()),'Packed metadata changed values')
        require(attrs.get('StripKey')=='No' and attrs.get('KeyCaseSensitive')=='No','Packed structural lookup policy changed')
        require(element.tag==('Dictionary' if kind=='mdx' else 'Library_Data'),'Wrong packed header root')
        if kind=='mdx':
            require(attrs['Encoding']==('UTF-8' if req['encoding']=='utf8' else 'UTF-16') and attrs['Format'].lower()=='html','Wrong MDX encoding/format')
            require(attrs['Compact']==('Yes' if meta['stylesheet'] else 'No'),'Compact/style contract changed')
            expected_rows=[(r['key'],r['text']) for r in sorted(req['entries'],key=lambda r:r['key'].lower())]
        else:expected_rows=[(r['key'],bytes(r['bytes'])) for r in sorted(req['resources'],key=lambda r:r['key'].lower())]
    for name,value in element.attrib.items():
        if name!='StyleSheet':require(value==attrs[name],'Standard XML metadata differs')
    require(read_legacy_physical(path,kind)==expected_rows and response['records']==len(expected_rows),'Packed physical order, duplicates or payload changed')
    require(audit(path)['status']=='structural_audit_passed','Published file failed independent wire audit')
    if case['native']:
        from mdict_utils.base.readmdict import MDX
        spec=specification();expected=sorted([(e['key'],spec['rendered'].get(e['key'],e['text'])) for e in spec['cases'][0]['entries']])
        rendered=[(k.decode('utf-8'),v.decode('utf-8')) for k,v in MDX(str(path),substyle=True).items()];require(rendered==expected,'Fresh packed numeric styles differ from inline controls')
    return {'records':len(expected_rows),'output_sha256':sha(path),'metadata_records_wire_passed':True,'Python_marker_expansion_passed':case['native']}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_metadata_jobs_failed','M1':'complete_unchanged','M2_complete':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded fresh Unicode16-literal MDX/MDD metadata packing and dedicated serial publication worker; existing metadata-only rebuild route reused','native_readers':'NOT_RUN_AWAIT_OFFLINE_REVIEW'}
    def run(label,command,parse=False):
        print(f'Running {label}',flush=True);r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8');text=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(label+'.log')).write_text(text)
        step={'name':label,'returncode':r.returncode};report['steps'].append(step)
        if r.returncode:step['failure_log_tail']=text[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded log tail');return json.loads(r.stdout) if parse else None
    try:
        report['stage']='preflight';require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing .venv mdict-utils==1.3.14');require(unicodedata.unidata_version=='16.0.0','Use the qualified Unicode16 Python environment')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_contents']=(ROOT/LOCK).read_text();cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        report['stage']='rust_tests';run('refresh-publication-artifacts',[cargo,'clean','--locked','--offline','--manifest-path',MANIFEST,'--package','studio-v2-import']);run('metadata-publication-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace'])
        command=[cargo,'run','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-metadata-jobs','--'];receipt={}
        for mode in ['sync','background']:
            report['stage']=mode;batch_cases=cases(out/mode);batch=out/(mode+'-requests.json');batch.write_text(json.dumps({'requests':[c['request'] for c in batch_cases]},ensure_ascii=False,indent=2)+'\n')
            actual=run(mode+'-batch',command+[mode,str(batch)],True);(out/(mode+'-actual.json')).write_text(json.dumps(actual,ensure_ascii=False,indent=2)+'\n');require(actual['mode']==mode and len(actual['jobs'])==len(batch_cases),'Batch job inventory differs')
            expected_files={'existing.mdx'};receipt[mode]=[]
            for index,(case,job) in enumerate(zip(batch_cases,actual['jobs'])):
                report['stage']=mode+':'+case['name'];require(job['index']==index,'Batch order changed');compare_job(job,case,mode=='background')
                check={'mode':mode,'case':case['name'],'status':'expected_refusal' if case['refusal'] else 'publication_oracle_passed','state':job['state']}
                if case['refusal']:check['code']=case['refusal']
                else:check.update(compare_file(case,job['response']));expected_files.add(destination(case['request']).name)
                report['checks'].append(check);receipt[mode].append((case['name'],bool(case['refusal']),case['refusal']))
            require((out/mode/'existing.mdx').read_bytes()==b'KEEP_SENTINEL','Existing destination changed');require({p.name for p in (out/mode).iterdir()}==expected_files,'Partial destination or staging residue left behind')
        require(receipt['sync']==receipt['background'],'Route case inventory differs');require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Source identities changed during qualification');check_lock()
        report['native_files']=[{'path':str(p.relative_to(out)),'sha256':sha(p)} for p in sorted((out/'background').glob('native-*.mdx'))]
        report['status']='m2_metadata_packing_publication_offline_passed_native_checks_pending';report['stage']='complete'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
    path=out/'m2-metadata-jobs-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_metadata_jobs_failed')
if __name__=='__main__':raise SystemExit(main())
