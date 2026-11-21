"""Read-only comparison of GUI exports with their original TXT/resource fixtures."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import stat

MAX_BYTES=128*1024*1024
MAX_LINE=8*1024*1024
MAX_ROWS=500000
IGNORED={'.DS_Store','.localized'}

def lines(path):
    total=0
    with Path(path).open('rb') as stream:
        while True:
            raw=stream.readline(MAX_LINE+1)
            if not raw:return
            total+=len(raw)
            if total>MAX_BYTES or len(raw)>MAX_LINE:raise ValueError('Entry verification input exceeds its bounded profile')
            yield raw.decode('utf-8',errors='strict')

def txt_rows(path,profile='canonical_v1'):
    result=[];key=None;body=[];body_lines=0;body_bytes=0
    for number,raw in enumerate(lines(path),1):
        if number==1:raw=raw.removeprefix('\ufeff')
        logical=raw[:-2] if raw.endswith('\r\n') else raw[:-1] if raw.endswith('\n') else raw
        if '\r' in logical or '\0' in logical:raise ValueError(f'Line {number}: lone CR or NUL')
        if key is None:
            if not logical or logical=='</>' or len(logical.encode())>4096:raise ValueError(f'Line {number}: invalid headword')
            key=logical
        elif logical=='</>':
            if not body_lines:raise ValueError(f'Line {number}: definition needs a body line')
            text=''.join(body)
            if profile=='canonical_v1':
                if not text.endswith('\n'):raise ValueError(f'Line {number}: missing body separator')
                text=text[:-1]
            result.append((key,text));key=None;body=[];body_lines=0;body_bytes=0
            if len(result)>MAX_ROWS:raise ValueError('Too many verification records')
        else:
            text=logical+('\n' if raw.endswith('\n') else '') if profile=='canonical_v1' else raw
            body_bytes+=len(text.encode())
            if body_bytes>4*1024*1024+1:raise ValueError(f'Line {number}: definition exceeds verification limit')
            body.append(text);body_lines+=1
    if key is not None:raise ValueError('Unterminated final TXT record')
    if not result:raise ValueError('No complete TXT records')
    return result

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON object field')
        result[key]=value
    return result

def jsonl_rows(path):
    result=[]
    for number,line in enumerate(lines(path),1):
        row=json.loads(line,object_pairs_hook=unique_object)
        if not isinstance(row,dict) or set(row)!={'key','text'} or not isinstance(row['key'],str) or not isinstance(row['text'],str):raise ValueError(f'Line {number}: expected key/text strings')
        result.append((row['key'],row['text']))
        if len(result)>MAX_ROWS:raise ValueError('Too many verification records')
    return result

def compare_entries(source,exported):
    original=Counter(source);actual=Counter(exported)
    expected_order=defaultdict(list);actual_order=defaultdict(list)
    for key,text in source:expected_order[key].append(text)
    for key,text in exported:actual_order[key].append(text)
    changed_order=[key for key in expected_order if expected_order[key]!=actual_order.get(key,[])]
    return {'status':'passed' if original==actual and not changed_order else 'failed','expected_records':len(source),'actual_records':len(exported),'missing_records':sum((original-actual).values()),'unexpected_records':sum((actual-original).values()),'changed_definition_or_duplicate_order_keys':changed_order[:10]}

def ignored(name):return name in IGNORED or name.startswith('._')

def resource_inventory(root):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Expected a regular resource directory')
    result={};visited=0;payload=0
    def error(e):raise e
    for directory,dirs,files in os.walk(root,followlinks=False,onerror=error):
        for name in dirs+files:
            visited+=1
            if visited>200000:raise ValueError('Resource verification exceeds path count profile')
            if not ignored(name) and (Path(directory)/name).is_symlink():raise ValueError('Resource verification refuses symlinks')
        dirs[:]=sorted(name for name in dirs if not ignored(name))
        for name in sorted(files):
            if ignored(name):continue
            path=Path(directory)/name;relative=path.relative_to(root).as_posix()
            if len(path.relative_to(root).parts)>32:raise ValueError('Resource path exceeds verification depth profile')
            if not stat.S_ISREG(path.lstat().st_mode):raise ValueError('Expected regular resource files')
            size=0;digest=hashlib.sha256()
            with path.open('rb') as stream:
                while chunk:=stream.read(65536):
                    size+=len(chunk);payload+=len(chunk)
                    if payload>2*1024*1024*1024:raise ValueError('Resource verification exceeds total output profile')
                    if size>256*1024*1024:raise ValueError('Resource exceeds verification file-size profile')
                    digest.update(chunk)
            result[relative]=(size,digest.hexdigest())
            if len(result)>100000:raise ValueError('Resource verification exceeds file count profile')
    return result

def compare_resources(original,extracted):
    before=resource_inventory(original);after=resource_inventory(extracted)
    missing=sorted(before.keys()-after.keys());extra=sorted(after.keys()-before.keys())
    changed=sorted(name for name in before.keys()&after.keys() if before[name]!=after[name])
    return {'status':'passed' if not missing and not extra and not changed else 'failed','expected_files':len(before),'actual_files':len(after),'payload_bytes':sum(size for size,_ in after.values()),'missing_paths':missing[:10],'unexpected_paths':extra[:10],'changed_bytes_paths':changed[:10]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='kind',required=True)
    entries=sub.add_parser('entries');entries.add_argument('--source',type=Path,required=True);entries.add_argument('--txt',type=Path);entries.add_argument('--jsonl',type=Path);entries.add_argument('--source-profile',choices=['canonical_v1','legacy_body_span_v1'],default='canonical_v1')
    resources=sub.add_parser('resources');resources.add_argument('--original',type=Path,required=True);resources.add_argument('--extracted',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.kind=='entries':
            if not args.txt and not args.jsonl:parser.error('Provide --txt and/or --jsonl')
            source=txt_rows(args.source,args.source_profile);checks={}
            if args.txt:checks['txt']=compare_entries(source,txt_rows(args.txt))
            if args.jsonl:checks['jsonl']=compare_entries(source,jsonl_rows(args.jsonl))
            result={'status':'passed' if all(item['status']=='passed' for item in checks.values()) else 'failed','checks':checks}
        else:result=compare_resources(args.original,args.extracted)
    except (OSError,ValueError) as e:result={'status':'failed','error':str(e)}
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
