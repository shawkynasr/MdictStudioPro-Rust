"""Independently check that a database copy changes exactly one selected definition."""
import argparse
import hashlib
import json
from pathlib import Path
from m4_database import framed, readonly


def inspect(path):
    assert path.stat().st_size <= 128*1024*1024
    c = readonly(path)
    try:
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        rows = c.execute('SELECT rowid,entry,paraphrase FROM mdx ORDER BY rowid').fetchall()
        assert 0 < len(rows) <= 100000
        assert all(isinstance(k, str) and isinstance(t, str) and len(k.encode()) <= 4096 and len(t.encode()) <= 1024*1024 for _, k, t in rows)
        assert sum(len(k.encode())+len(t.encode()) for _, k, t in rows) <= 32*1024*1024
        own = c.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='studio_meta'").fetchone()[0]
        meta = dict(c.execute('SELECT key,value FROM studio_meta')) if own else {}
        if meta:
            assert meta['rows_sha256'] == framed([(k,t) for _,k,t in rows]) and meta['records'] == str(len(rows))
        attrs = None
        if 'mdx_header_json' in meta:
            assert hashlib.sha256(meta['mdx_header_json'].encode()).hexdigest() == meta['mdx_header_sha256']
            attrs = json.loads(meta['mdx_header_json'])
        return rows, meta, attrs
    finally:
        c.close()


def check(source, copy, rowid, body, key=None):
    if key is not None:
        assert key and key != "</>" and not any(c in key for c in "\0\r\n") and len(key.encode()) <= 4096
    assert str(int(rowid)) == rowid and -(2**63) <= int(rowid) < 2**63
    assert len(body.encode()) <= 8192
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    old, old_meta, attrs = inspect(source)
    selected = [i for i, row in enumerate(old) if row[0] == int(rowid)]
    assert len(selected) == 1, 'Selected source rowid missing'
    index = selected[0]
    expected = [(key if i == index and key is not None else k, body if i == index else t) for i, (_,k,t) in enumerate(old)]
    rows, meta, copied_attrs = inspect(copy)
    assert [(k,t) for _,k,t in rows] == expected, 'Keys, unselected definitions, duplicates or order changed'
    assert [rid for rid,_,_ in rows] == list(range(1,len(rows)+1)), 'Expected rebuilt row numbers'
    assert copied_attrs == attrs, 'Dictionary metadata changed'
    assert meta['source_sha256'] == before
    assert meta['text_profile'] == old_meta.get('text_profile', 'canonical_v1')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before, 'Source changed'
    return {'status':'passed','records':len(rows),'source_rowid':rowid,'output_rowid':str(index+1),
            'source_sha256':before,'copy_sha256':hashlib.sha256(copy.read_bytes()).hexdigest(),
            'rows_sha256':meta['rows_sha256'],'unselected_rows_and_metadata_preserved':True,'source_unchanged':True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--copy',type=Path,required=True)
    p.add_argument('--rowid',required=True)
    p.add_argument('--text',required=True)
    p.add_argument('--key',help='Exact replacement headword; omit to preserve it')
    a=p.parse_args()
    try:
        result=check(a.source,a.copy,a.rowid,a.text,a.key)
    except Exception as error:
        result={'status':'failed','error':f'{type(error).__name__}: {error}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
