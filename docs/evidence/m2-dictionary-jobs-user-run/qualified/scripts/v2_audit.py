"""Independent structural audit of unencrypted zlib/plain MDict v2 files.

This stdlib-only auditor is not mdictlib, mdict-utils, or a native reader.
It does not establish cross-engine compatibility or visual rendering.
"""
import argparse
import collections
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import struct
import tempfile
import zlib
from real_corpus import file_hash
from patched_interop import require


def exact(stream,size):
    require(0<=size<=256*1024*1024,"Audit single-block limit exceeded")
    data=stream.read(size);require(len(data)==size,"Truncated dictionary section");return data


def block(data,expected):
    require(0<=expected<=256*1024*1024,"Audit decompressed-block limit exceeded")
    require(len(data)>=8,"Short compressed block")
    method=struct.unpack("<I",data[:4])[0]
    if method==0: body=data[8:]
    elif method==2:
        decoder=zlib.decompressobj();body=decoder.decompress(data[8:],expected+1)
        require(decoder.eof and not decoder.unused_data,"Incomplete or trailing compressed data")
    else: raise ValueError(f"Unsupported block compression/encryption tag {method}")
    require(len(body)==expected,"Decompressed length mismatch")
    require(zlib.adler32(body)&0xffffffff==struct.unpack(">I",data[4:8])[0],"Block ADLER32 mismatch")
    return body


class Assets(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True);self.paths=set()
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if value and key in {"src","href"}:
                if value.startswith(("#","http:","https:","data:","entry:","bword:","javascript:","mailto:")): continue
                if value.startswith("sound://"): value=value[len("sound://"):]
                value=value.split("#",1)[0].split("?",1)[0]
                if value:self.paths.add(value.replace("\\","/").lstrip("/"))


def css_urls(text):
    text=re.sub(r'/\*.*?\*/',"",text,flags=re.S)
    values=[]
    for match in re.finditer(r'url\(\s*([\'"]?)(.*?)\1\s*\)',text,re.I):
        value=match.group(2).strip()
        if value.startswith(("#","http:","https:","data:")):continue
        value=value.split("#",1)[0].split("?",1)[0]
        if value:values.append(value.replace("\\","/"))
    return sorted(set(values))


