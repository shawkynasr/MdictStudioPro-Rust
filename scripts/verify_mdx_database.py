"""Independently compare an MDX and its GUI-created SQLite copy (mdict-utils)."""
import argparse
import hashlib
import json
import re
import struct
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from m4_database import APP_ID,framed,readonly


def header_attributes(xml):
    # MDX numeric stylesheets use literal LF triplets in attribute values.
    # ElementTree applies XML attribute-whitespace normalization (LF -> space),
    # unlike the native MDX reader. Validate the XML first, then protect literal
    # attribute whitespace with references before decoding entities. Existing
    # references and escaped quotes remain untouched; no dictionary is edited.
    ET.fromstring(xml)
    def protect(match):
        return match.group().translate({10: '&#10;', 13: '&#13;', 9: '&#9;'})
    protected = re.sub(r"\"[^\"]*\"|'[^']*'", protect, xml)
    element = ET.fromstring(protected)
    assert element.tag == 'Dictionary', 'Expected Dictionary header'
    known=['GeneratedByEngineVersion','RequiredEngineVersion','Encrypted','Encoding','Format','KeyCaseSensitive','StripKey','Title','Description','StyleSheet','Compact','Compat']
    return {next((k for k in known if k.lower()==name.lower()),name):value
            for name,value in element.attrib.items()}


def check(path,expected_rows,expected_attributes,source_sha256):
    connection=readonly(path)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert connection.execute('PRAGMA application_id').fetchone()[0]==APP_ID
        assert connection.execute('PRAGMA user_version').fetchone()[0]==2
        rows=connection.execute('SELECT entry,paraphrase FROM mdx ORDER BY rowid').fetchall()
        assert rows==expected_rows,'Definitions, duplicates, or physical order differ'
        meta=dict(connection.execute('SELECT key,value FROM studio_meta'))
        assert set(meta)=={'profile','records','rows_sha256','source_sha256','text_profile','mdx_header_json','mdx_header_sha256'}
        assert meta['profile']=='studio-sqlite-mdx-v1'
        assert meta['text_profile']=='canonical_v1'
        assert meta['records']==str(len(rows)) and meta['rows_sha256']==framed(rows)
        assert meta['source_sha256']==source_sha256
        assert hashlib.sha256(meta['mdx_header_json'].encode()).hexdigest()==meta['mdx_header_sha256']
        assert json.loads(meta['mdx_header_json'])==expected_attributes,'Decoded MDX header attributes differ'
        return {'status':'passed','records':len(rows),'metadata_attributes':len(expected_attributes),'numeric_stylesheet_preserved':json.loads(meta['mdx_header_json']).get('StyleSheet','')==expected_attributes.get('StyleSheet',''),'source_sha256':source_sha256}
    finally:
        connection.close()


def read_mdx(path):
    from mdict_utils.base.readmdict import MDX
    from patched_interop import decode
    source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    reader=MDX(str(path),substyle=False)
    rows=[];decoded=0
    for key,value in reader.items():
        key,body=decode(key),decode(value);decoded+=len(key.encode())+len(body.encode())
        if len(rows)>=100000 or decoded>32*1024*1024:raise ValueError('Decoded profile exceeded')
        rows.append((key,body))
    with path.open('rb') as stream:
        length=struct.unpack('>I',stream.read(4))[0]
        if not 2<=length<=1024*1024 or length%2:raise ValueError('Invalid MDX header length')
        raw=stream.read(length);crc=stream.read(4)
    assert raw.endswith(b'\0\0') and len(raw)==length
    assert zlib.adler32(raw)&0xffffffff==struct.unpack('<I',crc)[0]
    attributes=header_attributes(raw.decode('utf-16le').removeprefix('\ufeff').removesuffix('\0'))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==source_hash,'MDX changed during verification'
    return source_hash,rows,attributes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mdx',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.mdx.stat().st_size>128*1024*1024 or args.database.stat().st_size>128*1024*1024:raise ValueError('File exceeds 128 MiB qualification profile')
        source_hash,rows,attributes=read_mdx(args.mdx)
        result=check(args.database,rows,attributes,source_hash)
        assert hashlib.sha256(args.mdx.read_bytes()).hexdigest()==source_hash,'MDX changed during verification'
    except Exception as e:
        result={'status':'failed','error':f'{type(e).__name__}: {e}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
