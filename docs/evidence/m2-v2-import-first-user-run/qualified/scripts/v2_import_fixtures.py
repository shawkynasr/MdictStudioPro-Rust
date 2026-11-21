"""Independent legacy-writer fixtures and explicit lookup/redirect oracle."""
import json
from pathlib import Path
import string
import struct
import xml.etree.ElementTree as ET
import zlib
from patched_interop import ROOT,custom_writer_class,read_python
from metadata_codecs import source_records

ROWS=[{'key':k,'text':v} for k,v in [('Apple','upper'),('apple','first'),('apple','second'),('a-b','hyphen'),('ab','plain'),('a.b','dot'),('a b','space'),('字','文字'),('𠀀','supplementary'),('مرحبا','أهلاً'),('İ','dotted I'),('ΣΟΣ','Greek'),(' spaced ','literal spaces'),('alias','@@@LINK=apple'),('alias-case','@@@LINK=aPpLe'),('chain','@@@LINK=alias'),('missing-alias','@@@LINK=absent'),('cycle-a','@@@LINK=cycle-b'),('cycle-b','@@@LINK=cycle-a'),('newline-alias','@@@LINK=apple\r\n'),('bad-alias','@@@LINK='),('multiline-alias','@@@LINK=apple\nextra'),('branch','terminal branch'),('branch','@@@LINK=cycle-a'),('space-alias','@@@LINK= spaced '),('style','`1`raw marker'),('script','<script>example content only</script>')]]
QUERIES=['apple','Apple','aPpLe','a?b','ab','A B','İ','i\u0307','ΣΟΣ','σος','مرحبا','字','𠀀','absent','alias','style','script',' spaced ','!!!']
REDIRECTS=['alias','alias-case','chain','missing-alias','cycle-a','newline-alias','bad-alias','multiline-alias','branch','space-alias','absent']
def rewrite(data,updates=None,remove=(),aliases=None,raw_edit=None):
    n=struct.unpack_from('>I',data)[0];raw=data[4:4+n]
    if zlib.adler32(raw)&0xffffffff!=struct.unpack_from('<I',data,4+n)[0]:raise AssertionError('Bad fixture input header checksum')
    xml=raw.decode('utf-16le').removesuffix('\0');root=ET.fromstring(xml)
    known=['GeneratedByEngineVersion','RequiredEngineVersion','Encrypted','Encoding','Format','KeyCaseSensitive','StripKey','StyleSheet','Title','Description']
    for name in list(root.attrib):
        canonical=next((k for k in known if k.lower()==name.lower()),name)
        if canonical!=name:root.set(canonical,root.attrib.pop(name))
    for name in remove:root.attrib.pop(name,None)
    for name,value in (updates or {}).items():root.set(name,value)
    for before,after in (aliases or {}).items():root.set(after,root.attrib.pop(before))
    xml=ET.tostring(root,encoding='unicode',short_empty_elements=True)
    if raw_edit:xml=raw_edit(xml)
    raw=(xml+'\r\n\0').encode('utf-16le')
    return struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff)+data[n+8:]
def normalize(key,case_sensitive,strip):
    key=key if case_sensitive else key.lower()
    return ''.join(c for c in key if c not in string.punctuation+string.whitespace) if strip else key
def select(rows,query,policy,case_sensitive=False,strip=False):
    exact=[i for i,row in enumerate(rows) if row['key']==query]
    if exact or policy=='raw_exact':return exact
    value=normalize(query,case_sensitive,strip)
    if not value:raise ValueError('empty_normalized_query')
    return [i for i,row in enumerate(rows) if normalize(row['key'],case_sensitive,strip)==value]
def lookup(rows,query,policy,case_sensitive=False,strip=False,max_results=256):
    ordinals=select(rows,query,policy,case_sensitive,strip)
    if len(ordinals)>max_results:raise ValueError('limit_exceeded')
    return [rows[i] for i in ordinals]
def resolve(rows,query,policy,case_sensitive=False,strip=False,max_hops=16,max_results=256):
    result=[];visits=0
    def walk(origin,ordinal,chain):
        nonlocal visits
        visits+=1
        if visits>4096:raise ValueError('limit_exceeded')
        if any(h['ordinal']==ordinal for h in chain):raise ValueError('redirect_cycle')
        row=rows[ordinal]
        if row['text'].startswith('@@@LINK='):
            target=row['text'][8:]
            if target.endswith('\r\n'):target=target[:-2]
            elif target.endswith('\n'):target=target[:-1]
            if not target or any(c in target for c in '\r\n\0'):raise ValueError('redirect_target')
            if len(chain)>=max_hops:raise ValueError('redirect_depth')
            selected=select(rows,target,policy,case_sensitive,strip)
            if not selected:raise ValueError('redirect_missing')
            hop={'ordinal':ordinal,'key':row['key'],'target':target}
            for next_ordinal in selected:walk(origin,next_ordinal,chain+[hop])
        else:
            if len(result)>=max_results:raise ValueError('limit_exceeded')
            result.append({'source_ordinal':origin,'terminal_ordinal':ordinal,'entry':row,'chain':chain})
    for ordinal in select(rows,query,policy,case_sensitive,strip):walk(ordinal,ordinal,[])
    return result
