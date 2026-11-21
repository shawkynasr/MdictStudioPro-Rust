"""Independent bounded v1.2 ASCII/LZO oracle and synthetic wire fixtures.

Application decoding uses the pinned native engine. This test oracle supports
only canonical unencrypted v1.2 ISO8859-1-labelled ASCII, and verifies all
block checksums, geometry and the complete physical record sequence.
"""
import json,struct,zlib
from pathlib import Path
import xml.etree.ElementTree as ET
from verify_mdx_database import header_attributes

def lzo(b,size):
 i=0;o=bytearray();cap=min(size,8*1024*1024)
 def byte():
  nonlocal i
  if i>=len(b):raise ValueError('truncated LZO')
  v=b[i];i+=1;return v
 def literals(n):
  nonlocal i
  if n>len(b)-i or n>cap-len(o):raise ValueError('literal cap')
  o.extend(b[i:i+n]);i+=n
 def match(p,n):
  if p<0 or p>=len(o) or n>cap-len(o):raise ValueError(('match cap',p,n,len(o)))
  for _ in range(n):o.append(o[p]);p+=1
 def length(t,mask):
  n=t&mask
  if n:return n
  n=mask
  v=byte()
  while v==0:n+=255;v=byte()
  return n+v
 state=0
 if b and b[0]>17:
  n=byte()-17;literals(n);state=4 if n>=4 else n
 while True:
  t=byte()
  if t<16:
   if state==0:
    n=length(t,15)+3;literals(n);state=4;continue
   off=byte();p=len(o)-(0x801 if state==4 else 1)-(t>>2)-(off<<2);n=3 if state==4 else 2;trailing=t&3
  elif t>=64:
   off=byte();p=len(o)-1-((t>>2)&7)-(off<<3);n=(t>>5)+1;trailing=t&3
  elif t>=32:
   n=length(t,31)+2;off=byte()|(byte()<<8);p=len(o)-1-(off>>2);trailing=off&3
  else:
   n=length(t,7)+2;off=byte()|(byte()<<8);p=len(o)-((t&8)<<11)-(off>>2);trailing=off&3
   if p==len(o):
    if n!=3 or trailing or i!=len(b) or len(o)!=size:raise ValueError('LZO EOF')
    return bytes(o)
   p-=0x4000
  match(p,n);literals(trailing);state=trailing


def block(b,n):
    if not 0<=n<=8*1024*1024 or len(b)<8:raise ValueError('Block size cap')
    typ=int.from_bytes(b[:4],'little')
    if typ==1:out=lzo(b[8:],n)
    elif typ==2:
        decoder=zlib.decompressobj();out=decoder.decompress(b[8:],n+1)
        if len(out)!=n or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError('Zlib framing')
    elif typ==0:out=b[8:]
    else:raise ValueError('Compression type')
    if len(out)!=n or zlib.adler32(out)&0xffffffff!=int.from_bytes(b[4:8],'big'):raise ValueError('Block checksum')
    return out

