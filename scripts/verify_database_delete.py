"""Independently verify removal of exactly one source row into a new database."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_database_entry import inspect


def check(source, copy, rowid):
    assert source.resolve() != copy.resolve(), 'Require a new database copy'
    assert str(int(rowid)) == rowid and -(2**63) <= int(rowid) < 2**63
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    old, old_meta, attrs = inspect(source)
    assert sum(rid == int(rowid) for rid, _, _ in old) == 1, 'Selected source rowid missing'
    expected = [(k,t) for rid,k,t in old if rid != int(rowid)]
    assert expected, 'At least one entry must remain'
    rows, meta, copied_attrs = inspect(copy)
    assert [(k,t) for _,k,t in rows] == expected, 'Wrong row removed or surviving rows/order changed'
    assert [rid for rid,_,_ in rows] == list(range(1,len(rows)+1)), 'Expected rebuilt row numbers'
    assert copied_attrs == attrs, 'Dictionary metadata changed'
    assert meta['source_sha256'] == before
    assert meta['text_profile'] == old_meta.get('text_profile', 'canonical_v1')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, 'Source changed'
    return {'status':'passed','records':len(rows),'source_rowid':rowid,
            'source_sha256':before,'copy_sha256':hashlib.sha256(copy.read_bytes()).hexdigest(),
            'rows_sha256':meta['rows_sha256'],'unselected_rows_and_metadata_preserved':True,'source_unchanged':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--copy',type=Path,required=True)
    p.add_argument('--rowid',required=True)
    a=p.parse_args()
    try:
        result=check(a.source,a.copy,a.rowid)
    except Exception as error:
        result={'status':'failed','error':f'{type(error).__name__}: {error}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
