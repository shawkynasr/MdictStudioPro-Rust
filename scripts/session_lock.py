"""Add one local session facade; preserve all accepted registry identities."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/sessions/Cargo.toml'
LOCK='m2/sessions/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/indexed-engine/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    if identities(new)!=identities(old)|{('studio-sessions','0.1.0',None,None)}:raise AssertionError('Session graph changed package identities')
    own=next(p for p in new if p['name']=='studio-sessions')
    if set(own['dependencies'])!={'mdictlib','serde','serde_json','studio-indexed-engine','tempfile'}:raise AssertionError('Session direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
