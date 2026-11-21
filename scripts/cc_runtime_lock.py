"""Isolated CC-CEDICT facade; registry dependencies identical to accepted runtime."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/cc-runtime/Cargo.toml'
LOCK='m2/cc-runtime/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/converter-runtime/Cargo.lock').read_text())['package']
    new=tomllib.loads((ROOT/LOCK).read_text())['package']
    def ids(rows):return {(p['name'],p['version'],p.get('source'),p.get('checksum')) for p in rows}
    expected=ids(old)-{('studio-converter-runtime','0.1.0',None,None)}|{('studio-cc-runtime','0.1.0',None,None)}
    if ids(new)!=expected:raise AssertionError('CC-CEDICT runtime registry graph changed')
    previous=next(p for p in old if p['name']=='studio-converter-runtime')
    current=next(p for p in new if p['name']=='studio-cc-runtime')
    if current['dependencies']!=previous['dependencies']:raise AssertionError('CC-CEDICT direct dependencies changed')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
