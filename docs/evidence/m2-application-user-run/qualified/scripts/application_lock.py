"""Build a joint lock seed solely from the two already qualified lock graphs."""
import json
from pathlib import Path
import tomllib

ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/application/Cargo.toml'
LOCK='m2/application/Cargo.lock'

def packages():
    graphs=[tomllib.loads((ROOT/p).read_text())['package'] for p in ['m2/Cargo.lock','m2/xlsx-reader/Cargo.lock']]
    versions={}
    for graph in graphs:
        for p in graph:versions.setdefault(p['name'],set()).add(p['version'])
    merged={}
    for graph in graphs:
        for original in graph:
            p=dict(original)
            if p['name']=='studio-cli':continue
            deps=[]
            for dep in p.get('dependencies',[]):
                parts=dep.split();name=parts[0]
                if len(parts)==1 and len(versions[name])>1:
                    found=[v['version'] for v in graph if v['name']==name]
                    if len(found)!=1:raise AssertionError(f'Ambiguous dependency in original graph: {dep}')
                    dep=f'{name} {found[0]}'
                deps.append(dep)
            if deps:p['dependencies']=deps
            key=(p['name'],p['version'])
            if key in merged and merged[key]!=p:raise AssertionError(f'Qualified dependency conflict: {key}')
            merged[key]=p
    merged['studio-application','0.1.0']={'name':'studio-application','version':'0.1.0','dependencies':['serde','serde_json','studio-core','studio-xlsx','tempfile']}
    return [merged[k] for k in sorted(merged)]

def render():
    out=['# Joint lock seed from qualified core and XLSX graphs; verify with Cargo --locked.','version = 4','']
    for p in packages():
        assert set(p)<=set(['name','version','source','checksum','dependencies'])
        out.append('[[package]]')
        for key in ['name','version','source','checksum']:
            if key in p:out.append(key+' = '+json.dumps(p[key]))
        if 'dependencies' in p:
            out.append('dependencies = [');out.extend(' '+json.dumps(d)+',' for d in p['dependencies']);out.append(']')
        out.append('')
    return '\n'.join(out)

def check_lock():
    actual=tomllib.loads((ROOT/LOCK).read_text())['package']
    if actual!=packages():raise AssertionError('Application dependency graph changed beyond qualified union')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in actual]

if __name__=='__main__':print(render(),end='')
