"""Qualify coherent literal headers and lookup; retain legacy diagnostics.

No existing converter/sort profile is changed. No native apps are launched.
"""
import argparse
import csv
import hashlib
import json
import locale
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib
from patched_interop import ROOT,require,verify_candidate_source,read_python
from real_corpus import file_hash
from real_rebuild import run,stop
from reference_builder import header_details
from v2_audit import audit,block
from fresh_pack import ordered


def entries():
    source=[('a-b','DASH'),('ab','PLAIN'),('aa','AA_BETWEEN'),('a b','SPACE'),('a.b','DOT'),('a!b','EXCLAMATION'),('a\\b','BACKSLASH'),
        ('Apple','TITLE_CASE'),('apple','LOWER_ONE'),('APPLE','UPPER_CASE'),('apple','LOWER_TWO'),
        ('Äpfel','UMLAUT_TITLE'),('äpfel','UMLAUT_LOWER'),('字','CHINESE'),('和','CHINESE_HE'),('مرحبا','ARABIC'),('𠀀','SUPPLEMENTARY')]
    for i in range(48):
        source.append((f'edge-{i:03d}',f'EDGE_{i:03d}'))
        if i%4==0:source.append(('duplicate',f'DUP_{i//4+1:02d}'))
    return [{'key':k,'text':f'<p>{v}</p>'} for k,v in source]


def normalized(key,strip):
    # Deliberately restricted oracle for these fixture characters. No claim of
    # exact historical MdxBuilder mapping or all-Unicode lowercase equivalence.
    key=key.lower()
    return ''.join(c for c in key if not(strip and ord(c)<128 and not c.isalnum()))


def expected_lookup(rows,query,strip):
    exact=[r for r in rows if r['key']==query]
    return exact or [r for r in rows if normalized(r['key'],strip)==normalized(query,strip)]


def rewrite_header(data,replacements):
    require(len(data)<=16*1024*1024,'Only bounded qualification files may be rewritten')
    n=struct.unpack_from('>I',data)[0]
    require(2<=n<=1024*1024 and n%2==0 and n+8<=len(data),'Invalid header geometry')
    xml=data[4:n+4];require(zlib.adler32(xml)&0xffffffff==struct.unpack_from('<I',data,n+4)[0],'Invalid original XML checksum')
    text=xml.decode('utf-16le')
    for before,after in replacements:
        require(text.count(before)==1,'Missing or ambiguous header edit anchor');text=text.replace(before,after,1)
    encoded=text.encode('utf-16le')
    return struct.pack('>I',len(encoded))+encoded+struct.pack('<I',zlib.adler32(encoded)&0xffffffff)+data[n+8:]


def sections(data):
    n=struct.unpack_from('>I',data)[0];return data[n+8:]


def block_membership(path):
    # Small synthetic inputs only. Independent block parser proves duplicate
    # ordinals straddle multiple blocks, not merely that blocks exist.
    data=path.read_bytes();require(len(data)<=16*1024*1024,'Oversized policy fixture')
    attrs=header_details(path)['attributes'];encoding='utf-16le' if attrs['Encoding']=='UTF-16' else 'utf-8';unit=2 if encoding=='utf-16le' else 1
    pos=struct.unpack_from('>I',data)[0]+8
    n,count,raw,packed,key_total=struct.unpack_from('>5Q',data,pos)
    info=block(data[pos+44:pos+44+packed],raw);cursor=0;offset=pos+44+packed;keys=[];members=[]
    for index in range(n):
        number=struct.unpack_from('>Q',info,cursor)[0];cursor+=8
        for _ in range(2):
            length=struct.unpack_from('>H',info,cursor)[0];cursor+=2+(length+1)*unit
        size,decoded=struct.unpack_from('>QQ',info,cursor);cursor+=16
        payload=block(data[offset:offset+size],decoded);offset+=size;at=0
        for _ in range(number):
            at+=8;end=at
            while end+unit<=len(payload) and payload[end:end+unit]!=b'\0'*unit:end+=unit
            require(end+unit<=len(payload),'Missing key terminator')
            keys.append(payload[at:end].decode(encoding));members.append(index);at=end+unit
        require(at==len(payload),'Unexpected key block suffix')
    require(cursor==len(info) and len(keys)==count and offset==pos+44+packed+key_total,'Incomplete key block walk')
    return keys,members