def decode(path):
    with Path(path).open('rb') as f:b=f.read(128*1024*1024+1)
    if len(b)>128*1024*1024:raise ValueError('File cap')
    pos=0
    def take(n):
        nonlocal pos
        if not 0<=n<=len(b)-pos:raise ValueError('Truncated structure')
        out=b[pos:pos+n];pos+=n;return out
    def nums(n):return struct.unpack('>'+str(n)+'I',take(n*4))
    n=nums(1)[0]
    if n<2 or n%2 or n>65536:raise ValueError('Header cap')
    raw=take(n)
    if zlib.adler32(raw)&0xffffffff!=int.from_bytes(take(4),'little'):raise ValueError('Header checksum')
    xml=raw.decode('utf-16le').removeprefix('\ufeff').removesuffix('\0');root=ET.fromstring(xml);a=header_attributes(xml)
    if root.tag!='Dictionary' or any(a.get(k)!='1.2' for k in ['GeneratedByEngineVersion','RequiredEngineVersion']) or a.get('Encrypted','No').lower() not in ('no','0','') or a.get('Encoding','').upper()!='ISO8859-1':raise ValueError('Require v1.2 unencrypted ISO8859-1')
    nb,count,isz,ksz=nums(4)
    if not 0<nb<=count<=100000 or isz>16*1024*1024 or ksz>128*1024*1024:raise ValueError('Index caps')
    info=take(isz);ip=0;descriptors=[]
    for _ in range(nb):
        c=struct.unpack_from('>I',info,ip)[0];ip+=4;names=[]
        for j in range(2):n=info[ip];ip+=1;names.append(info[ip:ip+n]);ip+=n
        pk,up=struct.unpack_from('>2I',info,ip);ip+=8;descriptors.append((c,names,pk,up))
    if ip!=len(info) or sum(p for c,n,p,u in descriptors)!=ksz or sum(c for c,n,p,u in descriptors)!=count:raise ValueError('Index geometry')
    keys=[];offsets=[]
    for c,names,pk,up in descriptors:
        data=block(take(pk),up);kp=0;batch=[]
        for _ in range(c):
            off=struct.unpack_from('>I',data,kp)[0];kp+=4;end=data.index(0,kp);key=data[kp:end];kp=end+1
            if not key or len(key)>4096 or not key.isascii():raise ValueError('Non-ASCII or invalid headword')
            keys.append(key.decode('ascii'));batch.append(key);offsets.append(off)
        if not batch or names!=[batch[0],batch[-1]] or kp!=len(data):raise ValueError('Key boundaries')
    nr,n,ri,rs=nums(4)
    if not 0<nr<=100000 or n!=count or ri!=nr*8 or rs>128*1024*1024:raise ValueError('Record geometry')
    desc=[nums(2) for _ in range(nr)]
    if sum(p for p,u in desc)!=rs or sum(u for p,u in desc)>32*1024*1024:raise ValueError('Record caps')
    body=b''.join(block(take(pk),up) for pk,up in desc)
    if pos!=len(b) or offsets!=sorted(offsets) or offsets[0]!=0 or offsets[-1]>=len(body):raise ValueError('Offsets or trailing bytes')
    rows=[]
    for i,key in enumerate(keys):
        raw=body[offsets[i]:offsets[i+1] if i+1<len(offsets) else len(body)]
        if not raw.endswith(b'\0') or b'\0' in raw[:-1] or not raw.isascii() or len(raw)>1024*1024+1:raise ValueError('Non-ASCII or invalid body')
        rows.append((key,raw[:-1].decode('ascii')))
    if sum(len(k)+len(t) for k,t in rows)>32*1024*1024:raise ValueError('Decoded cap')
    return rows,a

def envelope(b):return b'\0'*4+struct.pack('>I',zlib.adler32(b)&0xffffffff)+b

def fixture(nonascii=False):
    rows=[('apple','`1`fruit'),('duplicate','first'),('duplicate','second'),('empty',''),('last','last definition')]
    attrs={'GeneratedByEngineVersion':'1.2','RequiredEngineVersion':'1.2','Encrypted':'No','Encoding':'ISO8859-1','Format':'Html','Compact':'Yes','Compat':'Yes','KeyCaseSensitive':'No','Title':'Synthetic v1 ASCII','Description':'No encoding guess','StyleSheet':'1\n<b>\n</b>\n'}
    h=(ET.tostring(ET.Element('Dictionary',attrs),encoding='unicode')+'\r\n\0').encode('utf-16le');body=b'';records=[]
    for i,(k,t) in enumerate(rows):
        records.append(struct.pack('>I',len(body))+k.encode()+b'\0');body+=t.encode()+(b'\xc3\xa9' if nonascii and i==4 else b'')+b'\0'
    info=b'';keyblocks=b''
    for start,end in [(0,2),(2,5)]:
        keys=b''.join(records[start:end]);packed=envelope(keys);info+=struct.pack('>I',end-start)
        for key in [rows[start][0],rows[end-1][0]]:value=key.encode();info+=bytes([len(value)])+value
        info+=struct.pack('>II',len(packed),len(keys));keyblocks+=packed
    parts=[body[:7],body[7:]];blocks=[envelope(part) for part in parts]
    data=struct.pack('>I',len(h))+h+struct.pack('<I',zlib.adler32(h)&0xffffffff)+struct.pack('>4I',2,len(rows),len(info),len(keyblocks))+info+keyblocks+struct.pack('>4I',2,len(rows),16,sum(map(len,blocks)))+b''.join(struct.pack('>II',len(p),len(u)) for p,u in zip(blocks,parts))+b''.join(blocks)
    return data,rows,attrs

def write_fixtures(root):
    root.mkdir(parents=True,exist_ok=True)
    for name,bad in [('ascii',False),('nonascii',True)]:
        data,rows,attrs=fixture(bad);path=root/(name+'.mdx');path.write_bytes(data)
        if not bad:
            assert decode(path)==(rows,attrs)
            (root/'ascii.jsonl').write_text(''.join(json.dumps({'key':k,'text':t},separators=(',',':'))+'\n' for k,t in rows),encoding='utf-8')

if __name__=='__main__':write_fixtures(Path(__file__).resolve().parents[1]/'m3/fixtures/mdx-v1-ascii')
