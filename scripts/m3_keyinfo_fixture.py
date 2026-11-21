"""Independent stdlib MDX v2 Encrypted=2 fixtures and bounded wire oracle.

RIPEMD-128 and nibble/XOR keyword-index transform follow the published
RIPEMD-128 specification and readmdict's v2 wire description. This is test
infrastructure only: application decoding remains in the pinned Rust engine.
"""
import hashlib,json,struct,zlib
from pathlib import Path
import xml.etree.ElementTree as ET

R=[list(range(16)),[7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8],[3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12],[1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2]]
RP=[[5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12],[6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2],[15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13],[8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14]]
S=[[11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8],[7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12],[11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5],[11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12]]
SP=[[8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6],[9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11],[9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5],[15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8]]
MASK=0xffffffff

def ripemd128(data):
    size=len(data);data+=b'\x80';data+=b'\0'*((56-len(data))%64)+struct.pack('<Q',size*8)
    h=[0x67452301,0xefcdab89,0x98badcfe,0x10325476]
    def f(n,x,y,z):return [lambda:x^y^z,lambda:(x&y)|(~x&z),lambda:(x|~y)^z,lambda:(x&z)|(y&~z)][n]()
    def lane(words,right):
        a,b,c,d=h
        for q in range(4):
            for j in range(16):
                n=(3-q if right else q);k=([0x50a28be6,0x5c4dd124,0x6d703ef3,0] if right else [0,0x5a827999,0x6ed9eba1,0x8f1bbcdc])[q]
                shift=(SP if right else S)[q][j];v=(a+f(n,b,c,d)+words[(RP if right else R)[q][j]]+k)&MASK
                v=((v<<shift)|(v>>(32-shift)))&MASK;a,d,c,b=d,c,b,v
        return a,b,c,d
    for start in range(0,len(data),64):
        words=struct.unpack('<16I',data[start:start+64]);a,b,c,d=lane(words,False);aa,bb,cc,dd=lane(words,True)
        h=[(h[1]+c+dd)&MASK,(h[2]+d+aa)&MASK,(h[3]+a+bb)&MASK,(h[0]+b+cc)&MASK]
    return struct.pack('<4I',*h)

def transform(block,encrypt=False):
    key=ripemd128(block[4:8]+struct.pack('<I',0x3695));prev=0x36;out=bytearray(block[:8])
    for i,v in enumerate(block[8:]):
        if encrypt:
            t=v^prev^(i&255)^key[i%16];value=((t>>4)|(t<<4))&255;prev=value
        else:
            value=((v>>4)|(v<<4))&255;value^=prev^(i&255)^key[i%16];prev=v
        out.append(value)
    return bytes(out)

def envelope(data):return b'\x02\0\0\0'+struct.pack('>I',zlib.adler32(data)&MASK)+zlib.compress(data)

