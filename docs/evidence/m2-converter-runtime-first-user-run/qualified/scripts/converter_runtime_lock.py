"""Replace the qualified publication facade with one local converter facade."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/converter-runtime/Cargo.toml'
LOCK='m2/converter-runtime/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/publication-runtime/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def ids(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    expected=(ids(old)-{('studio-publication-runtime','0.1.0',None,None)})|{('studio-converter-runtime','0.1.0',None,None)}
    if ids(new)!=expected:raise AssertionError('Converter runtime registry identities changed')
    own=next(p for p in new if p['name']=='studio-converter-runtime')
    if set(own['dependencies'])!={'mdictlib','serde','serde_json','studio-application','studio-indexed-engine','studio-large-io','studio-sessions','studio-stream-extract','tempfile'}:raise AssertionError('Converter runtime direct dependencies differ')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
