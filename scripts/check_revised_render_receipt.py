"""Review source-bound full grouped output parity and publication boundaries.

Actual native TXT/private files remain on the Mac. Per-record comparison, strict
reopen and cleanup are assertions of the exact source-bound harness. This reviewer
binds every case, output summary and full normalized digest to independent Python
references, and independently recomputes the group plan from the complete source.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
from openpyxl import load_workbook
from m2_sizing import ROOT,sha,require
from m2_revised_render import REFERENCE,RSS_TARGET,protected_sources,fingerprints
from revised_render_lock import LOCK,check_lock
from revised_render_oracle import records,record_summary
from moe_fixtures import load_plugins
from xlsx_spool_oracle import inspect

def group_stats(source,sheet=None):
    spec=importlib.util.spec_from_file_location('review_group_normalizer',ROOT/'baseline/legacy/excel_utils.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    book=load_workbook(source,read_only=True,data_only=True);groups={};rows=skipped=0
    try:
        worksheet=book[sheet] if sheet else book.active;iterator=worksheet.iter_rows(values_only=True);headers=[str(v).strip() if v is not None else f'col_{i}' for i,v in enumerate(next(iterator))]
        for raw in iterator:
            if raw is None or all(v is None for v in raw):continue
            rows+=1;row={h:module._cell_to_str(raw[i] if i<len(raw) else None) for i,h in enumerate(headers)};head=row.get('字詞名','').strip()
            if not head:skipped+=1;continue
            size=sum(len(k.encode())+len(v.encode()) for k,v in row.items());entry=groups.setdefault(head,[0,0]);entry[0]+=1;entry[1]+=size
    finally:book.close()
    return {'source_sha256':sha(source),'input_rows':rows,'groups':len(groups),'skipped_rows':skipped,'index_charge_bytes':65536+sum(256+2*len(h.encode()) for h in groups)+64*(rows-skipped),'largest_group_rows':max(v[0] for v in groups.values()),'largest_group_input_bytes':max(v[1] for v in groups.values())}

def generate_oracles(full_source):
    ref=json.loads((ROOT/REFERENCE).read_text());require(sha(full_source)==ref['archive']['source_sha256'],'Independent source differs')
    for name,h in ref['legacy_oracle_sha256'].items():require(sha(ROOT/name)==h,'Captured oracle code changed')
    fixture=ROOT/'m2/revised-render/tests/fixtures/groups.xlsx';small={}
    with tempfile.TemporaryDirectory() as d:
        for kind in ['moe_revised','moe_revised_wfg']:
            output=Path(d)/(kind+'.txt');load_plugins()[kind].convert(str(fixture),str(output),'utf-8',lambda _:None,lambda _:None);aliases=sum(e['text'].startswith('@@@LINK=') for e in records(output));digest=record_summary(output,kind,True)
            small[kind]={'normalized_record_digest':digest,'file_bytes':output.stat().st_size,'raw_python_output_sha256':sha(output),'entries':digest['records'],'primary_entries':digest['records']-aliases,'alias_redirects':aliases}
    return {'method':'Fresh captured Python small converters; full source group plan recomputed with original normalization helper, without retaining definitions','small':small,'small_group_plan':group_stats(fixture),'small_rows':inspect(fixture),'full_group_plan':group_stats(full_source,ref['worksheet'])}

def review(report,oracles):
    ref=json.loads((ROOT/REFERENCE).read_text());kinds=['moe_revised','moe_revised_wfg'];fixture=ROOT/'m2/revised-render/tests/fixtures/groups.xlsx'
    require(report['status']=='full_Revised_and_WFG_grouped_TXT_publication_passed_application_integration_pending' and report['stage']=='complete','Grouped rendering gate incomplete')
    require(not report['M2_complete'] and not report['application_background_integration_qualified'] and not report['RSS_is_OS_limit'] and report['native_readers']=='NOT_REQUESTED','Standalone rendering scope expanded')
    require(report['build_profile']=='release_for_process_cases_debug_for_tests' and report['RSS_observation_target_bytes']==RSS_TARGET,'Build/memory scope differs')
    require(report['steps']==[{'name':'grouped-render-tests','returncode':0},{'name':'build-release-grouped-render','returncode':0}],'Grouped native command receipts differ')
    require(report['protected_source_sha256']==protected_sources() and report['source_sha256']==fingerprints(),'Grouped source identity differs')
    require(report['legacy_oracle_sha256']==ref['legacy_oracle_sha256'] and report['dependency_packages']==check_lock() and report['dependency_lock_sha256']==sha(ROOT/LOCK),'Oracle/registry identity differs')
    for name,h in ref['legacy_oracle_sha256'].items():require(sha(ROOT/name)==h,'Captured Python changed')
    specs=[]
    def add(name,kind,full=False,code=None,**options):specs.append((name,kind,full,code,options))
    for kind in kinds:
        add('small-'+kind,kind)
        for phase in ['index_rows','render_group','append_record','verify_output','before_publish']:add(kind+'-cancel-'+phase,kind,code='cancelled',cancel_phase=phase)
        add(kind+'-late-cancel',kind,cancel_phase='published')
        for name,limit in [('group-rows',{'group_rows':1}),('index-charge',{'index_charge_bytes':1}),('entries',{'entries':1}),('file-bytes',{'output_bytes':4})]:add(kind+'-lower-'+name,kind,code='limit_exceeded',tighten=limit)
    add('unknown-converter','moe_mini',code='invalid_input');add('cannot-grow-entries',kinds[0],code='invalid_input',tighten={'entries':200001});add('cannot-grow-reader',kinds[0],code='invalid_input',reader_tighten={'rows':200001});add('missing-sheet',kinds[0],code='sheet_not_found',worksheet='missing')
    for kind in kinds:add('full-'+kind,kind,True);add(kind+'-existing-output',kind,True,'destination_exists')
    checks=report['checks'];require(len(checks)==30 and [c['case'] for c in checks]==[s[0] for s in specs],'Grouped process case matrix differs')
    row_ref=json.loads((ROOT/'docs/evidence/m2-xlsx-spool-user-run/m2-xlsx-spool-report.json').read_text())['checks'][-1]['reply']['receipt'];successful={};published=failures=compared=0
    require(oracles['full_group_plan']['source_sha256']==ref['archive']['source_sha256'] and oracles['small_group_plan']['source_sha256']==sha(fixture),'Independent group-plan sources differ')
    for c,(name,kind,full,code,options) in zip(checks,specs):
        require(0<c['peak_RSS_bytes']<=RSS_TARGET,'Native RSS outside observation envelope');request=c['request'];options=dict(options);worksheet=options.pop('worksheet',ref['worksheet'] if full else None)
        require(request=={'source':request['source'],'destination':request['destination'],'converter':kind,'worksheet':worksheet,**options},'Unexpected request options')
        require(Path(request['source']).name==(ref['archive']['member'] if full else 'groups.xlsx'),'Wrong source file')
        require(Path(request['destination']).name==(('full-'+kind) if code=='destination_exists' else name)+'.txt','Wrong output file')
        reply=c['reply']
        if code:
            failures+=1;require(c['returncode']==1 and reply['status']=='failed' and reply['error']['code']==code and 'receipt' not in reply,'Wrong publication refusal')
            if code=='destination_exists':require(c['existing_output_sha256_preserved']==successful[kind]['output_sha256'],'Existing output changed')
            continue
        published+=1;receipt=reply['receipt'];expected=ref['cases'][kind] if full else oracles['small'][kind];group=oracles['full_group_plan'] if full else oracles['small_group_plan']
        require(c['returncode']==0 and reply['status']=='succeeded' and receipt['profile']=='moe-grouped-disk-rows-txt-v1' and receipt['converter']==kind,'Wrong grouped success profile')
        require(reply['late_cancel_observed']==(options.get('cancel_phase')=='published'),'Late cancellation behavior differs')
        require(set(reply['progress_phases'])=={'begin','snapshot','package_preflight','shared_strings','normalize_rows','verify_rows','rows_complete','index_rows','render_group','append_record','verify_output','before_publish','published'},'Missing render/verification/publication phase')
        for key in ['source_sha256','input_rows','groups','skipped_rows','index_charge_bytes','largest_group_rows','largest_group_input_bytes']:require(receipt[key]==group[key],'Group source/accounting differs: '+key)
        require(receipt['entries']==expected['entries'] and receipt['primary_entries']==expected['primary_entries']==receipt['groups'] and receipt['alias_redirects']==expected['alias_redirects'] and receipt['entries']==receipt['primary_entries']+receipt['alias_redirects'],'Primary/alias counts differ')
        require(c['normalized_record_digest']==expected['normalized_record_digest'] and c['records_compared']==expected['entries'],'Complete normalized record comparison differs')
        raw=c['raw_record_digest'];require(raw=={'records':receipt['entries'],'key_bytes':receipt['key_bytes'],'payload_bytes':receipt['body_bytes'],'framed_records_sha256':receipt['framed_records_sha256']},'Raw receipt/digest differs')
        require(receipt['key_bytes']==expected['normalized_record_digest']['key_bytes'] and receipt['body_bytes']==expected['normalized_record_digest']['payload_bytes'] and receipt['decoded_bytes']==receipt['key_bytes']+receipt['body_bytes'],'Output key/body byte accounting differs')
        require(receipt['file_bytes']==expected['file_bytes']==receipt['decoded_bytes']+6*receipt['entries'] and receipt['file_sha256']==c['output_sha256'],'Canonical file framing/hash differs')
        require(c['raw_python_bytes_equal']==(c['output_sha256']==c['python_output_sha256']),'Raw versus normalized equality misreported')
        if kind=='moe_revised_wfg':require(c['raw_python_bytes_equal'] and c['output_sha256']==expected['raw_python_output_sha256'],'WFG raw bytes differ from original reference')
        require(receipt['index_charge_bytes']<=64*1024*1024 and receipt['largest_group_rows']<=4096 and receipt['largest_group_input_bytes']<=16*1024*1024 and receipt['temporary_file_peak_bytes']<=512*1024*1024,'Group/private-file limits exceeded')
        if full:require(receipt['row_source']==row_ref,'Full row spool differs from accepted reader');successful[kind]=c
        else:require(all(receipt['row_source'][k]==v for k,v in oracles['small_rows'].items()),'Small source rows differ')
        require(receipt['temporary_file_peak_bytes']==receipt['row_source']['temporary_bytes']+receipt['file_bytes'],'Combined private-file extent differs');compared+=c['records_compared']
    require(published==6 and failures==24 and set(successful)==set(kinds),'Success/refusal totals differ')
    return {'process_cases':30,'successful_publications':6,'expected_refusals':24,'full_Revised_entries':162636,'full_WFG_entries':161182,'records_compared':compared,'full_Revised_RSS_bytes':successful[kinds[0]]['peak_RSS_bytes'],'full_WFG_RSS_bytes':successful[kinds[1]]['peak_RSS_bytes'],'max_observed_RSS_bytes':max(c['peak_RSS_bytes'] for c in checks),'scope':'Complete normalized digests match independent local original Python; WFG raw bytes also exact. Small oracles and full source group plan independently recomputed. Native record/reopen comparisons, cleanup and no-clobber checks represented by source-bound Mac harness; actual native TXT files not attached, no local Rust execution. Standalone converters only; background/admission integration and M2 closeout pending.'}
if __name__=='__main__':
    import sys
    if sys.argv[1]=='--oracles':print(json.dumps(generate_oracles(Path(sys.argv[2])),indent=2))
    else:print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text())),indent=2))
