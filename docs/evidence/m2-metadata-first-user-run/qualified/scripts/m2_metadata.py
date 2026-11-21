"""Qualify metadata-only v2 rebuilds; preserve binary sections and raw markers."""
import argparse
import hashlib
import html
import importlib.metadata
import json
import locale
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET
import zlib
from m2_v2_import import ROOT,require
from v2_import_lock import MANIFEST,LOCK,check_lock
from v2_import_fixtures import generate,rewrite,read_legacy_physical
from v2_audit import audit
from stylesheet_controls import specification,official_reference_stylesheet

APP='m2/v2-import/src/application.rs'
EXTENSION=b'\npub mod metadata;\n'
STYLE='1\n<span style="color:#1d4ed8;text-decoration:underline;">\n</span>\n2\n<b>\n</b>\n'
DESCRIPTION='Line one\nLine two\r\nTab\there & <tags> "quotes" apostrophe\' literal &amp; &#10; 字 العربية 𠀀'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def protected_sources():
    directory=ROOT/'docs/evidence/m2-import-jobs-user-run';report=json.loads((directory/'m2-import-jobs-report.json').read_text())
    expected={**report['protected_source_sha256'],**report['source_sha256']}
    for name,digest in expected.items():
        if name==APP:
            old=(directory/'qualified'/name).read_bytes();require(hashlib.sha256(old).hexdigest()==digest,'Accepted application snapshot changed')
            require((ROOT/name).read_bytes()==old+EXTENSION,'Application changed beyond metadata module export')
        else:require(sha(ROOT/name)==digest,f'Qualified source changed: {name}')
    return {name:sha(ROOT/name) for name in expected}
def fingerprints():
    paths=[p for p in (ROOT/'m2/v2-import').rglob('*') if p.is_file() and 'target' not in p.relative_to(ROOT/'m2/v2-import').parts and p.suffix in {'.rs','.toml','.lock'}]
    paths += [ROOT/'scripts/m2_metadata.py',ROOT/'scripts/test_m2_metadata.py']
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def header(data):
    n=struct.unpack_from('>I',data)[0];raw=data[4:n+4]
    require(len(raw)==n and zlib.adler32(raw)&0xffffffff==struct.unpack_from('<I',data,n+4)[0],'Header framing/checksum differs')
    xml=raw.decode('utf-16le').removesuffix('\0');element=ET.fromstring(xml)
    known=['GeneratedByEngineVersion','RequiredEngineVersion','Encrypted','Encoding','Format','KeyCaseSensitive','StripKey','Title','Description','StyleSheet','Compact','Compat']
    attrs={}
    for key,value in re.findall(r'([A-Za-z_][A-Za-z0-9_.-]*)="([^"]*)"',xml,re.S):
        name=next((k for k in known if k.lower()==key.lower()),key);require(name not in attrs,'Duplicate header alias');attrs[name]=html.unescape(value)
    return n,raw,xml,attrs,element
