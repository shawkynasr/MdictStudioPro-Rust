"""Independent bounded physical-record decoder for the first real-reader gate.

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
import zlib
from v2_audit import block,exact
from bounded_fixtures import digest_row

def scan_to_database(path,kind,queries,db,scratch=None):
    db.execute('CREATE TABLE selected(n INTEGER PRIMARY KEY,k TEXT NOT NULL,data BLOB NOT NULL)')
    state=0xcbf29ce484222325;count=keys=payloads=0;resources={};query_set=set(queries);framed=hashlib.sha256()
    for ordinal,(key,data) in enumerate(wire_rows(path,kind,scratch)):
        if ordinal==0:query_set.add(key)
        state=digest_row(state,ordinal,key,data);count+=1;keys+=len(key.encode());payloads+=len(data)
        raw=key.encode();framed.update(struct.pack('<QQ',ordinal,len(raw))+raw+struct.pack('<Q',len(data))+hashlib.sha256(data).digest())
        require(keys+payloads<=2*1024*1024*1024,'Decoded application scan cap')
        if key in query_set:db.execute('INSERT INTO selected VALUES(?,?,?)',(ordinal,key,data))
        if kind=='mdd':
            relative=key.replace('\\','/').removeprefix('/');require(relative not in resources,'MDD duplicate destination');resources[relative]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        if count%10000==0:print(f'Independent scan: {count} records',flush=True)
    db.commit();return {'records':count,'key_bytes':keys,'payload_bytes':payloads,'framed_fnv64':f'{state:016x}'},sorted(query_set),resources,framed.hexdigest()
def page(db,query,offset,limit,kind):
    total=db.execute('SELECT count(*) FROM selected WHERE k=?',(query,)).fetchone()[0];rows=[]
    if limit and offset<total:
        for n,k,data in db.execute('SELECT n,k,data FROM selected WHERE k=? ORDER BY n LIMIT ? OFFSET ?',(query,limit,offset)):
            rows.append({'ordinal':n,'key':k,**({'text':data.decode('utf-8')} if kind=='mdx' else {'bytes':list(data)})})
    next_offset=min(offset,total)+len(rows)
    return {'basis':'exact' if total else 'none','total':total,'offset':offset,'next_offset':next_offset if limit and next_offset<total else None,'rows':rows}
def redact_page(value):
    result={k:v for k,v in value.items() if k!='rows'};result['rows']=[]
    for row in value['rows']:
        data=row['text'].encode() if 'text' in row else bytes(row['bytes']);result['rows'].append({'ordinal':row['ordinal'],'key':row['key'],'payload_bytes':len(data),'payload_sha256':hashlib.sha256(data).hexdigest()})
    return result

def require(value,message):
    if not value:raise AssertionError(message)
def attrs(path):
    with path.open('rb') as f:
        n=struct.unpack('>I',exact(f,4))[0];require(n<=65536,'Header cap');raw=exact(f,n).decode('utf-16le').rstrip('\0')
    return {k:html.unescape(v) for k,v in re.findall(r'(\w+)="(.*?)"',raw,re.S)}
def wire_rows(path,kind,scratch=None):
    with path.open('rb') as f,tempfile.TemporaryDirectory(dir=scratch) as tmp:
        db=sqlite3.connect(Path(tmp)/'rows.sqlite')
        try:
            db.execute('CREATE TABLE rows(n INTEGER PRIMARY KEY,k TEXT,o INTEGER)')
            n=struct.unpack('>I',exact(f,4))[0];require(n<=65536,'Header cap');raw=exact(f,n);require(struct.unpack('<I',exact(f,4))[0]==zlib.adler32(raw)&0xffffffff,'Header checksum');a=attrs(path);require(a.get('GeneratedByEngineVersion') in {'2','2.0'} and a.get('RequiredEngineVersion') in {'2','2.0'},'Only v2 supported by this oracle');require(a.get('Encrypted','No').lower() in {'no','0',''},'Encrypted dictionary outside oracle profile');encoding='utf-16le' if kind=='mdd' or a['Encoding'].upper() in {'UTF-16','UTF-16LE'} else 'utf-8';unit=2 if encoding=='utf-16le' else 1
            summary=exact(f,40);blocks,count,info_size,info_comp,key_comp=struct.unpack('>5Q',summary);require(struct.unpack('>I',exact(f,4))[0]==zlib.adler32(summary)&0xffffffff,'Key summary checksum');require(blocks<=8192 and count<=500000 and info_size<=16*1024*1024,'Key index cap');info=block(exact(f,info_comp),info_size);pos=0;descriptors=[]
            for _ in range(blocks):
                count_block=struct.unpack_from('>Q',info,pos)[0];pos+=8
                boundaries=[]
                for _ in range(2):
                    length=struct.unpack_from('>H',info,pos)[0];pos+=2;boundaries.append(info[pos:pos+length*unit].decode(encoding));pos+=(length+1)*unit
                packed,decoded=struct.unpack_from('>QQ',info,pos);pos+=16;require(decoded<=8*1024*1024,'Key block cap');descriptors.append((count_block,packed,decoded,boundaries))
            require(pos==len(info) and sum(p for _,p,_,_ in descriptors)==key_comp,'Key index extent');ordinal=0
            previous=0
            for num,packed,decoded,boundaries in descriptors:
                data=block(exact(f,packed),decoded);pos=0;first=None;last=None
                for _ in range(num):
                    offset=struct.unpack_from('>Q',data,pos)[0];pos+=8;end=pos
                    while end+unit<=len(data) and data[end:end+unit]!=b'\0'*unit:end+=unit
                    require(end+unit<=len(data),'Key terminator');key=data[pos:end].decode(encoding);pos=end+unit;require(key and '\0' not in key and len(key.encode())<=4096 and offset>=previous and (ordinal!=0 or offset==0),'Key/offset profile');previous=offset;first=key if first is None else first;last=key;db.execute('INSERT INTO rows VALUES(?,?,?)',(ordinal,key,offset));ordinal+=1
                require(pos==len(data) and [first,last]==boundaries,'Key block extent/boundary differs')
            require(ordinal==count,'Physical count');nb,nr,index_bytes,packed_total=struct.unpack('>4Q',exact(f,32));require(nr==count and index_bytes==16*nb and nb<=8192,'Record index');index=exact(f,index_bytes);desc=[struct.unpack_from('>QQ',index,i*16) for i in range(nb)];require(sum(p for p,_ in desc)==packed_total,'Packed total')
            with tempfile.TemporaryFile(dir=tmp) as spool:
                total=0
                for packed,decoded in desc:
                    require(decoded<=8*1024*1024,'Record block cap');data=block(exact(f,packed),decoded);spool.write(data);total+=len(data)
                require(not f.read(1),'Trailing bytes');require(total<=2*1024*1024*1024,'Decoded wire cap')
                for ordinal,key,start,end in db.execute('SELECT n,k,o,lead(o) OVER (ORDER BY n) FROM rows ORDER BY n'):
                    end=total if end is None else end;require(0<=start<=end<=total and end-start<=2*1024*1024,'Record extent');spool.seek(start);data=exact(spool,end-start)
                    if kind=='mdx':require(data.endswith(b'\0'*unit),'Missing body terminator');data=data[:-unit].decode(encoding).encode('utf-8')
                    yield key,data
        finally:db.close()
