"""Independently verify that one new entry is appended without changing source rows."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_database_entry import inspect


def check(source, copy, key, body):
    assert source.resolve() != copy.resolve(), 'Require a new database copy'
    assert key and key != '</>' and not any(c in key for c in '\0\r\n') and len(key.encode()) <= 4096
    assert len(body.encode()) <= 8192
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    old,old_meta,attrs=inspect(source)
    assert len(old) < 100000
    expected=[(k,t) for _,k,t in old]+[(key,body)]
    rows,meta,copied_attrs=inspect(copy)
    assert [(k,t) for _,k,t in rows] == expected, 'Existing rows/order changed or new entry not appended exactly once'
    assert [rid for rid,_,_ in rows] == list(range(1,len(rows)+1)), 'Expected rebuilt row numbers'
    assert copied_attrs == attrs, 'Dictionary metadata changed'
    assert meta['source_sha256'] == before
    assert meta['text_profile'] == old_meta.get('text_profile','canonical_v1')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, 'Source changed'
    return {'status':'passed','records':len(rows),'output_rowid':str(len(rows)),
            'source_sha256':before,'copy_sha256':hashlib.sha256(copy.read_bytes()).hexdigest(),
            'rows_sha256':meta['rows_sha256'],'existing_rows_and_metadata_preserved':True,'source_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--copy',type=Path,required=True)
    p.add_argument('--key',required=True)
    p.add_argument('--text',required=True)
    a=p.parse_args()
    try:
        result=check(a.source,a.copy,a.key,a.text)
    except Exception as error:
        result={'status':'failed','error':f'{type(error).__name__}: {error}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