def check_output(source,destination,edits,summary,kind):
    before=source.read_bytes();after=destination.read_bytes();n,_,_,original,_=header(before);m,raw,xml,attrs,element=header(after)
    expected=dict(original)
    for name,value in edits.items():expected[{'title':'Title','description':'Description','stylesheet':'StyleSheet'}[name]]=value
    if expected.get('StyleSheet'):expected['Compact']='Yes'
    require(before[n+8:]==after[m+8:],'Metadata rebuild changed binary sections')
    require(attrs==expected==summary['header']['attributes'],'Header values changed or an unknown attribute was lost')
    require(summary['header']['raw_utf16le']==list(raw) and summary['header']['raw_xml']==xml,'Raw rebuilt header differs')
    require(summary['profile']=='mdict-v2-metadata-v1' and summary['file_bytes']==len(after),'Wrong profile/size')
    require(element.tag==('Dictionary' if kind=='mdx' else 'Library_Data'),'Wrong rebuilt root')
    for name,value in element.attrib.items():
        canonical=next((k for k in attrs if k.lower()==name.lower()),name)
        if canonical!='StyleSheet':require(value==attrs[canonical],'Standard XML multiline metadata did not preserve characters')
    style=expected.get('StyleSheet','')
    if style:require('StyleSheet="'+html.escape(style,quote=True).replace('&#x27;',"'")+'"' in xml,'Stylesheet LF/terminal-LF wire contract changed')
    require(audit(destination)['status']=='structural_audit_passed','Rebuilt file failed independent wire audit')
    rows=read_legacy_physical(destination,kind)
    require(rows==read_legacy_physical(source,kind),'Python/raw-wire physical records differ after rebuild')
    require(summary['records']==len(rows),'Physical count mismatch')
    return {'records':len(rows),'binary_sections_exact':True,'raw_and_decoded_metadata_exact':True,'standard_XML_non_stylesheet_metadata_exact':True,
        'standard_XML_stylesheet_value_equals_raw':element.attrib.get('StyleSheet','')==style,'style_rules':summary['stylesheet_rules']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_metadata_failed','M1':'complete_unchanged','M2_complete':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],
        'scope':'bounded metadata-only v2 rebuild with unchanged binary sections, explicit MDict stylesheet LF convention and XML character-reference whitespace in other attributes',
        'native_readers':'NOT_RUN_AWAIT_OFFLINE_REVIEW','entry_repacking':False,'background_metadata_publication':False}
    def run(label,command,refusal=None):
        print(f'Running {label}',flush=True);r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8');text=r.stdout+'\nSTDERR:\n'+r.stderr
        (out/(label+'.log')).write_text(text);step={'name':label,'returncode':r.returncode};report['steps'].append(step)
        if refusal:
            require(r.returncode==1 and not r.stdout.strip(),f'{label}: wrong refusal');value=json.loads(r.stderr.strip().splitlines()[-1]);require(value['error']['code']==refusal,f'{label}: wrong typed error {value}');step['expected_refusal']=refusal;return value
        if r.returncode:step['failure_log_tail']=text[-64000:]
        require(r.returncode==0,f'{label} failed; see embedded log tail');return json.loads(r.stdout) if r.stdout.strip().startswith('{') else None
    try:
        report['stage']='preflight';require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing .venv mdict-utils==1.3.14');locale.setlocale(locale.LC_COLLATE,'C')
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_contents']=(ROOT/LOCK).read_text()
        cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac')
        report['stage']='rust_tests';run('refresh-metadata-artifacts',[cargo,'clean','--locked','--offline','--manifest-path',MANIFEST,'--package','studio-v2-import'])
        run('metadata-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace'])
        report['stage']='fixtures';cases=generate(out/'inputs');command=[cargo,'run','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-metadata-rebuild','--']
        def rebuild(label,source,kind,edits,destination=None,refusal=None,cancel=None):
            report['stage']=label;destination=destination or out/(label+'.'+kind);before=sha(source);existing=destination.read_bytes() if destination.exists() else None
            request={'source':str(source),'destination':str(destination),'kind':kind,'edits':edits};path=out/(label+'-request.json');path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
            files_before=set(destination.parent.iterdir()) if refusal else None
            value=run(label,command+[str(path)]+([cancel] if cancel else []),refusal)
            require(sha(source)==before,'Source dictionary changed')
            if refusal:
                require(destination.read_bytes()==existing if existing is not None else not destination.exists(),'Failure changed/published destination')
                # Logs/request JSON are written outside the stage destination
                # directory for cancellation probes, so no staging residue may remain.
                if cancel:require(set(destination.parent.iterdir())==files_before,'Cancelled rebuild left staging residue')
                report['checks'].append({'case':label,'status':'expected_refusal','code':refusal,'input_sha256':before});return destination
            (out/(label+'-actual.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
            check=check_output(source,destination,edits,value['summary'],kind);report['checks'].append({'case':label,'status':'metadata_sections_records_passed','input_sha256':before,'output_sha256':sha(destination),**check});return destination
        positives=[c for c in cases if re.fullmatch(r'utf(?:8|16)-case[01]-strip[01]',c['name']) or c['name'] in {'utf8-missing-raw','utf16-missing-raw','mdd-duplicates'}]
        for case in positives:
            edits={'title':'Title & "quoted" <字> العربية 𠀀','description':DESCRIPTION}
            if case['kind']=='mdx':edits['stylesheet']=STYLE
            rebuild('metadata-'+case['name'],case['path'],case['kind'],edits)
        base=cases[0]['path']
        # Foreign extension fields, missing flags and unknown data-source labels
        # must survive this operation without a metadata whitelist dropping them.
        extension=out/'inputs/extension.mdx';extension.write_bytes(rewrite(base.read_bytes(),{'ForeignExtension':'A\nB & <字>','DataSourceFormat':'106'}))
        rebuild('unknown-attributes',extension,'mdx',{'description':DESCRIPTION})
        for label,edits,code in [
            ('missing-final-lf',{'stylesheet':'1\n<b>\n</b>'},'unsupported_policy'),
            ('crlf-stylesheet',{'stylesheet':'1\r\n<b>\r\n</b>\r\n'},'unsupported_policy'),
            ('incomplete-triplet',{'stylesheet':'1\n<b>\n'},'invalid_input'),
            ('duplicate-style-id',{'stylesheet':'1\n<b>\n</b>\n1\n<i>\n</i>\n'},'invalid_input'),
            ('dangling-marker',{'stylesheet':'2\n<b>\n</b>\n'},'invalid_input'),
            ('clear-live-styles',{'stylesheet':''},'invalid_input'),
            ('invalid-xml-control',{'title':'bad\x01'},'invalid_input'),
            ('oversized-metadata',{'description':'𠀀'*20000},'limit_exceeded'),
            ('escaped-header-budget',{'description':'&'*20000},'limit_exceeded'),
            ('utf16-header-budget',{'description':'a'*40000},'limit_exceeded')]:rebuild(label,base,'mdx',edits,refusal=code)
        corrupted=next(c['path'] for c in cases if c['name']=='bad-record-checksum');rebuild('corrupt-source',corrupted,'mdx',{},refusal='integrity')
        text=out/'inputs/text-format.mdx';text.write_bytes(rewrite(base.read_bytes(),{'Format':'Text'}));rebuild('styles-on-text',text,'mdx',{},refusal='unsupported_policy')
        mdd=next(c['path'] for c in cases if c['kind']=='mdd');rebuild('styles-on-mdd',mdd,'mdd',{'stylesheet':STYLE},refusal='unsupported_policy')
        sentinel=out/'existing.mdx';sentinel.write_bytes(b'sentinel');rebuild('existing-destination',base,'mdx',{},destination=sentinel,refusal='destination_exists')
        rebuild('source-equals-destination',base,'mdx',{},destination=base,refusal='destination_exists')
        cancel_dir=out/'cancel-probes';cancel_dir.mkdir()
        for phase in ['header','metadata_copy','metadata_commit']:rebuild('cancel-'+phase,base,'mdx',{},destination=cancel_dir/(phase+'.mdx'),refusal='cancelled',cancel=phase)
        native=out/'native';native.mkdir();spec=specification();style=official_reference_stylesheet();entries=spec['cases'][0]['entries']
        for encoding in ['utf8','utf16']:
            seed=out/'inputs'/('native-seed-'+encoding+'.mdx');seed_request=out/('native-seed-'+encoding+'.json');seed_request.write_text(json.dumps({'title':'Metadata stylesheet '+encoding,'description':'Seed only','encoding':encoding,'entries':entries},ensure_ascii=False)+'\n')
            run('seed-'+encoding,command+['seed',str(seed_request),str(seed)])
            destination=rebuild('native-'+encoding,seed,'mdx',{'title':'Metadata stylesheet '+encoding,'description':'Line one\nLine two & <tags> "quotes"','stylesheet':style},destination=native/('metadata-'+encoding+'.mdx'))
            from mdict_utils.base.readmdict import MDX
            rendered=[(k.decode('utf-8'),v.decode('utf-8')) for k,v in MDX(str(destination),substyle=True).items()]
            expected=sorted([(e['key'],spec['rendered'].get(e['key'],e['text'])) for e in entries])
            require(rendered==expected,'Python numeric marker expansion differs from inline controls');report['checks'][-1]['python_marker_expansion_exact']=True
        (native/'READ-ME.txt').write_text('After offline report review: test one MDX at a time in MDict and GoldenDict.\nCheck inline-red and marker-red: STYLE_ONE_OK in red/bold/border.\nCheck inline-blue and marker-blue: STYLE_TWO_OK in blue/underlined.\nCheck plain: PLAIN_CONTROL_OK. All five entries must exist. Restart and repeat.\nThese are standalone MDX files; no MDD is required.\n')
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Source identities changed');check_lock()
        report['native_files']=[{'path':str(p.relative_to(out)),'sha256':sha(p)} for p in sorted(native.glob('*.mdx'))]
        report['status']='m2_metadata_rebuild_offline_passed_native_checks_pending';report['stage']='complete'
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
    path=out/'m2-metadata-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_metadata_failed')
if __name__=='__main__':raise SystemExit(main())
