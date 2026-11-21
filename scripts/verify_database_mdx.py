"""Compare a rebuilt MDX with its source SQLite DB, using independent readers."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from m4_database import readonly,framed
from verify_mdx_database import read_mdx


def groups(rows):
    result=defaultdict(list)
    for key,body in rows:result[key].append(body)
    return dict(result)


def check(database,actual_rows,actual_attributes):
    connection=readonly(database)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        expected=connection.execute('SELECT entry,paraphrase FROM mdx ORDER BY rowid').fetchall()
        assert len(expected)==len(actual_rows) and groups(expected)==groups(actual_rows),'Definitions, duplicate multiplicity or duplicate order differ'
        own=connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='studio_meta'").fetchone()[0]
        meta=dict(connection.execute('SELECT key,value FROM studio_meta')) if own else {}
        if own:
            assert meta['records']==str(len(expected)) and meta['rows_sha256']==framed(expected)
        if 'mdx_header_json' in meta:
            assert hashlib.sha256(meta['mdx_header_json'].encode()).hexdigest()==meta['mdx_header_sha256']
            assert json.loads(meta['mdx_header_json'])==actual_attributes,'Stored MDX metadata differs from rebuilt header'
        else:
            for key,value in {'Title':database.stem,'Description':'','StyleSheet':'','Encoding':'UTF-8','KeyCaseSensitive':'No','StripKey':'No'}.items():
                assert actual_attributes.get(key)==value,f'Unexpected plain database default: {key}'
        return {'status':'passed','records':len(expected),'duplicate_definitions_preserved':True,'stored_metadata_preserved':'mdx_header_json' in meta,'encoding':actual_attributes.get('Encoding'),'title':actual_attributes.get('Title')}
    finally:
        connection.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--mdx',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.database.stat().st_size>128*1024*1024 or args.mdx.stat().st_size>128*1024*1024:raise ValueError('File exceeds 128 MiB verification profile')
        before=hashlib.sha256(args.database.read_bytes()).hexdigest()
        output_hash,rows,attributes=read_mdx(args.mdx)
        result=check(args.database,rows,attributes)
        assert hashlib.sha256(args.database.read_bytes()).hexdigest()==before,'Database changed during verification'
        result.update({'database_sha256':before,'mdx_sha256':output_hash})
    except Exception as e:
        result={'status':'failed','error':f'{type(e).__name__}: {e}'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
