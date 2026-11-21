"""Independent stdlib streaming v2 fixtures; no engine writer/big row list."""
import hashlib
import html
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

def block(data):return struct.pack('<I',2)+struct.pack('>I',zlib.adler32(data)&0xffffffff)+zlib.compress(data)
def frame_hash(state,data):
    for b in data:state=((state^b)*0x100000001b3)&0xffffffffffffffff
    return state
def digest_row(state,ordinal,key,payload):
    key=key.encode('utf-8')
    for data in [struct.pack('<Q',ordinal),struct.pack('<Q',len(key)),key,struct.pack('<Q',len(payload)),payload]:state=frame_hash(state,data)
    return state
def rows(count,kind='mdx',payload_size=256):
    for i in range(count):
        key=('row00000000' if i<2 else f'row{i:08d}')
        if count>=8 and i>=count-3:key=['مرحبا','字','𠀀'][i-(count-3)]
        if kind=='mdx':
            prefix=f'<p>{i:08d} 字 العربية {hashlib.sha256(str(i).encode()).hexdigest()} '
            body=prefix+'x'*max(0,payload_size-len(prefix.encode('utf-8'))-4)+'</p>'
            yield key,body
        else:yield key,b'' if i==count-1 else bytes((i+j)%256 for j in range(payload_size))
def write(path,count,kind='mdx',encoding='utf8',payload_size=256,target=65536,compression=True):
    codec='utf-16le' if kind=='mdd' or encoding=='utf16' else 'utf-8';unit=2 if codec=='utf-16le' else 1
    pack_block=block if compression else lambda data:b'\0'*4+struct.pack('>I',zlib.adler32(data)&0xffffffff)+data
    info=[];record_info=[];key_buffer=bytearray();record_buffer=bytearray();keys=[];offset=0;state=0xcbf29ce484222325;key_bytes=0;payload_bytes=0;query_rows={q:[] for q in ['row00000000','ROW00000000','absent','字','𠀀']}
    with tempfile.TemporaryDirectory() as tmp:
        key_path=Path(tmp)/'keys';record_path=Path(tmp)/'records'
        with key_path.open('wb') as key_data,record_path.open('wb') as records:
            def flush_keys():
                if not keys:return
                packed=pack_block(key_buffer);key_data.write(packed);descriptor=struct.pack('>Q',len(keys))
                for key in [keys[0],keys[-1]]:
                    raw=key.encode(codec);descriptor+=struct.pack('>H',len(raw)//unit)+raw+b'\0'*unit
                info.append(descriptor+struct.pack('>QQ',len(packed),len(key_buffer)));key_buffer.clear();keys.clear()
            def flush_records():
                if not record_buffer:return
                packed=pack_block(record_buffer);records.write(packed);record_info.append((len(packed),len(record_buffer)));record_buffer.clear()
            for ordinal,(key,payload) in enumerate(rows(count,kind,payload_size)):
                raw_payload=payload.encode('utf-8') if kind=='mdx' else payload
                state=digest_row(state,ordinal,key,raw_payload);key_bytes+=len(key.encode('utf-8'));payload_bytes+=len(raw_payload)
                if key in query_rows:query_rows[key].append({'ordinal':ordinal,'key':key,**({'text':payload} if kind=='mdx' else {'bytes':list(payload)})})
                encoded=payload.encode(codec)+b'\0'*unit if kind=='mdx' else payload
                entry=struct.pack('>Q',offset)+key.encode(codec)+b'\0'*unit
                if key_buffer and len(key_buffer)+len(entry)>target:flush_keys()
                if record_buffer and len(record_buffer)+len(encoded)>target:flush_records()
                key_buffer.extend(entry);keys.append(key);record_buffer.extend(encoded);offset+=len(encoded)
            flush_keys();flush_records()
        root='Dictionary' if kind=='mdx' else 'Library_Data';label=('UTF-16' if encoding=='utf16' else 'UTF-8') if kind=='mdx' else ''
        xml=f'<{root} GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" Encrypted="No" Encoding="{label}" Format="{"Html" if kind=="mdx" else ""}" KeyCaseSensitive="No" StripKey="No" Title="Bounded fixture" Description="Independent streaming fixture" StyleSheet="" Compact="No"/>\r\n\0'
        raw=xml.encode('utf-16le');info_bytes=b''.join(info);packed_info=block(info_bytes)
        summary=struct.pack('>5Q',len(info),count,len(info_bytes),len(packed_info),key_path.stat().st_size)
        with path.open('xb') as out:
            out.write(struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff));out.write(summary+struct.pack('>I',zlib.adler32(summary)&0xffffffff)+packed_info)
            with key_path.open('rb') as stream:shutil.copyfileobj(stream,out,65536)
            out.write(struct.pack('>4Q',len(record_info),count,len(record_info)*16,record_path.stat().st_size))
            for packed,unpacked in record_info:out.write(struct.pack('>QQ',packed,unpacked))
            with record_path.open('rb') as stream:shutil.copyfileobj(stream,out,65536)
    return {'path':path,'kind':kind,'scan':{'records':count,'key_bytes':key_bytes,'payload_bytes':payload_bytes,'framed_fnv64':f'{state:016x}'},'queries':query_rows,'key_blocks':len(info),'record_blocks':len(record_info)}
def mutate(base,destination,mode):
    data=bytearray(base.read_bytes());n=struct.unpack_from('>I',data)[0];start=n+8
    if mode=='header_length':struct.pack_into('>I',data,0,1<<30)
    elif mode in {'key_info_packed','key_info_decoded'}:
        struct.pack_into('>Q',data,start+(24 if mode=='key_info_packed' else 16),1<<40);struct.pack_into('>I',data,start+40,zlib.adler32(data[start:start+40])&0xffffffff)
    else:
        blocks,count,raw_info,packed_info,key_bytes=struct.unpack_from('>5Q',data,start);key_start=start+44+packed_info;record_start=key_start+key_bytes
        if mode=='record_declared_decoded':struct.pack_into('>Q',data,record_start+32+8,1<<40)
        elif mode=='key_block_checksum':data[key_start+4]^=1
        elif mode=='record_block_checksum':
            info_size=struct.unpack_from('>Q',data,record_start+16)[0];data[record_start+32+info_size+4]^=1
        elif mode=='key_block_entries':
            if blocks!=1:raise AssertionError('Entry-count mutation requires one key block')
            info=bytearray(zlib.decompress(data[start+44+8:start+44+packed_info]));struct.pack_into('>Q',info,0,1<<40);new_info=block(info)
            summary=struct.pack('>5Q',blocks,1<<40,raw_info,len(new_info),key_bytes);tail=bytearray(data[key_start:]);struct.pack_into('>Q',tail,key_bytes+8,1<<40)
            data=data[:start]+summary+struct.pack('>I',zlib.adler32(summary)&0xffffffff)+new_info+tail
        elif mode=='truncated':data=data[:-13]
        else:raise ValueError(mode)
    destination.write_bytes(data);return destination
