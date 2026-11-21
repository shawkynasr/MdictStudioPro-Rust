"""Same accepted graph; indexed engine moves from dev to runtime dependency."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/real-publication-runtime/Cargo.toml'
LOCK='m2/real-publication-runtime/Cargo.lock'
def check_lock():
    before=tomllib.loads((ROOT/'m2/full-converter-runtime/Cargo.lock').read_text())['package'];after=tomllib.loads((ROOT/LOCK).read_text())['package']
    expected=[{**p,'name':'studio-real-publication-runtime'} if p['name']=='studio-full-converter-runtime' else p for p in before]
    if after!=expected:raise AssertionError('Real publication graph differs from renamed accepted facade')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in after]
