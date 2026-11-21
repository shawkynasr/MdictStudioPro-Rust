"""Review source-bound real-reader results and retained independent M1 evidence.

User dictionaries/caches/output files are not attached. Full FNV stream agreement
and page payload comparison are assertions in the exact-source-bound Mac harness.
This reviewer cross-checks M1 corpus identities/counts/extents, resource hashes,
redacted page identities and controller/cleanup state. It does not reread MDX.
"""
import hashlib
import json
from pathlib import Path
import struct
from m2_sizing import ROOT
from m2_converter_runtime import admission

def require(ok,message):
    if not ok:raise AssertionError(message)
def review(r):
    require(r['status']=='m2_selected_real_reader_index_session_gate_passed_real_converters_and_closeout_pending' and r['stage']=='complete','Real reader batch incomplete');require(not r['M2_complete'] and not r['production_readiness'] and r['native_readers']=='NOT_REQUESTED','Do not expand scope')
    ids=['cc-cedict-mdx','cc-cedict-mdd','almaany-mdx','chinese-idioms-mdx'];require([c['case'] for c in r['checks']]==ids and len(r['steps'])==10 and all(s['returncode']==0 for s in r['steps']),'Command/case inventory differs');require(all(s['exists'] for s in r['selection']) and [s['id'] for s in r['selection']]==ids,'Selected input inventory differs')
    audit=json.loads((ROOT/'docs/evidence/real-corpus-local-audit/structural-audit.json').read_text());by_sha={a['sha256']:a for a in audit['cases']};total_records=total_pages=exchanges=resources=0;maximum=0;mdx_records=0
    for c in r['checks']:
        old=by_sha[c['source_sha256']];kind=c['kind'];scan=c['independent_scan'];require(c['status']=='real_scan_index_session_and_optional_extraction_passed' and c['lookup_policy']=='raw_exact','Case policy/status differs');require(old['status']=='structural_audit_passed' and c['file']==old['file'] and c['source_bytes']==old['size_bytes'] and scan['records']==old['records'],'Real corpus source identity/count differs from M1')
        unit=2 if old['header']['Encoding']=='UTF-16' else 1;require(scan['payload_bytes']==old['uncompressed_record_bytes']-(scan['records']*unit if kind=='mdx' else 0),'Decoded payload extent differs from independent M1 audit');require(len(scan['framed_fnv64'])==16 and len(c['oracle_framed_sha256'])==64,'Full stream digest shape differs')
        manifest=c['index_receipt']['manifest'];require(manifest==c['opened_manifest']['value'] and c['opened_manifest']['operation']=='opened' and manifest['source_sha256']==c['source_sha256'] and manifest['records']==scan['records'] and manifest['kind']==kind and manifest['policy']=='raw_exact','Cache/session source binding differs');require(c['index_receipt']['bytes']<=128*1024*1024 and c['index_receipt']['initial_runs']>0,'Index artifact caps differ');m=c['parser_memory'];require(m['locator']==0 and m['peak']<=m['budget']==64*1024*1024,'Parser budget/locator differs')
        require(len(c['pages'])==9,'Real page request inventory differs');require(all(0<n<=384*1024*1024 for n in c['peak_RSS_bytes'].values()),'RSS outside provisional envelope');maximum=max(maximum,*c['peak_RSS_bytes'].values());admission(c['opened_admission'],1,0);admission(c['final_admission'],0,0);f=c['final_admission'];require(f['shared']['active_operations']==0 and f['shared']['closed'] and f['readers']['closed'] and f['readers']['retained_reply_bytes']==f['readers']['retained_session_handles']==0,'Final reservations or retained objects leaked')
        for p in c['pages']:
            q=p['request'];v=p['reply']['value'];require(p['reply']['operation']=='page' and v['offset']==q['offset'] and v['basis'] in ['exact','none'] and len(v['rows'])<=q['limit'],'Redacted page identity/range differs');require(v['basis']==('exact' if v['total'] else 'none'),'Raw-exact basis differs');require([row['ordinal'] for row in v['rows']]==sorted(row['ordinal'] for row in v['rows']),'Physical duplicate order changed');require(all(set(row)=={'ordinal','key','payload_bytes','payload_sha256'} and row['key']==q['query'] and row['ordinal']<scan['records'] and len(row['payload_sha256'])==64 for row in v['rows']),'Page payload leaked or identity changed')
        extraction=c['extraction']
        if kind=='mdd':
            expected={};h=hashlib.sha256();by_key={x['path']:x for x in old['resources']}
            for i,row in enumerate(old['resources']):
                key=row['path'];raw=key.encode();digest=bytes.fromhex(row['sha256']);expected[key.replace('\\','/').removeprefix('/')]={'bytes':row['bytes'],'sha256':row['sha256']};h.update(struct.pack('<QQ',i,len(raw))+raw+struct.pack('<Q',row['bytes'])+digest)
            receipt=extraction['receipt'];require(extraction['files']==expected and receipt['framed_resources_sha256']==c['oracle_framed_sha256']==h.hexdigest(),'Extracted resource hashes/framing differ from retained M1 wire audit');require(receipt['profile']=='mdd-stream-extract-v1' and receipt['source_sha256']==c['source_sha256'] and receipt['resources']==scan['records'] and receipt['payload_bytes']==scan['payload_bytes'] and receipt['largest_resource_bytes']==max(x['bytes'] for x in old['resources']),'Real extraction receipt differs');require(receipt['locator_bytes']==receipt['materialized_record_limit']==0 and receipt['parser_peak_bytes']<=receipt['parser_budget_bytes']==64*1024*1024,'Extraction parser/materialization bounds differ');resources+=len(expected)
            for p in c['pages']:
                for row in p['reply']['value']['rows']:
                    known=by_key[row['key']];require(row['payload_bytes']==known['bytes'] and row['payload_sha256']==known['sha256'],'MDD page differs from M1 resource bytes')
        else:require(extraction is None,'Unexpected MDX resource extraction');mdx_records+=scan['records']
        jobs={};sessions=set();closed=set();pubjobs={};pages_taken=[];opened=0;extracted=0;admissions=[]
        for x in c['controller_transcript']:
            exchanges+=1;command=x['command'];reply=x['reply'];op=command['op'];require(set(reply)=={'ok'},'Unexpected real-runtime API failure');value=reply['ok']
            if op=='open':require(command['request']['policy']=='raw_exact' and command['request']['kind']==kind,'Wrong reader request');sessions.add(value['session']);jobs[value['job']]={'request':None,'state':None,'revision':0,'taken':False}
            elif op=='submit':require(command['session'] in sessions,'Unknown page session');jobs[value['job']]={'request':command['request'],'state':None,'revision':0,'taken':False}
            elif op=='job':
                job=jobs[command['job']];require(value['job_id']==command['job'] and value['revision']>=job['revision'],'Reader job/revision mismatch');job['revision']=value['revision'];require(value['state'] in ['queued','running','succeeded'],'Real reader failed');require(job['state']!='succeeded' or value['state']=='succeeded','Terminal reader regressed');job['state']=value['state'];require(value['error'] is None,'Unexpected reader error')
            elif op=='take':
                job=jobs[command['job']];require(job['state']=='succeeded' and not job['taken'],'Wrong/repeated reader result');job['taken']=True
                if job['request'] is None:require(value==c['opened_manifest'],'Opened manifest differs');opened+=1
                else:require(value==c['pages'][len(pages_taken)]['reply'] and job['request']==c['pages'][len(pages_taken)]['request'],'Page transcript differs from summary');pages_taken.append(value)
            elif op=='forget':require(jobs.pop(command['job'])['taken'],'Reader result not collected')
            elif op=='publish':require(kind=='mdd' and command['request']['kind']=='extraction','Unexpected publication');pubjobs[value['job']]={'state':None,'taken':False,'revision':0}
            elif op=='publish_job':
                job=pubjobs[command['job']];require(value['operation']=='extract_mdd' and value['job_id']==command['job'] and value['revision']>=job['revision'],'Extraction job identity/revision differs');job['revision']=value['revision'];require(value['state'] in ['queued','running','succeeded'] and value['error'] is None,'Extraction failed');require(job['state']!='succeeded' or value['state']=='succeeded','Terminal extraction changed');job['state']=value['state']
            elif op=='publish_take':
                job=pubjobs[command['job']]
                if value is None:require(job['taken'],'Extraction receipt disappeared')
                else:require(job['state']=='succeeded' and not job['taken'] and value=={'kind':'extraction','receipt':extraction['receipt']},'Wrong/repeated extraction result');job['taken']=True;extracted+=1
            elif op=='publish_cancel':require(value=='already_finished' and pubjobs[command['job']]['state']=='succeeded','Late cancel changed extraction')
            elif op=='publish_forget':require(pubjobs.pop(command['job'])['taken'],'Extraction result not collected')
            elif op=='wait_closed':require(value['closed'],'Close not acknowledged');closed.add(command['session'])
            elif op=='release':require(command['session'] in closed,'Released before managed barrier');sessions.remove(command['session'])
            elif op=='admission':admission(value);admissions.append(value)
            elif op not in ['close','shutdown']:raise AssertionError('Unexpected real controller command '+op)
        require(opened==1 and len(pages_taken)==9 and extracted==int(kind=='mdd') and not jobs and not pubjobs and not sessions,'Real-runtime transfer/cleanup totals differ');require(admissions[0]==c['opened_admission'] and admissions[-1]==c['final_admission'],'Admission summary binding differs');total_records+=scan['records'];total_pages+=len(pages_taken)
    require(total_records==296127 and mdx_records==296110 and resources==17 and total_pages==36 and exchanges==346,'Real matrix totals differ')
    return {'MDX_entries':mdx_records,'MDD_resources':resources,'total_records':total_records,'lookup_pages_reviewed':total_pages,'controller_exchanges':exchanges,'resource_hashes_recomputed_from_M1_audit':resources,'max_observed_RSS_bytes':maximum,'review':'M1 corpus identities/extents, resource hashes, redacted page identities and controller ledgers cross-checked; full FNV agreement and body comparisons represented by exact-source-bound Mac harness; actual user files not attached'}
if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
