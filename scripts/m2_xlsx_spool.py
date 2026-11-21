"""Qualify disk-backed normalized rows before Revised/WFG rendering integration."""
import argparse
import json
import os
import platform
import shutil
import traceback
from pathlib import Path
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,CommandTimeout
from m2_official_mini_idioms import extract_sources
from xlsx_spool_oracle import inspect
from xlsx_spool_lock import MANIFEST,LOCK,check_lock
REFERENCE='docs/evidence/revised-row-source-reference/reference.json'
RSS_TARGET=192*1024*1024
def protected_sources():
    report=json.loads((ROOT/'docs/evidence/m2-cc-full-user-run/m2-cc-full-report.json').read_text());result={**report['protected_source_sha256'],**report['source_sha256']}
    require(len(result)==241,'Previous source inventory differs')
    for name,h in result.items():require(sha(ROOT/name)==h,'Accepted source changed: '+name)
    for name in ['m2/xlsx-reader/src/xml.rs','m2/xlsx-reader/src/numbers.rs','m2/indexed-engine/src/sha256.rs']:require(name in result,'Shared helper not source-bound')
    return result
def fingerprints():
    paths=[p for p in (ROOT/'m2/xlsx-spool').rglob('*') if p.is_file() and 'target' not in p.parts]
    paths += [ROOT/n for n in ['scripts/m2_xlsx_spool.py','scripts/xlsx_spool_lock.py','scripts/xlsx_spool_oracle.py','scripts/test_xlsx_spool.py',REFERENCE]]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archives',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();out=args.output.resolve();require(out.name.startswith('m2-xlsx-spool-out'),'Use m2-xlsx-spool-out prefix for private exclusions');out.mkdir(exist_ok=False)
    report={'status':'m2_xlsx_spool_failed','stage':'preflight','M2_complete':False,'Revised_WFG_dictionary_conversion_qualified':False,'native_readers':'NOT_REQUESTED','steps':[],'checks':[],'RSS_observation_target_bytes':RSS_TARGET,'RSS_is_OS_limit':False,'build_profile':'release_for_process_cases_debug_for_tests'}
    try:
        reference=json.loads((ROOT/REFERENCE).read_text());report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['legacy_normalizer_sha256']=reference['legacy_normalizer_sha256']
        for name,h in report['legacy_normalizer_sha256'].items():require(sha(ROOT/name)==h,'Captured normalizer changed')
        report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK)
        sources=extract_sources(args.archives.resolve(),out/'sources',[reference['archive']]);source=sources[reference['archive']['member']];source_hash=sha(source)
        cargo=shutil.which('cargo');require(cargo is not None,'Run this batch on the Rust-enabled Mac')
        for name,cmd in [('row-spool-tests',[cargo,'test','--locked','--offline','--manifest-path',MANIFEST,'--workspace']),('build-release-row-spool',[cargo,'build','--release','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-xlsx-spool'])]:
            report['stage']=name;print(name,flush=True);result=timed_run(cmd);log=result.stdout+'\nSTDERR:\n'+result.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':result.returncode};report['steps'].append(step)
            if result.returncode:step['failure_log_tail']=log[-64000:]
            require(result.returncode==0,'Native command failed: '+name)
        binary=ROOT/'m2/xlsx-spool/target/release/studio-xlsx-spool';report['binary_sha256']=sha(binary)
        requests=out/'requests';requests.mkdir();scratch=out/'private-rust';scratch.mkdir();env=dict(os.environ);env.update(TMPDIR=str(scratch),LC_ALL='C');system=platform.system()
        def run(name,path,worksheet=None,code=None,**options):
            req={'source':str(path),'worksheet':worksheet,**options};request_path=requests/(name+'.json');request_path.write_text(json.dumps(req,ensure_ascii=False)+'\n');report['stage']=name;print(name,flush=True)
            command=['/usr/bin/time','-l' if system=='Darwin' else '-v',str(binary),str(request_path)];result=timed_run(command,env=env);(out/(name+'.stdout')).write_text(result.stdout);(out/(name+'.stderr')).write_text(result.stderr)
            try:reply=json.loads(result.stdout)
            except Exception:report['invalid_native_response']={'case':name,'stdout_tail':result.stdout[-64000:],'stderr_tail':result.stderr[-64000:]};raise
            rss=peak_rss(result.stderr,system);check={'case':name,'request':req,'returncode':result.returncode,'reply':reply,'peak_RSS_bytes':rss};report['checks'].append(check)
            require(rss<=RSS_TARGET,'Native process exceeds provisional 192 MiB row-reader target');require(not list(scratch.iterdir()),'Private row-spool residue after exit')
            if code:require(result.returncode==1 and reply['status']=='failed' and reply['error']['code']==code,'Unexpected row-spool refusal: '+name)
            else:require(result.returncode==0 and reply['status']=='succeeded' and reply['private_cleanup'],'Native row spool failed: '+name)
            return check
        # Independent original-helper expectations for all existing common-cell
        # golden files; only metadata/digests are reported, never cell contents.
        cases=json.loads((ROOT/'baseline/xlsx-reader-kit/expected.json').read_text())
        for name,case in cases.items():
            path=ROOT/'baseline/xlsx-reader-kit'/case['file'];before=sha(path);oracle=inspect(path,case.get('sheet'));check=run('small-'+name,path,case.get('sheet'));receipt=check['reply']['receipt'];check['python_row_oracle']=oracle
            require(all(receipt[k]==v for k,v in oracle.items()) and receipt['source_sha256']==before and sha(path)==before,'Small row normalization differs from captured Python: '+name)
        for name,file,code in [('date','date.xlsx','unsupported_cell'),('duration','duration.xlsx','unsupported_cell'),('missing-dimension','no-dimension.xlsx','unsupported_workbook'),('external-sheet','external.xlsx','unsupported_workbook'),('invalid-zip','invalid.xlsx','malformed_workbook')]:run(name,ROOT/'baseline/xlsx-reader-kit'/file,code=code)
        small=ROOT/'baseline/xlsx-reader-kit/normalization.xlsx'
        for phase in ['snapshot','shared_strings','normalize_rows','verify_rows','complete']:run('cancel-'+phase,small,code='cancelled',cancel_phase=phase)
        run('cannot-grow-rows',small,code='invalid_input',tighten={'rows':200001});run('cannot-grow-part',small,code='invalid_input',tighten={'part_bytes':96*1024*1024+1})
        sheet=reference['expected']['worksheet']
        for name,options in [('old-part-cap',{'part_bytes':32*1024*1024}),('old-row-cap',{'rows':32000}),('old-rectangle-cap',{'cells':512000}),('lowered-spool',{'spool_bytes':16})]:run(name,source,sheet,code='limit_exceeded',tighten=options)
        run('missing-sheet',source,'missing-sheet',code='sheet_not_found')
        report['stage']='full-python-row-oracle';print('Comparing complete Revised worksheet rows with captured Python',flush=True);oracle=inspect(source,sheet);report['full_python_row_oracle']=oracle;require(oracle==reference['expected'],'Mac Python rows differ from full independent reference')
        check=run('full-revised-rows',source,sheet);receipt=check['reply']['receipt'];require(all(receipt[k]==v for k,v in oracle.items()) and receipt['profile']=='moe-disk-rows-general-numeric-v1' and receipt['source_sha256']==source_hash,'Full normalized rows differ from both independent Python oracles')
        require(receipt['declared_rows']==163910 and receipt['declared_columns']==18 and receipt['stored_cells']==1530428 and receipt['shared_strings']==615738,'Full workbook structural counts differ');require(receipt['temporary_bytes']<=512*1024*1024 and receipt['shared_index_reserved_bytes']<=32*1024*1024,'Measured spool or shared index exceeds stated envelope')
        require(sha(source)==source_hash and protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'] and check_lock()==report['dependency_packages'],'Source or dependency changed during qualification');report['stage']='complete';report['status']='full_Revised_disk_row_normalization_passed_dictionary_rendering_and_integration_pending'
    except (Exception,KeyboardInterrupt) as error:
        report['error']=f'{type(error).__name__}: {error}';report['python_traceback']=traceback.format_exc()
        if isinstance(error,CommandTimeout):report['timed_out_command_output_tail']=error.output_tail
    path=out/'m2-xlsx-spool-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report['status']+': '+str(path));return int(report['status']=='m2_xlsx_spool_failed')
if __name__=='__main__':raise SystemExit(main())
