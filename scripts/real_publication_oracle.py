"""Disk-backed source preparation and frozen sort oracle; never bundles payloads."""
import bisect
import hashlib
import json
import sqlite3
from pathlib import Path
from m2_sizing import ROOT,require,sha
from real_reader_oracle import wire_rows,attrs
from large_io_oracle import digest
class FrozenLower:
    def __init__(self):
        t=json.loads((ROOT/'baseline/unicode/unicode16-casing.json').read_text());self.mapping=dict(t['lower_mappings']);self.cased=t['cased_ranges'];self.ignored=t['case_ignorable_ranges']
        self.starts={id(r):[a for a,b in r] for r in [self.cased,self.ignored]}
    def contains(self,r,c):
        n=ord(c);i=bisect.bisect_right(self.starts[id(r)],n)-1;return i>=0 and n<=r[i][1]
    def __call__(self,text):
        result=[]
        for i,c in enumerate(text):
            if c=='Σ':
                before=next((x for x in reversed(text[:i]) if not self.contains(self.ignored,x)),None);after=next((x for x in text[i+1:] if not self.contains(self.ignored,x)),None)
                if before is not None and self.contains(self.cased,before) and (after is None or not self.contains(self.cased,after)):result.append('ς');continue
            result.append(self.mapping.get(ord(c),c))
        return ''.join(result)
def metadata(source):
    a=attrs(source);reserved={s.lower() for s in ['GeneratedByEngineVersion','RequiredEngineVersion','Encrypted','Encoding','Format','KeyCaseSensitive','StripKey','Title','Description','StyleSheet','Compact','Compat','xmlns']}
    return {'title':a.get('Title',''),'description':a.get('Description',''),'stylesheet':a.get('StyleSheet',''),'extra':{k:v for k,v in a.items() if k.lower() not in reserved}}
def prepare(source,kind,directory):
    directory.mkdir();db=sqlite3.connect(directory/'records.sqlite');db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA temp_store=FILE');db.execute('CREATE TABLE records(n INTEGER PRIMARY KEY,k TEXT,s BLOB,data BLOB)');lower=FrozenLower();resources=directory/'resources';resources.mkdir();manifest=directory/'records.jsonl';count=decoded=plan=maximum=key_bytes=0
    try:
        with manifest.open('w',encoding='utf-8',newline='\n') as out:
            for n,(k,data) in enumerate(wire_rows(source,kind,directory)):
                b=k.encode();sort=lower(k).encode();count+=1;decoded+=len(b)+len(data);key_bytes+=len(b);plan+=160+len(b)+len(sort);maximum=max(maximum,len(data));db.execute('INSERT INTO records VALUES(?,?,?,?)',(n,k,sort,data))
                if kind=='mdx':row={'key':k,'text':data.decode('utf-8')}
                else:
                    name=f'{n:08d}.bin';(resources/name).write_bytes(data);row={'key':k,'file':name}
                out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
                require(count<=500000 and decoded<=2*1024**3 and len(b)<=4096 and len(data)<=4*1024**2,'Source exceeds reader oracle profile')
        db.commit();expected=digest((k,data) for k,data in db.execute('SELECT k,data FROM records ORDER BY s,n'))
        blockers=[]
        for field,value,cap in [('records',count,100000),('decoded_bytes',decoded,32*1024**2),('largest_payload',maximum,1024**2),('conservative_plan_charge',plan,16*1024**2),('manifest_bytes',manifest.stat().st_size,128*1024**2)]:
            if value>cap:blockers.append({'limit':field,'value':value,'max':cap})
        return {'source_sha256':sha(source),'source_bytes':source.stat().st_size,'kind':kind,'records':count,'key_bytes':key_bytes,'decoded_bytes':decoded,'largest_payload_bytes':maximum,'conservative_plan_charge_bytes':plan,'manifest_bytes':manifest.stat().st_size,'manifest_sha256':sha(manifest),'expected_sorted_records':expected,'packing_blockers':blockers,'metadata':metadata(source)},manifest,resources
    finally:db.close()
def verify_output(path,kind,expected,meta,scratch):
    got=digest(wire_rows(path,kind,scratch));require(got==expected,'Independent full output records differ from frozen stable sort oracle');a=attrs(path)
    for k,v in {'Title':meta['title'],'Description':meta['description'],'StyleSheet':meta['stylesheet'],'KeyCaseSensitive':'No','StripKey':'No',**meta['extra']}.items():require(a.get(k)==v,'Output metadata differs: '+k)
    return {'records':got,'file_bytes':path.stat().st_size,'file_sha256':sha(path),'metadata':a}
