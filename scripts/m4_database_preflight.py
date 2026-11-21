"""Read-only MDX size preflight; stops at the first observed profile violation."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib
from patched_interop import decode
from verify_mdx_database import header_attributes

FILE_CAP=128*1024*1024
RECORD_CAP=100000
DECODED_CAP=32*1024*1024
KEY_CAP=4096
BODY_CAP=1024*1024


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
    return h.hexdigest()


def choose_mdx():
    if sys.platform!='darwin':raise ValueError('Provide --mdx PATH outside macOS')
    done=subprocess.run(['osascript','-e','POSIX path of (choose file with prompt "Choose an MDX dictionary to check against the database size profile")'],capture_output=True,text=True)
    if done.returncode:raise ValueError('File selection cancelled; no dictionary was checked')
    return Path(done.stdout.rstrip('\r\n'))


def scan_rows(values,retain_rows=False):
    rows=[];count=decoded=largest_key=largest_body=0
    def result(status,issue,complete):
        return ({'status':status,'first_issue':issue,'scan_complete':complete,
                 'counts_scope':'whole_dictionary' if complete else 'observed_prefix_only',
                 'records_observed':count,'decoded_bytes_observed':decoded,
                 'largest_key_bytes_observed':largest_key,'largest_body_bytes_observed':largest_body},
                rows if status=='fits_size_profile' else [])
    for key,body in values:
        key,body=decode(key),decode(body)
        count+=1;k=len(key.encode('utf-8'));t=len(body.encode('utf-8'));decoded+=k+t
        largest_key=max(largest_key,k);largest_body=max(largest_body,t)
        for name,observed,maximum in [('record_count',count,RECORD_CAP),('headword_bytes',k,KEY_CAP),
                                      ('definition_bytes',t,BODY_CAP),('decoded_text_bytes',decoded,DECODED_CAP)]:
            if observed>maximum:
                return result('exceeds_size_profile',{'name':name,'observed':observed,'maximum':maximum,'record_ordinal':count},False)
        if not key or key=='</>' or any(c in key for c in '\0\r\n'):
            return result('invalid_input',{'name':'invalid_headword','record_ordinal':count},False)
        if retain_rows:rows.append((key,body))
    if not count:return result('invalid_input',{'name':'nonempty_dictionary','observed':0,'minimum':1},True)
    return result('fits_size_profile',None,True)


def inspect_mdx(path,retain_rows=False,reader_factory=None):
    start=time.perf_counter();path=path.expanduser().absolute()
    if path.suffix.lower()!='.mdx' or not path.is_file() or path.is_symlink():raise ValueError('Choose a regular non-symlink MDX file')
    before=sha(path);size=path.stat().st_size;attrs=None;rows=[]
    if size>FILE_CAP:
        result={'status':'exceeds_size_profile','first_issue':{'name':'file_bytes','observed':size,'maximum':FILE_CAP},
                'scan_complete':False,'counts_scope':'not_decoded','records_observed':0,'decoded_bytes_observed':0}
    else:
        with path.open('rb') as f:
            prefix=f.read(4)
            if len(prefix)!=4:raise ValueError('Missing MDX header length')
            length=struct.unpack('>I',prefix)[0]
            if not 2<=length<=1024*1024 or length%2:raise ValueError('Invalid MDX header length')
            raw=f.read(length);crc=f.read(4)
        if len(raw)!=length or not raw.endswith(b'\0\0') or len(crc)!=4 or zlib.adler32(raw)&0xffffffff!=struct.unpack('<I',crc)[0]:raise ValueError('Invalid MDX header extent or checksum')
        attrs=header_attributes(raw.decode('utf-16le').removeprefix('\ufeff').removesuffix('\0'))
        if reader_factory is None:
            from mdict_utils.base.readmdict import MDX
            reader_factory=MDX
        reader=reader_factory(str(path),substyle=False);values=iter(reader.items())
        try:result,rows=scan_rows(values,retain_rows)
        finally:
            close=getattr(values,'close',None)
            if close is not None:close()
    if sha(path)!=before:raise ValueError('Source changed during preflight')
    result.update(schema='studio-m4-database-preflight-v1',source={'name':path.name,'sha256':before,'bytes':size},
                  limits={'file_bytes':FILE_CAP,'records':RECORD_CAP,'decoded_text_bytes':DECODED_CAP,'headword_bytes':KEY_CAP,'definition_bytes':BODY_CAP},
                  source_unchanged=True,elapsed_ms=(time.perf_counter()-start)*1000,
                  qualification_scope='Size and headword-shape screening only; no Rust execution, native compatibility or checkpoint completion claim.')
    return result,rows,attrs


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mdx',type=Path,help='Omit for the macOS picker');a=p.parse_args()
    try:
        result,_,_=inspect_mdx(a.mdx if a.mdx is not None else choose_mdx())
    except (Exception,KeyboardInterrupt) as error:result={'status':'failed','error':f'{type(error).__name__}: {error}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='fits_size_profile' else 1


if __name__=='__main__':raise SystemExit(main())
