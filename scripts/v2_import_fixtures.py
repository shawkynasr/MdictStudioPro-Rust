"""Independent legacy-writer fixtures and explicit lookup/redirect oracle."""
import json
from pathlib import Path
import string
import struct
import xml.etree.ElementTree as ET
import zlib
from patched_interop import ROOT,custom_writer_class,read_python
from metadata_codecs import source_records
from v2_audit import block,exact

ROWS=[{'key':k,'text':v} for k,v in [('Apple','upper'),('apple','first'),('apple','second'),('a-b','hyphen'),('ab','plain'),('a.b','dot'),('a b','space'),('字','文字'),('𠀀','supplementary'),('مرحبا','أهلاً'),('İ','dotted I'),('ΣΟΣ','Greek'),(' spaced ','literal spaces'),('alias','@@@LINK=apple'),('alias-case','@@@LINK=aPpLe'),('chain','@@@LINK=alias'),('missing-alias','@@@LINK=absent'),('cycle-a','@@@LINK=cycle-b'),('cycle-b','@@@LINK=cycle-a'),('newline-alias','@@@LINK=apple\r\n'),('bad-alias','@@@LINK='),('multiline-alias','@@@LINK=apple\nextra'),('branch','terminal branch'),('branch','@@@LINK=cycle-a'),('space-alias','@@@LINK= spaced '),('style','`1`raw marker'),('script','<script>example content only</script>')]]
QUERIES=['apple','Apple','aPpLe','a?b','ab','A B','İ','i\u0307','ΣΟΣ','σος','مرحبا','字','𠀀','absent','alias','style','script',' spaced ','!!!']
REDIRECTS=['alias','alias-case','chain','missing-alias','cycle-a','newline-alias','bad-alias','multiline-alias','branch','space-alias','absent']
def raw_wire_keys(path,kind,with_resources=False):
    """Decode fixture key blocks without the legacy reader's bytes.strip().

    Independent stdlib wire decoding; no Rust lookup or writer offset table.
    Full record framing/checksums remain covered by the existing wire audit.
    """
    with path.open('rb') as stream:
        n=struct.unpack('>I',exact(stream,4))[0]
        if n>65536:raise AssertionError('Fixture header too large')
        raw=exact(stream,n);checksum=struct.unpack('<I',exact(stream,4))[0]
        if zlib.adler32(raw)&0xffffffff!=checksum:raise AssertionError('Fixture header checksum')
        attrs=ET.fromstring(raw.decode('utf-16le').removesuffix('\0')).attrib
        encoding='utf-16le' if kind=='mdd' or attrs.get('Encoding','').upper() in {'UTF-16','UTF-16LE'} else 'utf-8'
        unit=2 if encoding=='utf-16le' else 1
        summary=exact(stream,40);blocks,count,info_size,info_comp,key_comp=struct.unpack('>5Q',summary)
        if blocks>1024 or count>1000 or info_size>1048576 or info_comp>1048576 or key_comp>1048576:raise AssertionError('Fixture key budget')
        if zlib.adler32(summary)&0xffffffff!=struct.unpack('>I',exact(stream,4))[0]:raise AssertionError('Fixture key-section checksum')
        info=block(exact(stream,info_comp),info_size);pos=0;descriptors=[]
        for _ in range(blocks):
            entries=struct.unpack_from('>Q',info,pos)[0];pos+=8;boundaries=[]
            for _ in range(2):
                length=struct.unpack_from('>H',info,pos)[0];pos+=2
                boundaries.append(info[pos:pos+length*unit].decode(encoding,'strict'));pos+=(length+1)*unit
            packed,unpacked=struct.unpack_from('>QQ',info,pos);pos+=16
            if unpacked>1048576:raise AssertionError('Fixture key block budget')
            descriptors.append((entries,packed,unpacked,boundaries))
        if pos!=len(info) or sum(d[1] for d in descriptors)!=key_comp:raise AssertionError('Fixture key summary sizes')
        keys=[];offsets=[];previous=0
        for entries,packed,unpacked,boundaries in descriptors:
            data=block(exact(stream,packed),unpacked);pos=0;names=[]
            if entries>count:raise AssertionError('Fixture key block count')
            for _ in range(entries):
                offset=struct.unpack_from('>Q',data,pos)[0];pos+=8;end=pos
                while end+unit<=len(data) and data[end:end+unit]!=b'\0'*unit:end+=unit
                if end+unit>len(data) or offset<previous:raise AssertionError('Fixture key terminator/offset')
                previous=offset;offsets.append(offset);key=data[pos:end].decode(encoding,'strict');pos=end+unit;names.append(key)
            if pos!=len(data) or not names or [names[0],names[-1]]!=boundaries:raise AssertionError('Fixture key boundaries')
            keys.extend(names)
        if len(keys)!=count:raise AssertionError('Fixture physical key count')
        if with_resources:
            if kind!='mdd':raise AssertionError('Binary resource oracle requires MDD')
            blocks,entries,info_size,packed_size=struct.unpack('>4Q',exact(stream,32))
            if blocks>1024 or entries!=count or info_size!=16*blocks or packed_size>1048576:raise AssertionError('Fixture resource summary')
            info=exact(stream,info_size);descriptors=[struct.unpack_from('>QQ',info,i*16) for i in range(blocks)]
            if sum(p for p,u in descriptors)!=packed_size or sum(u for p,u in descriptors)>1048576:raise AssertionError('Fixture resource budget')
            data=b''.join(block(exact(stream,p),u) for p,u in descriptors)
            if stream.read(1) or previous>len(data) or (offsets and offsets[0]!=0):raise AssertionError('Fixture resource extent')
            payloads=[data[start:end] for start,end in zip(offsets,offsets[1:]+[len(data)])]
            return keys,payloads
        return keys

