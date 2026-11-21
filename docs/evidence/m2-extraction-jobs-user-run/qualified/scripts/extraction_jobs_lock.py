"""Add the extraction facade to the accepted session and extractor graphs."""
from pathlib import Path
import tomllib
ROOT=Path(__file__).resolve().parents[1]
MANIFEST='m2/extraction-jobs/Cargo.toml'
LOCK='m2/extraction-jobs/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/sessions/Cargo.lock').read_text())['package'];extract=tomllib.loads((ROOT/'m2/stream-extract/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def identities(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    if identities(new)!=identities(old)|identities(extract)|{('studio-extraction-jobs','0.1.0',None,None)}:raise AssertionError('Shared-admission dependency identities changed')
    own=next(p for p in new if p['name']=='studio-extraction-jobs')
    if set(own['dependencies'])!={'mdictlib','serde','serde_json','studio-indexed-engine','studio-sessions','studio-stream-extract','tempfile'}:raise AssertionError('Facade direct dependency inventory differs')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
