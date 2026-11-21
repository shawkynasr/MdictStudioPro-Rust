"""Review source-bound row receipts, independent Python rows and disk sizes.

Native row/spool files are private. Reopen parity, cleanup and source preservation
are assertions of the exact Mac harness. This review binds every case to that
source, checks its full digest against the independent complete Python reference,
and cross-checks full source/shared-string/JSONL extents independently.
"""
import importlib.util
import json
from pathlib import Path
import zipfile
from m2_sizing import ROOT,sha,require
from m2_xlsx_spool import REFERENCE,RSS_TARGET,protected_sources,fingerprints
from xlsx_spool_oracle import inspect,RowDigest
from xlsx_spool_lock import LOCK,check_lock

def generate_oracles(source):
    from openpyxl import load_workbook
    from openpyxl.reader.strings import read_string_table
    reference=json.loads((ROOT/REFERENCE).read_text());require(sha(source)==reference['archive']['source_sha256'],'Independent source differs')
    for name,h in reference['legacy_normalizer_sha256'].items():require(sha(ROOT/name)==h,'Original normalizer changed')
    with zipfile.ZipFile(source) as z:
        with z.open('xl/sharedStrings.xml') as stream:strings=read_string_table(stream)
        shared_count=len(strings);shared_bytes=sum(len(value.encode('utf-8')) for value in strings)
    del strings
    spec=importlib.util.spec_from_file_location('review_original_normalizer',ROOT/'baseline/legacy/excel_utils.py');normalizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(normalizer)
    book=load_workbook(source,read_only=True,data_only=True);spool_bytes=0;digest=RowDigest()
    try:
        sheet=book[reference['expected']['worksheet']];rows=sheet.iter_rows(values_only=True);headers=[str(v).strip() if v is not None else f'col_{i}' for i,v in enumerate(next(rows))]
        for raw in rows:
            if raw is None or all(v is None for v in raw):continue
            row={h:normalizer._cell_to_str(raw[i] if i<len(raw) else None) for i,h in enumerate(headers)}
            spool_bytes+=len(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8'))+1;digest.add(row)
    finally:book.close()
    require(digest.finish()==reference['expected']['row_digest'] and sha(source)==reference['archive']['source_sha256'],'Independent review row digest/source differs')
    return {'method':'Fresh complete original-helper row pass and independent openpyxl shared-string table; exact sorted-key compact UTF-8 JSONL byte extent recomputed without retaining rows','source_sha256':sha(source),'source_bytes':source.stat().st_size,'shared_strings':shared_count,'shared_string_bytes':shared_bytes,'row_spool_bytes':spool_bytes,'row_digest':digest.finish()}

def review(report,oracles):
    ref=json.loads((ROOT/REFERENCE).read_text());full=ref['expected']
    require(report['status']=='full_Revised_disk_row_normalization_passed_dictionary_rendering_and_integration_pending' and report['stage']=='complete','Row batch incomplete')
    require(not report['M2_complete'] and not report['Revised_WFG_dictionary_conversion_qualified'] and not report['RSS_is_OS_limit'] and report['native_readers']=='NOT_REQUESTED','Row-only qualification scope expanded')
    require(report['build_profile']=='release_for_process_cases_debug_for_tests' and report['RSS_observation_target_bytes']==RSS_TARGET,'Row process build/memory profile differs')
    require(report['steps']==[{'name':'row-spool-tests','returncode':0},{'name':'build-release-row-spool','returncode':0}],'Row native command receipts differ')
    require(report['protected_source_sha256']==protected_sources() and report['source_sha256']==fingerprints(),'Row qualified source bindings differ')
    require(report['legacy_normalizer_sha256']==ref['legacy_normalizer_sha256'],'Captured helper identity differs')
    require(report['dependency_packages']==check_lock() and report['dependency_lock_sha256']==sha(ROOT/LOCK),'Row dependency graph/lock differs')
    cases=json.loads((ROOT/'baseline/xlsx-reader-kit/expected.json').read_text());checks=report['checks'];by={c['case']:c for c in checks}
    failures={**{name:(file,code,{}) for name,file,code in [('date','date.xlsx','unsupported_cell'),('duration','duration.xlsx','unsupported_cell'),('missing-dimension','no-dimension.xlsx','unsupported_workbook'),('external-sheet','external.xlsx','unsupported_workbook'),('invalid-zip','invalid.xlsx','malformed_workbook')]},**{'cancel-'+phase:('normalization.xlsx','cancelled',{'cancel_phase':phase}) for phase in ['snapshot','shared_strings','normalize_rows','verify_rows','complete']},'cannot-grow-rows':('normalization.xlsx','invalid_input',{'tighten':{'rows':200001}}),'cannot-grow-part':('normalization.xlsx','invalid_input',{'tighten':{'part_bytes':96*1024*1024+1}}),**{name:(ref['archive']['member'],'limit_exceeded',{'tighten':options}) for name,options in [('old-part-cap',{'part_bytes':32*1024*1024}),('old-row-cap',{'rows':32000}),('old-rectangle-cap',{'cells':512000}),('lowered-spool',{'spool_bytes':16})]},'missing-sheet':(ref['archive']['member'],'sheet_not_found',{})}
    require(len(checks)==len(by)==27 and list(by)==['small-'+name for name in cases]+list(failures)+['full-revised-rows'],'Row case inventory/order differs')
    for c in checks:
        require(0<c['peak_RSS_bytes']<=RSS_TARGET,'Row process exceeded observed RSS envelope')
        if c['case'] in failures:
            file,code,options=failures[c['case']];require(Path(c['request']['source']).name==file and c['request']=={'source':c['request']['source'],'worksheet':('missing-sheet' if c['case']=='missing-sheet' else full['worksheet']) if file==ref['archive']['member'] else None,**options},'Refusal source/options differ')
            require(c['returncode']==1 and c['reply']['status']=='failed' and c['reply']['error']['code']==code and 'receipt' not in c['reply'],'Wrong typed row refusal')
        else:
            reply=c['reply'];receipt=reply['receipt'];require(c['returncode']==0 and reply['status']=='succeeded' and reply['private_cleanup'] and receipt['profile']=='moe-disk-rows-general-numeric-v1','Successful row receipt differs')
            require(set(reply['progress_phases'])=={'begin','snapshot','package_preflight','shared_strings','normalize_rows','verify_rows','complete'},'Missing row/reopen/cleanup progress')
            require(receipt['row_spool_bytes']<=192*1024*1024 and receipt['temporary_bytes']<=512*1024*1024 and receipt['shared_index_bytes']==16*receipt['shared_strings']<=receipt['shared_index_reserved_bytes']<=32*1024*1024,'Row spool/index accounting exceeds envelope')
    for name,case in cases.items():
        check=by['small-'+name];path=ROOT/'baseline/xlsx-reader-kit'/case['file'];oracle=inspect(path,case.get('sheet'));receipt=check['reply']['receipt'];d=RowDigest()
        for row in case['rows']:d.add(row)
        require(oracle['row_digest']==d.finish() and oracle['headers']==case['headers'],'Review oracle differs from captured golden rows')
        require(check['python_row_oracle']==oracle and all(receipt[k]==v for k,v in oracle.items()) and receipt['source_sha256']==sha(path),'Small native row output differs from original golden/helper')
        require(check['request']=={'source':check['request']['source'],'worksheet':case.get('sheet')} and Path(check['request']['source']).name==case['file'],'Small row source/options differ')
    check=by['full-revised-rows'];receipt=check['reply']['receipt']
    require(report['full_python_row_oracle']==full and all(receipt[k]==v for k,v in full.items()) and receipt['source_sha256']==ref['archive']['source_sha256'],'Complete native rows differ from independent Python references')
    require(check['request']=={'source':check['request']['source'],'worksheet':full['worksheet']} and Path(check['request']['source']).name==ref['archive']['member'],'Full row source/options differ')
    require(receipt['declared_rows']==163910 and receipt['declared_columns']==18 and receipt['stored_cells']==1530428 and receipt['parts']==11 and receipt['advertised_expansion_bytes']==129494214 and receipt['largest_advertised_part_bytes']==74152456,'Full workbook structural counts differ')
    require(oracles['source_sha256']==ref['archive']['source_sha256'] and oracles['source_bytes']==ref['archive']['source_bytes'] and oracles['row_digest']==full['row_digest'],'Independent review source/rows differ')
    require(receipt['shared_strings']==oracles['shared_strings']==615738 and receipt['shared_string_bytes']==oracles['shared_string_bytes'] and receipt['row_spool_bytes']==oracles['row_spool_bytes'],'Disk extents differ from independent complete Python serialization')
    require(receipt['temporary_bytes']==oracles['source_bytes']+oracles['shared_string_bytes']+oracles['row_spool_bytes'],'Full private-file byte sum differs')
    return {'full_normalized_rows':163909,'full_row_pairs':2950362,'process_cases':27,'successes':10,'expected_refusals':17,'full_process_RSS_bytes':check['peak_RSS_bytes'],'max_observed_RSS_bytes':max(c['peak_RSS_bytes'] for c in checks),'full_temporary_bytes':receipt['temporary_bytes'],'shared_strings':receipt['shared_strings'],'scope':'Full row digest, nine small original goldens, typed refusals and independently recomputed SST/JSONL extents checked. Native files/cleanup remain assertions of exact Mac harness. Release process measurements; no local Rust execution or Revised/WFG dictionary rendering qualification; M2 partial.'}
if __name__=='__main__':
    import sys
    if sys.argv[1]=='--oracles':print(json.dumps(generate_oracles(Path(sys.argv[2])),indent=2))
    else:print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text())),indent=2))
