"""Review the attached source-bound disk-index receipt without executing Rust."""
import json
from pathlib import Path
from index_fixtures import SPECIAL,expected_page
from bounded_fixtures import rows as generated_rows

def require(condition,message):
    if not condition:raise AssertionError(message)

def review(report):
    require(report['status']=='m2_disk_index_paged_lookup_passed_larger_integration_pending' and report['stage']=='complete','Index batch did not complete')
    require(not report['M2_complete'] and not report['production_readiness'] and report['native_readers']=='NOT_REQUESTED','Do not expand index acceptance scope')
    require(report['unicode_version']=='16.0.0','Wrong independent normalization oracle version')
    steps=report['steps'];checks=report['checks'];step={s['name']:s for s in steps}
    require(len(steps)==58 and len(step)==58 and len(checks)==55 and len({c['case'] for c in checks})==55,'Index inventory differs')
    require([(s['name'],s['returncode']) for s in steps[:3]]==[('refresh-index-artifacts',0),('index-tests',0),('build-index-cli',0)],'Rust command receipt differs')
    published={c['case']:c for c in checks if c['status']=='published'};pages=[c for c in checks if c['status']=='pages_passed'];refused={c['case']:c for c in checks if c['status']=='expected_refusal'}
    require(len(published)==12 and len(pages)==20 and len(refused)==23,'Index outcome counts differ')
    for c in checks:
        s=step[c['case']];require(s['returncode']==(1 if c['status']=='expected_refusal' else 0),'Case exit code differs')
        require(0<c['peak_RSS_bytes']==s['peak_RSS_bytes']<=384*1024*1024,'RSS observation receipt differs')
    expected_refusals={**{n:'integrity' for n in ['wrong-policy','stale-same-mtime','bad-checksum','bad-truncated','bad-revision','bad-ordinal','bad-token','bad-extent','bad-duplicate-ordinal','empty-normalized']},**{n:'limit_exceeded' for n in ['page-count-cap','page-byte-cap','run-byte-cap']},'mdd-policy':'invalid_input','empty-normalized-query':'invalid_input','existing-destination':'destination_exists','missing-cache':'io',**{'cancel-'+p:'cancelled' for p in ['index_runs','index_merge','index_verify','index_publish','index_snapshot','index_lookup']}}
    require({n:c['error']['code'] for n,c in refused.items()}==expected_refusals,'Typed refusal inventory differs')
    for name,c in published.items():
        a=c['actual'];r=a['receipt'];m=r['manifest'];require(a['status']=='published' and m['source_sha256']==c['source_sha256'],'Build/source binding differs')
        require(a['revision']==m['revision']=='studio-disk-index-v1-frozen16' and m['engine_revision']=='mdictlib-0.2.8-studio-sort-v6','Build revisions differ')
        require(m['casing_sha256']=='f69d2e55d6b8c8d5fe33f764cc47b829bccc6d73aaff1791e1216328a1c24071','Frozen table binding differs')
        require(4096<r['bytes']<=128*1024*1024 and r['initial_runs']>=2,'Build size/run count differs')
    page_count=0;large_rows={k:list(generated_rows(65536,k)) for k in ['mdx','mdd']}
    for c in pages:
        name=c['case'];a=c['actual'];strip=False;sensitive=False;kind='mdx';policy='header_ascii_v1'
        if name.startswith(('utf8-','utf16-')):
            prefix=name.removesuffix('-lookup').removesuffix('-reopen-pages');parts=prefix.split('-');strip=parts[1]=='strip1';sensitive=parts[2]=='case1';rows=SPECIAL+[('duplicate',f'body-{i}') for i in range(400)];build=prefix+'-build'
            if name.endswith('-reopen-pages'):queries=[('duplicate',o,128) for o in [0,128,256,384,400,2**64-1]]+[('duplicate',0,0)]
            else:queries=[(q,0,4) for q in ['apple','Apple','APPLE','a?b','A B','ΣΟΣ','σος','i\u0307','مرحبا','字','𠀀','\U00010d70','alias','absent']]
        elif name=='raw-query':
            rows=SPECIAL+[('duplicate',f'body-{i}') for i in range(400)];build='raw-build';policy='raw_exact';queries=[('APPLE',0,10)]
        elif name in ['larger-mdx-query','larger-mdd-query']:
            kind='mdd' if 'mdd' in name else 'mdx';rows=large_rows[kind];build=name.replace('-query','-build');policy='raw_exact' if kind=='mdd' else 'header_ascii_v1';queries=[(q,0,3) for q in ['row00000000','ROW00000000','字','𠀀','absent']]
        elif name=='mdd-query':
            rows=list(generated_rows(100,'mdd'));kind='mdd';policy='raw_exact';build='mdd-build';queries=[('𠀀',0,2)]
        else:raise AssertionError('Unexpected page case: '+name)
        b=published[build];require(a['manifest']==b['actual']['receipt']['manifest'] and c['source_sha256']==b['source_sha256'] and c['artifact_sha256']==b['artifact_sha256'],'Reopened cache/source identity differs')
        require(a['manifest']['policy']==policy and a['manifest']['kind']==kind and a['manifest']['case_sensitive']==sensitive and a['manifest']['strip_key']==strip and a['manifest']['records']==len(rows),'Fixture policy/count differs')
        require(a['scan']['records']==len(rows) and a['memory']['locator']==0 and a['memory']['peak']<=a['memory']['budget']==64*1024*1024,'Reader count/locator/accounting differs')
        require(len(a['results'])==len(queries),'Page response count differs')
        for result,(query,offset,limit) in zip(a['results'],queries):
            # This single new Unicode16 scalar is explicit in the fixture.
            # Older local Python versions lack that lowercase mapping; keep the
            # expected row literal instead of using their evolving Unicode data.
            if query=='\U00010d70':
                found=[] if sensitive else [{'ordinal':12,'key':'\U00010d50','text':'Unicode16'}]
                expected={'basis':'normalized' if found else 'none','total':len(found),'offset':0,'next_offset':None,'rows':found}
            else:expected=expected_page(rows,query,offset,limit,policy,sensitive,strip,kind)
            require(result['query']==query and result['page']==expected,f'Fixture page comparison failed: {name} {query!r} {offset}')
            require(isinstance(result['lookup_us'],int) and result['lookup_us']>=0,'Missing page timing observation');page_count+=1
    require(page_count==180,'Expected 180 page results')
    maximum=max(c['peak_RSS_bytes'] for c in checks);require(maximum==6189056,'Maximum RSS receipt differs')
    return {'builds':12,'query_runs':20,'page_results':180,'expected_refusals':23,'max_observed_RSS_bytes':maximum,'review':'exact embedded pages independently recomputed; Rust not executed by this reviewer'}

if __name__=='__main__':
    import sys
    report=json.loads(Path(sys.argv[1]).read_text());print(json.dumps(review(report),indent=2))
