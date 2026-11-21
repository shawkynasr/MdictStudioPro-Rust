"""Add an ordinal FNV scan to the complete frozen-sort source preparation."""
import sqlite3
from bounded_fixtures import digest_row
from real_publication_oracle import prepare

def prepare_cc(source,directory):
    inventory,manifest,resources=prepare(source,'mdx',directory)
    db=sqlite3.connect(directory/'records.sqlite');db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA temp_store=FILE');state=0xcbf29ce484222325;count=keys=payload=0
    try:
        for i,(k,data) in enumerate(db.execute('SELECT k,data FROM records ORDER BY s,n')):
            state=digest_row(state,i,k,data);count+=1;keys+=len(k.encode());payload+=len(data)
    finally:db.close()
    return inventory,{'records':count,'key_bytes':keys,'payload_bytes':payload,'framed_fnv64':f'{state:016x}'},manifest,resources