def validate_literal(spec,result,path):
    attrs=result['attributes']
    expected={'StripKey':'No','KeyCaseSensitive':'No','Format':'Html','Compact':'No','Compat':'Yes','StyleSheet':'','Encrypted':'No','Title':spec['title']}
    for key,value in expected.items():require(attrs.get(key)==value,f'Literal metadata mismatch: {key}')
    require('Stripkey' not in attrs and result['resolved_strip'] is False and result['resolved_case_sensitive'] is False,'Ambiguous literal policy')
    expected_rows=sorted(spec['entries'],key=lambda e:e['key'].lower())
    require(result['rows']==expected_rows,'Literal physical order/payload differs')
    require([(r['key'],r['text']) for r in expected_rows]==read_python(path,'mdx'),'Independent Python rows differ')
    require([q['query'] for q in result['lookups']]==spec['queries'],'Incomplete lookup inventory')
    for q in result['lookups']:require(q['rows']==expected_lookup(expected_rows,q['query'],False),f"Literal lookup differs for {q['query']!r}")
    require(result['key_blocks']>2 and result['record_blocks']>2,'Policy case did not cross block boundaries')
    keys,members=block_membership(path)
    require(keys==[r['key'] for r in expected_rows],'Independent block walk differs')
    spans={m for k,m in zip(keys,members) if k=='duplicate'}
    require(len(spans)>=3,'Duplicate group did not span at least three key blocks')
    observed=audit(path);require(observed['status']=='structural_audit_passed','Independent wire audit failed')
    require(observed['records_without_terminal_null']==0,'Unterminated MDX records')
    return {'status':'passed','records':len(expected_rows),'lookups':len(spec['queries']),'duplicate_key_blocks':len(spans),'key_blocks':result['key_blocks'],'record_blocks':result['record_blocks'],'attributes':attrs,'sha256':file_hash(path)}