def audit(path):
    path=path.resolve();before=file_hash(path)
    result={"file":path.name,"sha256":before,"size_bytes":path.stat().st_size,"status":"failed","scope":"independent structural audit only; no Rust/Python engine comparison or GUI verification"}
    try:
        with path.open("rb") as source,tempfile.TemporaryDirectory() as tmp:
            db=sqlite3.connect(Path(tmp)/"keys.sqlite")
            try:
                db.execute("CREATE TABLE keys(n INTEGER PRIMARY KEY,k TEXT NOT NULL,o INTEGER NOT NULL)")
                size=struct.unpack(">I",exact(source,4))[0];require(size<=1024*1024,"Oversized XML header")
                raw=exact(source,size);checksum=struct.unpack("<I",exact(source,4))[0]
                require(checksum==zlib.adler32(raw)&0xffffffff,"XML header checksum mismatch")
                attrs={k:html.unescape(v) for k,v in re.findall(r'(\w+)="(.*?)"',raw.decode("utf-16le").rstrip("\0\r\n"),re.S)}
                result["header"]={k:attrs.get(k) for k in ["GeneratedByEngineVersion","Encoding","Encrypted","Compact","Format","KeyCaseSensitive","StripKey"]}
                result["embedded_stylesheet_characters"]=len(attrs.get("StyleSheet",""))
                require(attrs.get("GeneratedByEngineVersion")=="2.0","Auditor supports v2 only")
                require(attrs.get("Encrypted","No").lower() in {"no","0",""},"Auditor does not support encrypted input")
                kind="mdd" if path.suffix.lower()==".mdd" else "mdx"
                encoding="utf-16le" if kind=="mdd" else attrs.get("Encoding","UTF-8")
                if encoding.upper()=="UTF-16":encoding="utf-16le"
                unit=2 if encoding.lower().replace("-","") in {"utf16le","utf16"} else 1
                summary=exact(source,40)
                blocks,count,info_size,info_comp,key_comp=struct.unpack(">5Q",summary)
                require(zlib.adler32(summary)&0xffffffff==struct.unpack(">I",exact(source,4))[0],"Key-section checksum mismatch")
                info=block(exact(source,info_comp),info_size)
                cursor=0;descriptors=[]
                for _ in range(blocks):
                    n=struct.unpack_from(">Q",info,cursor)[0];cursor+=8
                    boundaries=[]
                    for _ in range(2):
                        units=struct.unpack_from(">H",info,cursor)[0];cursor+=2
                        boundaries.append(info[cursor:cursor+units*unit].decode(encoding,"strict"));cursor+=(units+1)*unit
                    packed,unpacked=struct.unpack_from(">QQ",info,cursor);cursor+=16
                    descriptors.append((n,packed,unpacked,boundaries))
                require(cursor==len(info),"Key summary has trailing bytes")
                require(sum(d[1] for d in descriptors)==key_comp,"Key block sizes do not sum correctly")
                ordinal=0;previous=0
                for n,packed,unpacked,boundaries in descriptors:
                    data=block(exact(source,packed),unpacked);pos=0;first=None;last=None
                    for _ in range(n):
                        offset=struct.unpack_from(">Q",data,pos)[0];pos+=8;end=pos
                        while end+unit<=len(data) and data[end:end+unit]!=b"\0"*unit:end+=unit
                        require(end+unit<=len(data),"Missing key terminator")
                        key=data[pos:end].decode(encoding,"strict");pos=end+unit
                        require(offset>=previous,"Record offsets are decreasing");previous=offset
                        require(offset<2**63,"Record offset exceeds audit index range")
                        db.execute("INSERT INTO keys VALUES(?,?,?)",(ordinal,key,offset));ordinal+=1
                        if first is None:first=key
                        last=key
                    require(pos==len(data),"Trailing keyword block bytes")
                    require([first,last]==boundaries,"First/last key summaries differ from physical entries")
                require(ordinal==count,"Physical key count differs from section count")
                record_blocks,record_entries,record_info_size,record_comp=struct.unpack(">4Q",exact(source,32))
                require(record_entries==count and record_info_size==16*record_blocks,"Record section count/size mismatch")
                rec_info=exact(source,record_info_size)
                records=[struct.unpack_from(">QQ",rec_info,i*16) for i in range(record_blocks)]
                require(sum(p for p,u in records)==record_comp,"Record packed sizes differ from header")
                with tempfile.TemporaryFile() as decoded:
                    total=0
                    for packed,unpacked in records:
                        body=block(exact(source,packed),unpacked);decoded.write(body);total+=len(body)
                    require(source.tell()==path.stat().st_size,"Unexpected bytes after record section")
                    require(previous<=total,"Record offset exceeds record data")
                    db.execute("CREATE INDEX key_names ON keys(k)")
                    resources=[];assets=Assets();redirects=0;markers=0;empty=0;missing_null=0;sample=[];languages=collections.Counter()
                    cursor=db.execute("SELECT k,o,lead(o) OVER (ORDER BY n) FROM keys ORDER BY n")
                    for key,start,end in cursor:
                        end=total if end is None else end;require(end>=start,"Negative record extent")
                        decoded.seek(start);data=exact(decoded,end-start)
                        if kind=="mdd":
                            resource={"path":key,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
                            if key.lower().endswith(".css"):
                                try:resource["css_url_references"]=css_urls(data.decode("utf-8-sig","strict"))
                                except UnicodeDecodeError:resource["css_url_scan"]="not_utf8_not_scanned"
                            resources.append(resource)
                            continue
                        terminal=b"\0"*unit
                        if data.endswith(terminal):data=data[:-unit]
                        else:missing_null+=1
                        text=data.decode(encoding,"strict")
                        if not text:empty+=1
                        if text.startswith("@@@LINK="):redirects+=1
                        markers+=len(re.findall(r'`\d+`',text))
                        assets.feed(text);assets.reset()
                        if any('\u4e00'<=c<='\u9fff' for c in key):languages["CJK_keys"]+=1
                        if any('\u0600'<=c<='\u06ff' for c in key):languages["Arabic_keys"]+=1
                        if len(sample)<8:sample.append(key)
                    duplicates=db.execute("SELECT count(*) FROM (SELECT k FROM keys GROUP BY k HAVING count(*)>1)").fetchone()[0]
                    result.update(records=count,key_blocks=blocks,record_blocks=record_blocks,uncompressed_record_bytes=total,duplicate_headwords=duplicates,
                                  sample_keys=sample,script_counts=dict(languages),redirect_records=redirects,style_markers=markers,empty_bodies=empty,records_without_terminal_null=missing_null,
                                  local_asset_references=sorted(assets.paths),resources=resources,
                                  checks=["header_adler32","key_section_adler32","all_key_block_checksums_and_lengths","physical_key_counts","key_boundary_summaries","all_record_block_checksums_and_lengths","record_offsets","strict_text_decoding"],status="structural_audit_passed")
            finally:db.close()
    except Exception as error:result["error"]=str(error)
    after=file_hash(path);result["sha256_after"]=after
    if before!=after:result.update(status="failed",error="Input changed during audit")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("files",type=Path,nargs="+");parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();reports=[audit(path) for path in args.files]
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump({"suite":"independent-v2-structural-audit-v1","cases":reports,"native_readers":"NOT_RUN","Rust_engine":"NOT_RUN","mdict_utils":"NOT_RUN"},stream,ensure_ascii=False,indent=2)
    for report in reports:print(report["file"],report["status"],report.get("records",report.get("error")))
    return 0 if all(r["status"]=="structural_audit_passed" for r in reports) else 1


if __name__=="__main__":raise SystemExit(main())
