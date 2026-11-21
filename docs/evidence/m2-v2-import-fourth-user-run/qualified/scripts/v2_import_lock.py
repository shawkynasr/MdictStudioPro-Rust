"""Seed the isolated import graph from the accepted application graph."""
import copy
import json
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/v2-import/Cargo.toml'
LOCK='m2/v2-import/Cargo.lock'
def seed_packages():
    rows=copy.deepcopy(tomllib.loads((ROOT/'m2/application/Cargo.lock').read_text())['package'])
    # Application is a dependency here; its test-only tempfile edge is not
    # active. The same tempfile package is still a core/import dependency.
    app=next(p for p in rows if p['name']=='studio-application');app['dependencies']=[d for d in app['dependencies'] if d!='tempfile']
    rows.append({'name':'studio-v2-import','version':'0.1.0','dependencies':['mdictlib','quick-xml','serde','serde_json','studio-application','studio-core','tempfile']})
    return sorted(rows,key=lambda p:(p['name'],p['version']))
def render():
    out=['# Isolated v2 import seed; registry identities match the accepted application lock.','version = 4','']
    for row in seed_packages():
        out.append('[[package]]')
        for name in ['name','version','source','checksum']:
            if name in row:out.append(name+' = '+json.dumps(row[name]))
        if 'dependencies' in row:out+=['dependencies = [']+[' '+json.dumps(d)+',' for d in row['dependencies']]+[']']
        out.append('')
    return '\n'.join(out)
def check_lock():
    expected=tomllib.loads((ROOT/'m2/application/Cargo.lock').read_text())['package'];rows=tomllib.loads((ROOT/LOCK).read_text())['package']
    def registry(items):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in items if 'source' in p}
    if registry(expected)!=registry(rows):raise AssertionError('Import workspace changed registry versions/checksums')
    if {(p['name'],p['version']) for p in rows}!={(p['name'],p['version']) for p in expected}|{('studio-v2-import','0.1.0')}:raise AssertionError('Unexpected import package inventory')
    importer=next(p for p in rows if p['name']=='studio-v2-import')
    if set(importer['dependencies'])!=set(seed_packages()[[p['name'] for p in seed_packages()].index('studio-v2-import')]['dependencies']):raise AssertionError('Importer direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in rows]
if __name__=='__main__':print(render(),end='')
