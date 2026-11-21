"""Independent streaming v2 MDD writer: resource boundaries need not align blocks."""
import hashlib
from pathlib import Path
import shutil
import struct
import tempfile
import zlib

def chunks(size,seed):
    pattern=bytes((seed+i)%256 for i in range(256));offset=0
    while offset<size:
        n=min(65536,size-offset);start=offset%256;p=pattern[start:]+pattern[:start];yield (p*((n+255)//256))[:n];offset+=n
def block(data,compressed=True):return struct.pack('<I',2 if compressed else 0)+struct.pack('>I',zlib.adler32(data)&0xffffffff)+(zlib.compress(data) if compressed else data)
def write(path,recipes,compressed=True,target=65536):
    recipes=list(recipes);info=[];record_info=[];key_buffer=bytearray();record_buffer=bytearray();names=[];offset=0;expected=[];framed=hashlib.sha256()
    with tempfile.TemporaryDirectory() as tmp:
        kp=Path(tmp)/'keys';rp=Path(tmp)/'records'
        with kp.open('wb') as keyout,rp.open('wb') as recordout:
            def flush_keys():
                if not names:return
                packed=block(key_buffer,compressed);keyout.write(packed);descriptor=struct.pack('>Q',len(names))
                for key in [names[0],names[-1]]:
                    b=key.encode('utf-16le');descriptor+=struct.pack('>H',len(b)//2)+b+b'\0\0'
                info.append(descriptor+struct.pack('>QQ',len(packed),len(key_buffer)));key_buffer.clear();names.clear()
            def flush_records():
                if not record_buffer:return
                packed=block(record_buffer,compressed);recordout.write(packed);record_info.append((len(packed),len(record_buffer)));record_buffer.clear()
            for ordinal,recipe in enumerate(recipes):
                key,size,seed=recipe['key'],recipe['bytes'],recipe.get('seed',0);entry=struct.pack('>Q',offset)+key.encode('utf-16le')+b'\0\0'
                if key_buffer and len(key_buffer)+len(entry)>target:flush_keys()
                key_buffer.extend(entry);names.append(key);h=hashlib.sha256()
                for data in chunks(size,seed):
                    h.update(data);pos=0
                    while pos<len(data):
                        n=min(target-len(record_buffer),len(data)-pos);record_buffer.extend(data[pos:pos+n]);pos+=n
                        if len(record_buffer)==target:flush_records()
                digest=h.digest();raw=key.encode();framed.update(struct.pack('<QQ',ordinal,len(raw))+raw+struct.pack('<Q',size)+digest)
                relative=key.replace('\\','/').removeprefix('/');expected.append({'ordinal':ordinal,'key':key,'relative':relative,'bytes':size,'sha256':digest.hex()});offset+=size
            flush_keys();flush_records()
        xml='<Library_Data GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" Encrypted="No" Encoding="" Format="" KeyCaseSensitive="No" StripKey="No" Title="Streaming resources" Description="Independent span fixtures" StyleSheet="" Compact="No"/>\r\n\0';header=xml.encode('utf-16le');infodata=b''.join(info);packedinfo=block(infodata);summary=struct.pack('>5Q',len(info),len(recipes),len(infodata),len(packedinfo),kp.stat().st_size)
        with path.open('xb') as out:
            out.write(struct.pack('>I',len(header))+header+struct.pack('<I',zlib.adler32(header)&0xffffffff));out.write(summary+struct.pack('>I',zlib.adler32(summary)&0xffffffff)+packedinfo)
            with kp.open('rb') as src:shutil.copyfileobj(src,out,65536)
            out.write(struct.pack('>4Q',len(record_info),len(recipes),16*len(record_info),rp.stat().st_size))
            for packed,decoded in record_info:out.write(struct.pack('>QQ',packed,decoded))
            with rp.open('rb') as src:shutil.copyfileobj(src,out,65536)
    return {'path':path,'expected':expected,'resources':len(recipes),'payload_bytes':offset,'largest_resource_bytes':max((r['bytes'] for r in recipes),default=0),'framed_resources_sha256':framed.hexdigest(),'record_blocks':len(record_info),'key_blocks':len(info)}