def generate(directory):
    directory.mkdir(parents=True,exist_ok=False);writer=custom_writer_class();cases=[]
    for name,codec,api in [('utf8','utf-8','utf-8'),('utf16','utf-16le','utf16')]:
        records=source_records({'python':codec,'entries':ROWS},directory/(name+'-records'));base=directory/(name+'-base.mdx')
        engine=writer(records,title='Foreign v2 import',description='Legacy writer fixture',encoding=api,is_mdd=False,sort_style='mdxbuilder',key_size=64,record_size=64)
        with base.open('wb') as stream:engine.write(stream)
        for case_sensitive in [False,True]:
            for strip in [False,True]:
                label=f'{name}-case{int(case_sensitive)}-strip{int(strip)}';path=directory/(label+'.mdx')
                path.write_bytes(rewrite(base.read_bytes(),{'KeyCaseSensitive':'Yes' if case_sensitive else 'No','StripKey':'Yes' if strip else 'No','StyleSheet':'1\n<b>\n</b>\n','Description':'Line one\nLine two & <tags> "quoted"'},aliases={'StripKey':'Stripkey'} if strip else None))
                # Reopen independently after header mutation; expected rows are
                # physical records, not a second copy of the Rust implementation.
                rows=[{'key':k,'text':v} for k,v in read_python(path,'mdx')]
                if sorted((r['key'],r['text']) for r in rows)!=sorted((r['key'],r['text']) for r in ROWS):raise AssertionError('Legacy writer changed fixture payloads')
                cases.append({'name':label,'kind':'mdx','path':path,'policy':'header_ascii_v1','case_sensitive':case_sensitive,'strip':strip,'rows':rows})
        base_case=cases[-4]
        cases.append({**base_case,'name':name+'-raw','policy':'raw_exact'})
        missing=directory/(name+'-missing-flags.mdx');missing.write_bytes(rewrite(base_case['path'].read_bytes(),remove=('StripKey','KeyCaseSensitive')))
        cases.append({**base_case,'name':name+'-missing-raw','path':missing,'policy':'raw_exact','missing_flags':True})
        cases.append({**base_case,'name':name+'-missing-header-policy','path':missing,'refusal':'unsupported_policy'})
    source=cases[0]['path'];base=source.read_bytes()
    for name,update,code in [('v1',{'GeneratedByEngineVersion':'1.2','RequiredEngineVersion':'1.2'},'unsupported_policy'),('v3',{'GeneratedByEngineVersion':'3.0','RequiredEngineVersion':'3.0'},'unsupported_policy'),('encrypted',{'Encrypted':'2'},'unsupported_policy'),('legacy-encoding',{'Encoding':'ISO8859-1'},'unsupported_policy')]:
        path=directory/(name+'.mdx');path.write_bytes(rewrite(base,update));cases.append({'name':name,'kind':'mdx','path':path,'policy':'raw_exact','refusal':code})
    checksum=directory/'bad-checksum.mdx';data=bytearray(base);n=struct.unpack_from('>I',data)[0];data[4+n]^=1;checksum.write_bytes(data);cases.append({'name':'bad-checksum','kind':'mdx','path':checksum,'policy':'raw_exact','refusal':'integrity'})
    # Corrupt only the declared block ADLER32, preserving compressed payloads
    # and all section lengths. Full import must verify unqueried blocks too.
    for name,kind in [('bad-key-checksum','key'),('bad-record-checksum','record')]:
        data=bytearray(base);n=struct.unpack_from('>I',data)[0];start=n+8;_,_,_,info_bytes,key_bytes=struct.unpack_from('>5Q',data,start)
        keys=start+44+info_bytes;records_header=keys+key_bytes;_,_,record_info,_=struct.unpack_from('>4Q',data,records_header)
        block=keys if kind=='key' else records_header+32+record_info;data[block+4]^=1;path=directory/(name+'.mdx');path.write_bytes(data)
        cases.append({'name':name,'kind':'mdx','path':path,'policy':'raw_exact','refusal':'integrity'})
    conflict=directory/'conflicting-alias.mdx';conflict.write_bytes(rewrite(base,raw_edit=lambda s:s.replace('StripKey="No"','StripKey="No" Stripkey="Yes"',1)));cases.append({'name':'conflicting-alias','kind':'mdx','path':conflict,'policy':'raw_exact','refusal':'invalid_input'})
    payloads=[('\\data\\dup.bin',bytes([0,255,128])),('\\data\\dup.bin',bytes(range(256))),('empty.bin',b''),('../raw.bin',b'raw key only; no extraction')]
    data=[]
    for i,(key,value) in enumerate(payloads):
        path=directory/f'resource-{i}.bin';path.write_bytes(value);data.append({'key':key,'path':str(path),'size':len(value),'pos':0})
    mdd=directory/'foreign.mdd';engine=writer(data,title='Foreign resources',description='Raw resource identity',encoding='utf-8',is_mdd=True,sort_style='mdxbuilder',key_size=64,record_size=64)
    with mdd.open('wb') as stream:engine.write(stream)
    resources=[{'key':k,'bytes':list(v)} for k,v in read_python(mdd,'mdd')]
    if sorted((r['key'],bytes(r['bytes'])) for r in resources)!=sorted(payloads):raise AssertionError('Legacy writer changed resource payloads')
    cases.append({'name':'mdd-duplicates','kind':'mdd','path':mdd,'resources':resources})
    cases.append({**cases[0],'name':'result-budget','policy':'raw_exact','max_results':1})
    cases.append({**cases[0],'name':'redirect-depth','policy':'raw_exact','max_hops':0})
    cases.append({**cases[0],'name':'entry-budget','policy':'raw_exact','max_entries':1,'refusal':'limit_exceeded'})
    return cases
