"""Independent physical-record decoder and deterministic IO fixture recipes.

Stdlib wire decoding uses SQLite offsets and a disk payload spool. It does not
use the Rust reader, its exported text, or legacy stylesheet expansion.
"""
import hashlib
import html
import json
from pathlib import Path
import re
import sqlite3
import struct
import tempfile
from v2_audit import block,exact

def require(value,message):
    if not value:raise AssertionError(message)
def attrs(path):
    with path.open('rb') as f:
        n=struct.unpack('>I',exact(f,4))[0];require(n<=65536,'Header cap');raw=exact(f,n).decode('utf-16le').rstrip('\0')
    return {k:html.unescape(v) for k,v in re.findall(r'(\w+)="(.*?)"',raw,re.S)}
def wire_rows(path,kind):
    with path.open('rb') as f,tempfile.TemporaryDirectory() as tmp:
        db=sqlite3.connect(Path(tmp)/'rows.sqlite')
        try:
            db.execute('CREATE TABLE rows(n INTEGER PRIMARY KEY,k TEXT,o INTEGER)')
            n=struct.unpack('>I',exact(f,4))[0];require(n<=65536,'Header cap');exact(f,n+4);a=attrs(path);encoding='utf-16le' if kind=='mdd' or a['Encoding'].upper() in {'UTF-16','UTF-16LE'} else 'utf-8';unit=2 if encoding=='utf-16le' else 1
            summary=exact(f,40);blocks,count,info_size,info_comp,key_comp=struct.unpack('>5Q',summary);exact(f,4);require(blocks<=8192 and count<=100000 and info_size<=16*1024*1024,'Key index cap');info=block(exact(f,info_comp),info_size);pos=0;descriptors=[]
            for _ in range(blocks):
                count_block=struct.unpack_from('>Q',info,pos)[0];pos+=8
                for _ in range(2):
                    length=struct.unpack_from('>H',info,pos)[0];pos+=2+(length+1)*unit
                packed,decoded=struct.unpack_from('>QQ',info,pos);pos+=16;require(decoded<=8*1024*1024,'Key block cap');descriptors.append((count_block,packed,decoded))
            require(pos==len(info) and sum(p for _,p,_ in descriptors)==key_comp,'Key index extent');ordinal=0
            for num,packed,decoded in descriptors:
                data=block(exact(f,packed),decoded);pos=0
                for _ in range(num):
                    offset=struct.unpack_from('>Q',data,pos)[0];pos+=8;end=pos
                    while end+unit<=len(data) and data[end:end+unit]!=b'\0'*unit:end+=unit
                    require(end+unit<=len(data),'Key terminator');key=data[pos:end].decode(encoding);pos=end+unit;db.execute('INSERT INTO rows VALUES(?,?,?)',(ordinal,key,offset));ordinal+=1
                require(pos==len(data),'Key block trailing data')
            require(ordinal==count,'Physical count');nb,nr,index_bytes,packed_total=struct.unpack('>4Q',exact(f,32));require(nr==count and index_bytes==16*nb and nb<=8192,'Record index');index=exact(f,index_bytes);desc=[struct.unpack_from('>QQ',index,i*16) for i in range(nb)];require(sum(p for p,_ in desc)==packed_total,'Packed total')
            with tempfile.TemporaryFile() as spool:
                total=0
                for packed,decoded in desc:
                    require(decoded<=8*1024*1024,'Record block cap');data=block(exact(f,packed),decoded);spool.write(data);total+=len(data)
                require(not f.read(1),'Trailing bytes');require(total<=128*1024*1024,'Decoded wire cap')
                for ordinal,key,start,end in db.execute('SELECT n,k,o,lead(o) OVER (ORDER BY n) FROM rows ORDER BY n'):
                    end=total if end is None else end;require(0<=start<=end<=total and end-start<=4*1024*1024,'Record extent');spool.seek(start);data=exact(spool,end-start)
                    if kind=='mdx':require(data.endswith(b'\0'*unit),'Missing body terminator');data=data[:-unit].decode(encoding).encode('utf-8')
                    yield key,data
        finally:db.close()
def digest(rows):
    h=hashlib.sha256();count=keys=payloads=0
    for key,data in rows:
        key=key.encode('utf-8');h.update(struct.pack('<QQ',count,len(key)));h.update(key);h.update(struct.pack('<Q',len(data)));h.update(hashlib.sha256(data).digest());count+=1;keys+=len(key);payloads+=len(data)
    return {'records':count,'key_bytes':keys,'payload_bytes':payloads,'framed_records_sha256':h.hexdigest()}
SPECIAL=['Apple','apple','APPLE','apple','a-b','ab','a.b','a b','İ','i\u0307','ΣΟΣ','σος','字','مرحبا','𠀀',' spaced ']
def row(i,kind):
    key=SPECIAL[i] if i<len(SPECIAL) else f'row{i:08d}'
    if kind=='mdd':return key,bytes(range(256)) if i!=3 else b''
    text='' if i==3 else f'`1`字 مرحبا {i:08d}\n\n'+'x'*220+('\n' if i%2 else '')
    return key,text.encode('utf-8')
def ordered(count,kind):
    # Recipe scalars have stable lowercase mappings across the supported Python
    # versions. Rust still uses the full frozen Unicode16 table. Greek ΣΟΣ here
    # deliberately exercises context-sensitive final sigma.
    return sorted((row(i,kind) for i in range(count)),key=lambda r:r[0].lower())
def json_line(key,data):return json.dumps({'key':key,'text':data.decode('utf-8')},ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n'
def compare_export(path,rows,txt=False):
    h=hashlib.sha256();expected=0
    with path.open('rb') as f:
        for key,data in rows:
            b=key.encode('utf-8')+b'\n'+data+b'\n</>\n' if txt else json_line(key,data)
            require(f.read(len(b))==b,'Export bytes differ from independent recipe');h.update(b);expected+=len(b)
        require(not f.read(1),'Unexpected trailing exported bytes')
    return {'bytes':expected,'sha256':h.hexdigest()}
