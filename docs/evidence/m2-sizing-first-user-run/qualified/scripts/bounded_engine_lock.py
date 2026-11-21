"""Add one local sizing workspace; keep all accepted registry identities."""
import json
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/bounded-engine/Cargo.toml'
LOCK='m2/bounded-engine/Cargo.lock'
DEPENDENCIES=['mdictlib','quick-xml','serde','serde_json','studio-core','studio-v2-import','tempfile']
def render():
    old=(ROOT/'m2/v2-import/Cargo.lock').read_text()
    return old.rstrip()+'\n\n[[package]]\nname = "studio-bounded-engine"\nversion = "0.1.0"\ndependencies = [\n'+''.join(' '+json.dumps(d)+',\n' for d in DEPENDENCIES)+']\n'
def check_lock():
    old=tomllib.loads((ROOT/'m2/v2-import/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identity(rows):return {(r['name'],r['version'],r.get('source'),r.get('checksum')) for r in rows}
    if identity(new)!=identity(old)|{('studio-bounded-engine','0.1.0',None,None)}:raise AssertionError('Sizing workspace changed package identities')
    own=next(r for r in new if r['name']=='studio-bounded-engine')
    if set(own['dependencies'])!=set(DEPENDENCIES):raise AssertionError('Sizing workspace direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
if __name__=='__main__':print(render(),end='')