def diagnostics(result,strip):
    rows=result['rows'];misses=[]
    for q in result['lookups']:
        expected=expected_lookup(rows,q['query'],strip)
        if q['rows']!=expected:misses.append({'query':q['query'],'expected':expected,'actual':q['rows']})
    keys=[normalized(r['key'],strip) for r in rows]
    return {'lookup_differences':misses,'ordering_monotonic_under_reference_lookup':keys==sorted(keys),'attributes':result['attributes'],'resolved_strip':result['resolved_strip'],
        'status':'observed_not_native_qualified','note':'App legacy comparators, backslash regex quirk and reader fallback are separate contracts'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--timeout',type=float,default=600);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'blocked','checks':{},'legacy_diagnostics':{},'alias_checks':{},'native_readers':'NOT_RUN',
        'not_proven':['native_lookup_of_new_candidates','official_MdxBuilder_comparator','legacy_export_native_compatibility','all_Unicode_normalization','general_stylesheet_serialization','M1_completion']}
    try:
        require(args.timeout>0,'Timeout must be positive')
        locale.setlocale(locale.LC_COLLATE,'C')
        run([sys.executable,ROOT/'scripts/prepare_sort_experiment.py','--revision','6','--reuse'],out/'prepare.log',args.timeout)
        vendor=ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6';verify_candidate_source(vendor,6)
        run(['cargo','test','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml'],out/'rust-tests.log',args.timeout)
        built=run(['cargo','build','--locked','--manifest-path','experiments/real-rebuild/Cargo.toml','--message-format=json'],out/'build.log',args.timeout)
        binaries={r['executable'] for line in built.splitlines() if line.startswith('{') for r in [json.loads(line)] if r.get('reason')=='compiler-artifact' and r.get('target',{}).get('name')=='studio-real-rebuild' and r.get('executable')}
        require(len(binaries)==1,'Cannot identify Rust executable');binary=Path(binaries.pop())
        report['source_sha256']={str(path.relative_to(ROOT)):file_hash(path) for path in [ROOT/'experiments/real-rebuild/src/main.rs',ROOT/'experiments/real-rebuild/src/policy.rs',ROOT/'experiments/real-rebuild/src/strict.rs',ROOT/'experiments/real-rebuild/Cargo.lock',vendor/'src/write/mod.rs',vendor/'src/write/studio_legacy_sort.rs',Path(__file__).resolve()]}
        rows=entries();queries=list(dict.fromkeys(r['key'] for r in rows))+['missing','aPpLe','a?b','DUPLICATE','edge?031','A\\B']
        observations={};specs={};paths={}
        for name,profile,encoding in [('literal-utf8','literal','utf8'),('literal-utf16','literal','utf16'),('legacy-mdict-utils','mdict-utils','utf8'),('legacy-mdxbuilder','mdxbuilder','utf8')]:
            spec={'entries':rows,'queries':queries,'profile':profile,'encoding':encoding,'title':'07-header-'+name}
            spec_path=out/f'{name}.json';spec_path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');specs[name]=spec_path
            observed=json.loads(run([binary,'policy-build',spec_path,out/name],out/f'{name}.log',args.timeout));path=out/name/'policy.mdx'
            paths[name]=path;observations[name]=observed
            (out/f'{name}-observations.json').write_text(json.dumps(observed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            if profile=='literal':report['checks'][name]=validate_literal(spec,observed,path)
            else:
                require(observed['resolved_strip'] is True,'Legacy diagnostic flag was not applied')
                expected_rows=ordered([(r['key'],r['text']) for r in rows],profile)
                require([(r['key'],r['text']) for r in observed['rows']]==expected_rows,'Legacy physical order/payload changed')
                require(audit(path)['status']=='structural_audit_passed','Legacy diagnostic wire audit failed')
                report['legacy_diagnostics'][name]=diagnostics(observed,True)
        for name,base,flag in [('alias-no','literal-utf8','No'),('alias-yes','legacy-mdict-utils','Yes')]:
            original=paths[base].read_bytes();changed=rewrite_header(original,[(f' StripKey="{flag}"',f' Stripkey="{flag}"')]);path=out/f'{name}.mdx';path.write_bytes(changed)
            require(sections(original)==sections(changed),'Alias edit changed key/record sections')
            observed=json.loads(run([binary,'policy-inspect',specs[base],path],out/f'{name}.log',args.timeout))
            equivalent=observed['lookups']==observations[base]['lookups'] and observed['rows']==observations[base]['rows'] and observed['resolved_strip']==(flag=='Yes')
            report['alias_checks'][name]={'status':'passed' if equivalent else 'failed','lookup_and_rows_equal':equivalent,'observations':observed}
        # A flag-only change on literal-ordered rows must be identified as a
        # mismatch, rather than being mistaken for a complete compatibility fix.
        original=paths['literal-utf8'].read_bytes();path=out/'flag-only-mismatch.mdx';path.write_bytes(rewrite_header(original,[(' StripKey="No"',' StripKey="Yes"')]))
        changed=json.loads(run([binary,'policy-inspect',specs['literal-utf8'],path],out/'flag-only-mismatch.log',args.timeout))
        mismatch=diagnostics(changed,True);require(not mismatch['ordering_monotonic_under_reference_lookup'],'Negative control did not detect flag/order mismatch')
        report['flag_only_negative_control']={'status':'passed_mismatch_detected','observation':mismatch}
        path=out/'conflicting-aliases.mdx';path.write_bytes(rewrite_header(original,[(' StripKey="No"',' StripKey="No" Stripkey="Yes"')]))
        process=subprocess.Popen([str(binary),'policy-inspect',str(specs['literal-utf8']),str(path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
        try:stdout,stderr=process.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:stop(process);process.communicate();raise RuntimeError('Conflicting aliases check timed out')
        (out/'conflicting-aliases.log').write_bytes(stdout+b'\nSTDERR:\n'+stderr)
        require(process.returncode==1 and b'Conflicting StripKey aliases' in stderr and not stdout.strip(),'Conflicting flags were not rejected before rows/lookup')
        report['conflicting_aliases']={'status':'passed_rejected_before_lookup'}
        require(all(c['status']=='passed' for c in report['alias_checks'].values()),'Header alias lookup differs; review alias logs, native candidates withheld')
        native=out/'native-candidates';native.mkdir()
        for name in ['literal-utf8','literal-utf16']:shutil.copyfile(paths[name],native/f'07-header-{name}.mdx')
        with (out/'native-checklist.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream);writer.writerow(['file','query','studio_exact_first_expected_tokens','MDict_actual','GoldenDict_actual'])
            for name in ['literal-utf8','literal-utf16']:
                for query in ['a-b','ab','a b','a.b','a!b','a\\b','a?b','aPpLe','apple','duplicate','edge-000','edge-047','字','مرحبا','𠀀','missing']:
                    matches=expected_lookup(observations[name]['rows'],query,False)
                    writer.writerow([f'07-header-{name}.mdx',query,' | '.join(r['text'] for r in matches) or 'NO ENTRY','',''])
        report['native_candidates']={p.name:file_hash(p) for p in native.iterdir()}
        report['status']='literal_header_lookup_offline_passed_legacy_diagnostics_recorded_native_pending'
    except Exception as error:report['status']='failed_header_lookup_qualification';report['error']=str(error)
    (out/'header-lookup-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {out/'header-lookup-report.json'}")
    return 0 if report['status']=='literal_header_lookup_offline_passed_legacy_diagnostics_recorded_native_pending' else 1


if __name__=='__main__':raise SystemExit(main())
