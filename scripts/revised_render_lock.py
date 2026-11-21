"""Add one local grouped renderer to the exact accepted disk-row graph."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/revised-render/Cargo.toml'
LOCK='m2/revised-render/Cargo.lock'
def check_lock():
    old=tomllib.loads((ROOT/'m2/xlsx-spool/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    expected=[{**p,'dependencies':[d for d in p.get('dependencies',[]) if d!='studio-xlsx']} if p['name']=='studio-xlsx-spool' else p for p in old]+[{'name':'studio-revised-render','version':'0.1.0','dependencies':['serde','serde_json','studio-xlsx','studio-xlsx-spool','tempfile']}]
    def keyed(rows):return {(p['name'],p['version']):p for p in rows}
    if keyed(new)!=keyed(expected):raise AssertionError('Grouped render graph differs from accepted dependency subset plus local facade')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