def fixture(encoding):
    rows=[('apple','<p>fruit</p>'),('empty',''),('مرحبا','<div dir="rtl">أهلاً وسهلاً</div>'),('字','<p>First.</p>'),('字','<p>Second.</p>')]
    enc='utf-8' if encoding=='UTF-8' else 'utf-16le';unit=1 if enc=='utf-8' else 2
    attrs={'GeneratedByEngineVersion':'2.0','RequiredEngineVersion':'2.0','Encrypted':'2','Encoding':encoding,'Format':'Html','KeyCaseSensitive':'No','StripKey':'No','Title':'Keyword index fixture','Description':'UTF-8 / UTF-16 · 字 · العربية','StyleSheet':'','Compact':'No','Compat':'No'}
    header=(ET.tostring(ET.Element('Dictionary',attrs),encoding='unicode')+'\r\n\0').encode('utf-16le')
    keys=b'';body=b''
    for key,text in rows:
        keys+=struct.pack('>Q',len(body))+key.encode(enc)+b'\0'*unit;body+=text.encode(enc)+b'\0'*unit
    kb=envelope(keys);rb=envelope(body)
    info=struct.pack('>Q',len(rows))
    for key in [rows[0][0],rows[-1][0]]:info+=struct.pack('>H',len(key.encode(enc))//unit)+key.encode(enc)+b'\0'*unit
    info+=struct.pack('>QQ',len(kb),len(keys));ib=transform(envelope(info),True)
    summary=struct.pack('>5Q',1,len(rows),len(info),len(ib),len(kb))
    data=struct.pack('>I',len(header))+header+struct.pack('<I',zlib.adler32(header)&MASK)+summary+struct.pack('>I',zlib.adler32(summary)&MASK)+ib+kb+struct.pack('>4Q',1,len(rows),16,len(rb))+struct.pack('>QQ',len(rb),len(body))+rb
    return data,rows,attrs

def decode(path):
    """Bounded canonical v2 zlib/uncompressed oracle; no LZO or legacy fallback."""
    data=Path(path).read_bytes()
    if len(data)>128*1024*1024:raise ValueError('128 MiB input cap')
    pos=0
    def take(n):
        nonlocal pos
        if not 0<=n<=len(data)-pos:raise ValueError('Truncated structure')
        out=data[pos:pos+n];pos+=n;return out
    def nums(n):return struct.unpack('>'+str(n)+'Q',take(8*n))
    def block(b,n):
        if n>8*1024*1024 or len(b)<8:raise ValueError('Block cap')
        if b[:4]==b'\x02\0\0\0':
            d=zlib.decompressobj();out=d.decompress(b[8:],n+1)
            if len(out)!=n or not d.eof or d.unused_data or d.unconsumed_tail:raise ValueError('Block framing')
        elif b[:4]==b'\0'*4:out=b[8:]
        else:raise ValueError('Oracle only supports zlib/uncompressed blocks')
        if len(out)!=n or zlib.adler32(out)&MASK!=struct.unpack('>I',b[4:8])[0]:raise ValueError('Block checksum/size')
        return out
    n=struct.unpack('>I',take(4))[0]
    if n>65536 or n%2:raise ValueError('Header cap')
    header=take(n)
    if zlib.adler32(header)&MASK!=struct.unpack('<I',take(4))[0]:raise ValueError('Header checksum')
    attrs=ET.fromstring(header.decode('utf-16le').removeprefix('\ufeff').removesuffix('\0')).attrib
    if attrs['GeneratedByEngineVersion'] not in ('2','2.0') or attrs['RequiredEngineVersion'] not in ('2','2.0') or attrs.get('Encrypted')!='2':raise ValueError('Require declared v2 Encrypted=2')
    enc={'UTF-8':'utf-8','UTF-16':'utf-16le','UTF-16LE':'utf-16le'}[attrs['Encoding'].upper()];unit=1 if enc=='utf-8' else 2
    summary=take(40);nb,count,info_size,info_comp,key_comp=struct.unpack('>5Q',summary)
    if nb>100000 or count>100000 or info_size>16*1024*1024 or info_comp>16*1024*1024:raise ValueError('Index caps')
    if zlib.adler32(summary)&MASK!=struct.unpack('>I',take(4))[0]:raise ValueError('Section checksum')
    info=block(transform(take(info_comp)),info_size);ip=0;descriptors=[]
    for _ in range(nb):
        c=struct.unpack_from('>Q',info,ip)[0];ip+=8;names=[]
        for _ in range(2):
            size=struct.unpack_from('>H',info,ip)[0];ip+=2
            names.append(info[ip:ip+size*unit].decode(enc));ip+=size*unit
            if info[ip:ip+unit]!=b'\0'*unit:raise ValueError('Summary terminator')
            ip+=unit
        packed,unpacked=struct.unpack_from('>QQ',info,ip);ip+=16;descriptors.append((c,packed,unpacked,names))
    if ip!=len(info) or sum(d[1] for d in descriptors)!=key_comp:raise ValueError('Key index geometry')
    keys=[];offsets=[]
    for c,packed,unpacked,names in descriptors:
        kb=block(take(packed),unpacked);i=0;batch=[]
        for _ in range(c):
            offset=struct.unpack_from('>Q',kb,i)[0];i+=8;end=i
            while end+unit<=len(kb) and kb[end:end+unit]!=b'\0'*unit:end+=unit
            if end+unit>len(kb):raise ValueError('Key terminator')
            key=kb[i:end].decode(enc);i=end+unit;keys.append(key);batch.append(key);offsets.append(offset)
        if i!=len(kb) or not batch or [batch[0],batch[-1]]!=names:raise ValueError('Key block boundaries')
    nr,entries,ri,rsize=nums(4)
    if entries!=count or len(keys)!=count or nr>100000 or ri!=16*nr or rsize>128*1024*1024:raise ValueError('Record geometry')
    descriptors=[nums(2) for _ in range(nr)]
    if sum(p for p,u in descriptors)!=rsize or sum(u for p,u in descriptors)>32*1024*1024:raise ValueError('Record byte cap')
    body=b''.join(block(take(p),u) for p,u in descriptors)
    if pos!=len(data) or offsets!=sorted(offsets) or (offsets and offsets[0]!=0):raise ValueError('Offsets or trailing data')
    rows=[]
    for i,key in enumerate(keys):
        raw=body[offsets[i]:offsets[i+1] if i+1<len(offsets) else len(body)]
        if not raw.endswith(b'\0'*unit):raise ValueError('Body terminator')
        rows.append((key,raw[:-unit].decode(enc)))
    return rows,attrs

def write_fixtures(root):
    root.mkdir(parents=True,exist_ok=True)
    for name,encoding in [('utf8','UTF-8'),('utf16','UTF-16')]:
        data,rows,attrs=fixture(encoding);path=root/(name+'.mdx');path.write_bytes(data)
        assert decode(path)==(rows,attrs)
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'key':k,'text':t},ensure_ascii=False,separators=(',',':'))+'\n' for k,t in rows),encoding='utf-8')

if __name__=='__main__':write_fixtures(Path(__file__).resolve().parents[1]/'m3/fixtures/mdx-keyinfo')
