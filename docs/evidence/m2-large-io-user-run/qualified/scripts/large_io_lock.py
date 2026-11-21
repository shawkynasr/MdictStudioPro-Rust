"""The large IO workspace adds one local crate to the qualified import graph."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/large-io/Cargo.toml'
LOCK='m2/large-io/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/v2-import/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    if identities(new)!=identities(old)|{('studio-large-io','0.1.0',None,None)}:raise AssertionError('Large IO registry identities changed')
    own=next(p for p in new if p['name']=='studio-large-io')
    if set(own['dependencies'])!={'libc','mdictlib','quick-xml','serde','serde_json','studio-application','studio-core','studio-v2-import','tempfile'}:raise AssertionError('Large IO direct dependency inventory differs')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
