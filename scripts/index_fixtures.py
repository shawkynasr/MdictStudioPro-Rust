"""Independent Python wire fixtures, page oracle and cache-corruption probes."""
import hashlib
import json
import string
import struct
from unittest.mock import patch
import bounded_fixtures as wire
from v2_import_fixtures import rewrite

SPECIAL=[('Apple','upper'),('apple','first'),('apple','second'),('a-b','hyphen'),('ab','plain'),('a.b','dot'),('a b','space'),('ΣΟΣ','Greek'),('İ','dotted'),('字','Chinese'),('مرحبا','Arabic'),('𠀀','supplementary'),('\U00010d50','Unicode16'),(' spaced ','spaces'),('!!!','punctuation'),('alias','@@@LINK=apple')]
def make(path,encoding='utf8',strip=False,sensitive=False,duplicates=400):
    rows=SPECIAL+ [('duplicate',f'body-{i}') for i in range(duplicates)]
    with patch.object(wire,'rows',lambda *args:iter(rows)):
        fixture=wire.write(path,len(rows),'mdx',encoding,target=128)
    path.write_bytes(rewrite(path.read_bytes(),{'StripKey':'Yes' if strip else 'No','KeyCaseSensitive':'Yes' if sensitive else 'No'}))
    fixture.update(rows=rows,strip=strip,sensitive=sensitive)
    return fixture
def select(rows,query,policy='header_ascii_v1',sensitive=False,strip=False):
    def norm(s):
        s=s if sensitive else s.lower()
        return ''.join(c for c in s if c not in string.punctuation+'\t\n\v\f\r ') if strip else s
    exact=[i for i,(k,v) in enumerate(rows) if k==query]
    if exact:return 'exact',exact
    if policy=='raw_exact':return 'none',[]
    token=norm(query)
    if not token:raise ValueError('empty_normalized_query')
    found=[i for i,(k,v) in enumerate(rows) if norm(k)==token]
    return ('normalized' if found else 'none'),found
def expected_page(rows,query,offset,limit,policy='header_ascii_v1',sensitive=False,strip=False,kind='mdx'):
    basis,selected=select(rows,query,policy,sensitive,strip);page=selected[offset:offset+limit];next_offset=min(offset,len(selected))+len(page)
    return {'basis':basis,'total':len(selected),'offset':offset,'next_offset':next_offset if limit>0 and next_offset<len(selected) else None,'rows':[{'ordinal':i,'key':rows[i][0],**({'text':rows[i][1]} if kind=='mdx' else {'bytes':list(rows[i][1])})} for i in page]}
def corrupt(base,path,mode):
    b=bytearray(base.read_bytes())
    if mode=='checksum':b[-1]^=1
    elif mode=='truncated':del b[-13:]
    else:
        size=struct.unpack_from('<I',b,8)[0];manifest=json.loads(b[12:12+size]);count=manifest['records']
        if mode=='revision':manifest['revision']='wrong-revision';encoded=json.dumps(manifest,separators=(',',':')).encode();b[8:4096]=struct.pack('<I',len(encoded))+encoded+b'\0'*(4084-len(encoded))
        elif mode=='ordinal':struct.pack_into('<I',b,4096+12,count)
        elif mode=='token':
            offset,length=struct.unpack_from('<QI',b,4096)
            if length:b[offset]=ord('z') if b[offset]!=ord('z') else ord('y')
        elif mode=='extent':struct.pack_into('<Q',b,4096,2**63)
        elif mode=='duplicate-ordinal':b[4096+16+12:4096+32]=b[4096+12:4096+16]
        else:raise ValueError(mode)
        b[-32:]=hashlib.sha256(b[:-32]).digest()
    path.write_bytes(b)
    return path
