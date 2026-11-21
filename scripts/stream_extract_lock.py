"""Independent streaming extractor with accepted dependency versions."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/stream-extract/Cargo.toml'
LOCK='m2/stream-extract/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/v2-import/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    if identities(new)!=identities(old)|{('studio-stream-extract','0.1.0',None,None)}:raise AssertionError('Extraction dependency identities changed')
    own=next(p for p in new if p['name']=='studio-stream-extract')
    if set(own['dependencies'])!={'libc','mdictlib','quick-xml','serde','serde_json','studio-core','studio-v2-import','tempfile'}:raise AssertionError('Extraction direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
