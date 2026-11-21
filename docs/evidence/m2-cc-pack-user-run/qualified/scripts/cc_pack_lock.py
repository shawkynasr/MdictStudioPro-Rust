"""Add one local bounded packer to the unchanged accepted 68-package graph."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/cc-pack-runtime/Cargo.toml'
LOCK='m2/cc-pack-runtime/Cargo.lock'
def check_lock():
    def graph(path):return {(p['name'],p['version']):p for p in tomllib.loads((ROOT/path).read_text())['package']}
    old=graph('m2/real-publication-runtime/Cargo.lock');expected=dict(old);root=expected.pop(('studio-real-publication-runtime','0.1.0'));root={**root,'name':'studio-cc-pack-runtime','dependencies':sorted(root['dependencies']+['studio-cc-pack-io'])};expected[(root['name'],root['version'])]=root
    base=old[('studio-large-io','0.1.0')];expected[('studio-cc-pack-io','0.1.0')]={**base,'name':'studio-cc-pack-io','dependencies':sorted(base['dependencies']+['miniz_oxide','studio-large-io'])}
    actual=graph(LOCK)
    # Dependency array ordering is immaterial to identity/edge verification.
    def normalized(g):return {k:{**p,**({'dependencies':sorted(p['dependencies'])} if 'dependencies' in p else {})} for k,p in g.items()}
    if normalized(actual)!=normalized(expected):raise AssertionError('CC pack dependency graph differs from exact accepted graph plus local packer')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in actual.values()]
