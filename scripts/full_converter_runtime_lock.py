"""Compose accepted graphs without changing registry identities or dependency edges."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/full-converter-runtime/Cargo.toml'
LOCK='m2/full-converter-runtime/Cargo.lock'
def check_lock():
    def graph(path):return {(p['name'],p['version']):p for p in tomllib.loads((ROOT/path).read_text())['package']}
    old=graph('m2/cc-runtime/Cargo.lock');grouped=graph('m2/revised-render/Cargo.lock');expected=dict(old)
    for key,p in grouped.items():
        if key in expected and expected[key]!=p:raise AssertionError('Accepted dependency edges conflict: '+str(key))
        expected[key]=p
    root=expected.pop(('studio-cc-runtime','0.1.0'));root={**root,'name':'studio-full-converter-runtime','dependencies':sorted(root['dependencies']+['studio-revised-render','studio-xlsx','studio-xlsx-spool'])};expected[(root['name'],root['version'])]=root
    actual=graph(LOCK)
    if actual!=expected:raise AssertionError('Full runtime graph differs from exact accepted union')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in actual.values()]
