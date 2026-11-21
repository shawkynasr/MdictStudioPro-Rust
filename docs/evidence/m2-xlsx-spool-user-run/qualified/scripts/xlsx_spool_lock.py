"""Exact reachable dependency subset of the accepted CC runtime graph."""
import tomllib
from m2_sizing import ROOT
MANIFEST='m2/xlsx-spool/Cargo.toml'
LOCK='m2/xlsx-spool/Cargo.lock'
DIRECT=['quick-xml','serde','serde_json','studio-xlsx','tempfile','zip']
def check_lock():
    old=tomllib.loads((ROOT/'m2/cc-runtime/Cargo.lock').read_text())['package'];new=tomllib.loads((ROOT/LOCK).read_text())['package']
    seen={};pending=list(DIRECT)
    while pending:
        dep=pending.pop().split();matches=[p for p in old if p['name']==dep[0] and (len(dep)==1 or p['version']==dep[1])]
        if len(matches)!=1:raise AssertionError('Ambiguous dependency identity')
        p=matches[0];key=p['name'],p['version']
        if key in seen:continue
        seen[key]=p;pending.extend(p.get('dependencies',[]))
    expected=list(seen.values())+[{'name':'studio-xlsx-spool','version':'0.1.0','dependencies':DIRECT}]
    def keyed(rows):return {(p['name'],p['version']):p for p in rows}
    if keyed(expected)!=keyed(new):raise AssertionError('Row-spool dependency graph differs from exact qualified subset')
    return [{'name':p['name'],'version':p['version'],'checksum':p.get('checksum')} for p in new]