def read_legacy_physical(path,kind):
    if kind=='mdd':
        keys,payloads=raw_wire_keys(path,kind,with_resources=True);rows=read_python(path,kind)
        expected=[(key.encode('utf-8').strip().decode('utf-8'),payload) for key,payload in zip(keys,payloads)]
        # The legacy record loop may stop at EOF before yielding zero-length
        # trailing records. Their offsets and empty bytes are independently
        # proven above. Every nonempty resource must still agree with Python.
        if rows!=expected[:len(rows)] or any(payload for key,payload in expected[len(rows):]):
            raise AssertionError(f'Python/raw-wire resource mismatch: {rows!r} != {expected!r}')
        return list(zip(keys,payloads))
    keys=raw_wire_keys(path,kind);rows=read_python(path,kind)
    if len(keys)!=len(rows):raise AssertionError(f'Python/raw-wire record count mismatch: {len(rows)} != {len(keys)}')
    result=[]
    for ordinal,(raw_key,(legacy_key,payload)) in enumerate(zip(keys,rows)):
        # readmdict._split_key_block strips ASCII whitespace from UTF-8 bytes.
        # Check that projection explicitly; preserve the actual wire key in the
        # Rust oracle. Never strip a definition or normalize a redirect target.
        expected=raw_key.encode('utf-8').strip().decode('utf-8')
        if legacy_key!=expected:raise AssertionError(f'Python key projection mismatch at {ordinal}: {legacy_key!r} != {expected!r}; wire={raw_key!r}')
        result.append((raw_key,payload))
    return result

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
        # Read the unmodified writer output independently. Header mutations
        # below retain every byte of the binary key/record sections. The old
        # Python reader cannot parse ET's numeric LF references in StyleSheet;
        # keep that metadata case for Rust without using it as a Python input.
        rows=[{'key':k,'text':v} for k,v in read_legacy_physical(base,'mdx')]
        if sorted((r['key'],r['text']) for r in rows)!=sorted((r['key'],r['text']) for r in ROWS):
            from collections import Counter
            actual=Counter((r['key'],r['text']) for r in rows);expected=Counter((r['key'],r['text']) for r in ROWS)
            raise AssertionError(f'Legacy writer changed fixture payloads: missing={list((expected-actual).elements())!r}; extra={list((actual-expected).elements())!r}')
        for case_sensitive in [False,True]:
            for strip in [False,True]:
                label=f'{name}-case{int(case_sensitive)}-strip{int(strip)}';path=directory/(label+'.mdx')
                path.write_bytes(rewrite(base.read_bytes(),{'KeyCaseSensitive':'Yes' if case_sensitive else 'No','StripKey':'Yes' if strip else 'No','StyleSheet':'1\n<b>\n</b>\n','Description':'Line one\nLine two & <tags> "quoted"'},aliases={'StripKey':'Stripkey'} if strip else None))
                original=base.read_bytes();changed=path.read_bytes()
                original_n=struct.unpack_from('>I',original)[0];changed_n=struct.unpack_from('>I',changed)[0]
                if original[original_n+8:]!=changed[changed_n+8:]:raise AssertionError('Header mutation changed binary sections')
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
    resources=[{'key':k,'bytes':list(v)} for k,v in read_legacy_physical(mdd,'mdd')]
    if sorted((r['key'],bytes(r['bytes'])) for r in resources)!=sorted(payloads):raise AssertionError('Legacy writer changed resource payloads')
    cases.append({'name':'mdd-duplicates','kind':'mdd','path':mdd,'resources':resources})
    cases.append({**cases[0],'name':'result-budget','policy':'raw_exact','max_results':1})
    cases.append({**cases[0],'name':'redirect-depth','policy':'raw_exact','max_hops':0})
    cases.append({**cases[0],'name':'entry-budget','policy':'raw_exact','max_entries':1,'refusal':'limit_exceeded'})
    return cases
