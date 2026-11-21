"""Pin the shared publication runtime to the already qualified dependency union."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/publication-runtime/Cargo.toml'
LOCK='m2/publication-runtime/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/extraction-jobs/Cargo.lock').read_text())['package'];large=tomllib.loads((ROOT/'m2/large-io/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    expected=(identities(old)-{('studio-extraction-jobs','0.1.0',None,None)})|identities(large)|{('studio-publication-runtime','0.1.0',None,None)}
    if identities(new)!=expected:raise AssertionError('Publication runtime package identities changed')
    own=next(p for p in new if p['name']=='studio-publication-runtime')
    if set(own['dependencies'])!={'mdictlib','serde','serde_json','studio-indexed-engine','studio-large-io','studio-sessions','studio-stream-extract','tempfile'}:raise AssertionError('Publication runtime direct dependency inventory differs')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
