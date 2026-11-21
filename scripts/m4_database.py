"""Qualify the isolated Rust SQLite backend against an independent Python oracle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tomllib
import traceback

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m4/database/Cargo.toml'
APP_ID=1296323408
META_SQL='CREATE TABLE studio_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)'
MDX_SQL='CREATE TABLE mdx (entry TEXT NOT NULL, paraphrase TEXT NOT NULL)'


def framed(rows):
    digest=hashlib.sha256()
    for ordinal,(key,body) in enumerate(rows):
        digest.update(ordinal.to_bytes(8,'big'))
        for value in (key,body):
            data=value.encode('utf-8')
            digest.update(len(data).to_bytes(8,'big'))
            digest.update(data)
    return digest.hexdigest()


def readonly(path):
    # as_uri percent-encodes path punctuation; user text never becomes SQL.
    return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)


def check_database(path,expected,source_hash):
    with readonly(path) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert connection.execute('PRAGMA application_id').fetchone()[0]==APP_ID
        assert connection.execute('PRAGMA user_version').fetchone()[0]==1
        rows=connection.execute('SELECT entry,paraphrase FROM mdx ORDER BY rowid').fetchall()
        assert rows==expected,'SQLite rows/order/multiplicity differ from independent TXT parse'
        meta=dict(connection.execute('SELECT key,value FROM studio_meta'))
        assert meta['profile']=='studio-sqlite-text-v1'
        assert meta['source_sha256']==source_hash
        assert meta['rows_sha256']==framed(expected)
        assert meta['records']==str(len(expected))
        assert meta['text_profile']=='canonical_v1'
    return {'records':len(expected),'rows_sha256':framed(expected)}


def graph(lock):
    packages=tomllib.loads(lock.read_text())['package']
    assert next(p for p in packages if p['name']=='rusqlite')['version']=='0.43.0'
    registry=[{'name':p['name'],'version':p['version'],'checksum':p['checksum']} for p in packages if p.get('source')]
    assert all(len(p['checksum'])==64 and all(c in '0123456789abcdef' for c in p['checksum']) for p in registry)
    return registry


def protected():
    from m2_closeout import inventory
    from m3_shell import sources
    result=inventory()
    result.update(sources())
    for path in (ROOT/'m3').rglob('Cargo.lock'):
        if 'target' not in path.parts:result[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def source_inventory():
    paths=[p for p in (ROOT/'m4/database').rglob('*') if p.is_file() and 'target' not in p.parts and p.name!='Cargo.lock']
    paths.extend([ROOT/'scripts/m4_database.py',ROOT/'scripts/test_m4_database.py',ROOT/'docs/M4-DATABASE.md'])
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install',action='store_true',help='Create only the new isolated database lock if absent and fetch its locked crates')
    parser.add_argument('--output',type=Path,default=Path('m4-database-out'))
    args=parser.parse_args()
    out=args.output.resolve()
    if not out.name.startswith('m4-database-out'):parser.error('Use an m4-database-out prefix')
    out.mkdir(parents=True,exist_ok=False)
    report={'schema':'studio-m4-database-v1','status':'failed','native_tests_executed':False,'database_GUI_enabled':False,'steps':[],'checks':[]}

    def run(name,command,expected=0):
        report['stage']=name
        print(name,flush=True)
        done=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=1200)
        log=done.stdout+'\nSTDERR:\n'+done.stderr
        (out/(name+'.log')).write_text(log)
        report['steps'].append({'name':name,'command':[str(c) for c in command],'returncode':done.returncode,'log_tail':log[-24000:]})
        if done.returncode!=expected:raise RuntimeError(name+' failed')
        return done.stdout

    try:
        report['protected_source_sha256']=protected()
        report['source_sha256']=source_inventory()
        cargo=shutil.which('cargo')
        if not cargo:raise RuntimeError('Rust/Cargo required; no native SQLite checks ran')
        lock=ROOT/'m4/database/Cargo.lock'
        if args.install:
            if not lock.exists():run('database-lock',[cargo,'generate-lockfile','--manifest-path',MANIFEST])
            run('database-fetch',[cargo,'fetch','--locked','--manifest-path',MANIFEST])
        if not lock.exists():raise RuntimeError('First run requires --install to resolve only m4/database/Cargo.lock')
        report['registry_graph']=graph(lock)
        report['resolved_lock_toml']=lock.read_text()
        report['lock_sha256']=hashlib.sha256(lock.read_bytes()).hexdigest()
        metadata=json.loads(run('database-metadata',[cargo,'metadata','--offline','--locked','--format-version','1','--manifest-path',MANIFEST]))
        run('database-tests',[cargo,'test','--offline','--locked','--manifest-path',MANIFEST])
        report['native_tests_executed']=True
        run('database-build',[cargo,'build','--offline','--locked','--manifest-path',MANIFEST])
        binary=Path(metadata['target_directory'])/'debug'/('studio-database.exe' if os.name=='nt' else 'studio-database')

        def execute(name,request,error=None):
            path=out/(name+'.request.json');path.write_text(json.dumps(request,ensure_ascii=False))
            result=json.loads(run(name,[str(binary),'execute',str(path)],expected=1 if error else 0))
            if error:assert result['status']=='failed' and result['error']['code']==error,result
            else:assert result['status']=='passed',result
            return result

        from verify_gui_extraction import txt_rows
        source=out/'source.txt';shutil.copyfile(ROOT/'m3/fixtures/build-source.txt',source)
        expected=txt_rows(source);assert len(expected)==5
        source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
        db=out/'dictionary.db';exported=out/'roundtrip.txt'
        created=execute('create',{'operation':'txt_to_db','source':str(source),'destination':str(db),'profile':'canonical_v1'})
        report['oracle']=check_database(db,expected,source_hash)
        report['sqlite_version']=created['result']['value']['sqlite_version']
        report['checks'].append('python_sqlite_exact_rows_and_studio_metadata')
        execute('export',{'operation':'db_to_txt','source':str(db),'destination':str(exported)})
        assert txt_rows(exported)==expected
        assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash
        report['checks'].append('txt_db_txt_duplicate_and_body_roundtrip')
        key=next(key for key,_ in expected if sum(other==key for other,_ in expected)>1)
        first=execute('lookup-first',{'operation':'lookup','source':str(db),'query':key,'offset':0,'limit':1})['result']['value']
        second=execute('lookup-second',{'operation':'lookup','source':str(db),'query':key,'offset':1,'limit':1})['result']['value']
        assert first['total']==2 and first['next_offset']==1 and second['next_offset'] is None
        assert [first['rows'][0]['text'],second['rows'][0]['text']]==[body for headword,body in expected if headword==key]
        report['checks'].append('exact_duplicate_lookup_pagination')
        before=db.read_bytes();browsed=[];offset=0
        while True:
            page=execute('browse-'+str(offset),{'operation':'browse','source':str(db),'offset':offset,'limit':2})['result']['value']
            assert page['total']==5
            browsed.extend((row['key'],row['text']) for row in page['rows'])
            if page['next_offset'] is None:break
            offset=page['next_offset']
        assert browsed==expected and db.read_bytes()==before
        report['checks'].append('read_only_browse_pagination_exact_order')
        for name,destination,operation,input_path in [('existing-db',db,'txt_to_db',source),('existing-txt',exported,'db_to_txt',db)]:
            before=destination.read_bytes();request={'operation':operation,'source':str(input_path),'destination':str(destination)}
            if operation=='txt_to_db':request['profile']='canonical_v1'
            execute(name,request,'destination_exists');assert destination.read_bytes()==before
        report['checks'].append('existing_destinations_unchanged')
        legacy=out/'legacy.db'
        with sqlite3.connect(legacy) as connection:
            connection.execute(MDX_SQL);connection.executemany('INSERT INTO mdx VALUES (?,?)',expected)
        connection.close()
        legacy_out=out/'legacy-export.txt';execute('legacy-import',{'operation':'db_to_txt','source':str(legacy),'destination':str(legacy_out)})
        assert txt_rows(legacy_out)==expected
        report['checks'].append('python_created_legacy_two_text_column_database')
        malformed=out/'malformed.txt';malformed.write_text('word\nmissing delimiter\n');absent=out/'must-not-exist.db'
        execute('malformed-txt',{'operation':'txt_to_db','source':str(malformed),'destination':str(absent),'profile':'canonical_v1'},'invalid_input');assert not absent.exists()
        compressed=out/'compressed.db'
        with sqlite3.connect(compressed) as connection:
            connection.execute(MDX_SQL);connection.execute('INSERT INTO mdx VALUES (?,?)',('word',sqlite3.Binary(b'not text')))
        connection.close()
        absent=out/'compressed-must-not-exist.txt';execute('compressed-refusal',{'operation':'db_to_txt','source':str(compressed),'destination':str(absent)},'unsupported_profile');assert not absent.exists()
        report['checks'].append('malformed_and_blob_inputs_refused_without_publication')
        assert protected()==report['protected_source_sha256'],'Accepted M2 or desktop M3 sources/locks changed'
        assert source_inventory()==report['source_sha256'],'Database sources changed during qualification'
        assert hashlib.sha256(lock.read_bytes()).hexdigest()==report['lock_sha256'],'Database lock changed during qualification'
        report['status']='backend_subset_passed'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc);report['traceback']=traceback.format_exc()
    finally:
        path=out/'m4-database-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(report['status']+': '+str(path),flush=True)
    return 0 if report['status']=='backend_subset_passed' else 1


if __name__=='__main__':raise SystemExit(main())
