"""Independent disk-index workspace, with previously accepted registry versions."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/indexed-engine/Cargo.toml'
LOCK='m2/indexed-engine/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/bounded-engine/Cargo.lock').read_text())['package']
    new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    expected=identities(old)-{('studio-bounded-engine','0.1.0',None,None)}|{('studio-indexed-engine','0.1.0',None,None)}
    if identities(new)!=expected:raise AssertionError('Indexed workspace changed accepted dependency identities')
    own=next(p for p in new if p['name']=='studio-indexed-engine')
    seed=next(p for p in old if p['name']=='studio-bounded-engine')
    if own['dependencies']!=seed['dependencies']:raise AssertionError('Indexed direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
