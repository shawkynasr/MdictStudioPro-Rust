"""Finish an existing verified rebuild when only its declared Amiri file is missing.

No Cargo calls, dictionary scans or source writes. Recheck file hashes, add the
explicitly selected font, preserve the old report, and publish staged outputs.
"""
import argparse
import copy
import csv
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
from patched_interop import require
from real_corpus import file_hash


def inside(directory,name):
    relative=PurePosixPath(name)
    require(not relative.is_absolute() and relative.parts and '..' not in relative.parts and '\\' not in name,'Unsafe report output path')
    path=directory.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(directory.resolve()),'Output escapes staged directory')
    return path


def preflight(out,font):
    report_path=out/'real-rebuild-report.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    require(report['status']=='rebuild_records_passed_companions_pending','Expected a completed rebuild waiting only for companions')
    require(report.get('engine_revision')==6 and report.get('cases'),'Unexpected rebuild evidence')
    staged=out/'work/dictionaries';verified=out/'verified-dictionaries'
    require(staged.is_dir() and not staged.is_symlink() and not (out/'work').is_symlink(),'Missing or linked staged dictionary directory')
    require(not verified.exists(),'Verified output already exists; refusing overwrite')
    require(report.get('input_integrity'),'Missing original input integrity evidence')
    for name,check in report['input_integrity'].items():
        require(check['before']==check['after'] and file_hash(Path(name))==check['before'],f'Original input changed: {name}')
    expected={}
    for case in report['cases']:
        require(case['status']=='passed_rebuild_records_metadata_and_order' and case['different_key_payload_counts']==0,'A dictionary rebuild did not pass')
        require(case['source_sha256']==report['input_integrity'][case['source']]['before'],'Source identity differs from input integrity evidence')
        scans=[case[phase][reader] for phase in ['source_scans','rebuilt_scans'] for reader in ['r','p']]
        require(len({s['records'] for s in scans})==1 and scans[0]['records']==case['builder']['records'],'Incomplete scan record counts')
        require(len({s['ordered_key_payload_sha256'] for s in scans})==1,'Physical order scan evidence differs')
        require(all(s['attributes']==scans[0]['attributes'] for s in scans),'Metadata scan evidence differs')
        require(case.get('lookups') and all(x['status']=='passed' for x in case['lookups'].values()),'Rebuilt lookup evidence failed')
        audit=case['structural_audit']
        require(audit['status']=='structural_audit_passed' and audit['sha256']==audit['sha256_after']==case['output_sha256'],'Structural audit identity differs')
        require(audit['records']==case['builder']['records'],'Structural audit record count differs')
        path=inside(staged,case['output_name'])
        require(path.is_file() and file_hash(path)==case['output_sha256'],f'Staged dictionary changed: {case["output_name"]}')
        expected[path]=case['output_sha256']
    missing=[]
    for companion in report['companions']:
        path=inside(staged,companion['relative_output'])
        if companion['status']=='missing':missing.append(companion);continue
        require(companion['status'] in {'copied_exact_bytes','rebuilt_dictionary_companion'},'Another companion remains unqualified')
        require(path.is_file() and file_hash(path)==companion['sha256'],'Staged companion changed')
        require(path not in expected or expected[path]==companion['sha256'],'Companion identity conflicts with dictionary')
        expected[path]=companion['sha256']
    require(len(missing)==1 and missing[0]['relative_output']=='fonts/amiri-regular.ttf','This finalizer supports only the single missing Amiri companion')
    font=font.expanduser().resolve()
    require(font.is_file() and font.suffix.lower()=='.ttf' and 12<=font.stat().st_size<=16*1024*1024,'Select the original Amiri Regular TTF (up to 16 MiB)')
    with font.open('rb') as stream:require(stream.read(4)==b'\0\1\0\0','Expected a TrueType sfnt font')
    font_hash=file_hash(font);target=inside(staged,missing[0]['relative_output'])
    if target.exists():require(target.is_file() and file_hash(target)==font_hash,'A different font already exists in staging')
    for path in staged.rglob('*'):
        require(not path.is_symlink(),'Staged output contains a symbolic link')
        if path.is_file() and path.name!='.DS_Store':require(path in expected or path==target,'Staging contains an unverified extra file')
    return report,staged,verified,font,target,font_hash,missing[0]


def finalize(out,font):
    out=out.expanduser().resolve()
    report,staged,verified,font,target,checksum,pending=preflight(out,font)
    updated=copy.deepcopy(report)
    for companion in updated['companions']:
        if companion['relative_output']==pending['relative_output']:
            companion.update(status='copied_exact_bytes',source=str(font),sha256=checksum)
    updated['input_integrity'][str(font)]={'before':checksum,'after':checksum}
    updated.update(status='real_rebuild_offline_passed_native_untested',native_readers='NOT_RUN_READY_FOR_STAGED_MANUAL_TEST',
        finalization={'method':'font_only_existing_hashes_rechecked_no_rebuild_or_rescan','font_source':str(font),'font_sha256':checksum,
                      'previous_report':'real-rebuild-report.before-finalize.json'})
    backup=out/'real-rebuild-report.before-finalize.json'
    original=(out/'real-rebuild-report.json').read_bytes()
    if backup.exists():require(backup.read_bytes()==original,'Existing backup differs; refusing overwrite')
    else:
        with backup.open('xb') as stream:stream.write(original)
    published=False
    with tempfile.TemporaryDirectory(prefix='.finalize-',dir=out) as scratch:
        scratch=Path(scratch)
        try:
            if not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                # Exclusive destination creation; never overwrite a pre-existing font.
                with font.open('rb') as source,target.open('xb') as destination:shutil.copyfileobj(source,destination)
            require(file_hash(target)==checksum and file_hash(font)==checksum,'Font changed while copying')
            with (scratch/'reader-results.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['reader','dictionary','key','result','notes']);writer.writeheader()
                for case in updated['cases']:
                    if case['output_name'].lower().endswith('.mdx'):
                        for reader in ['GoldenDict','MDict']:
                            for key in case['lookups']:writer.writerow({'reader':reader,'dictionary':case['output_name'],'key':key,'result':'NOT_RUN'})
            (scratch/'report.json').write_text(json.dumps(updated,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            # Verify unchanged dictionaries/companions one final time before promotion.
            preflight(out,font)
            staged.rename(verified);published=True
            os.replace(scratch/'reader-results.csv',out/'reader-results.csv')
            os.replace(scratch/'report.json',out/'real-rebuild-report.json')
        except Exception:
            if published and verified.exists() and not staged.exists():verified.rename(staged)
            raise
    print(f"real_rebuild_offline_passed_native_untested: {out/'real-rebuild-report.json'}")
    print(f"Ready for staged native tests: {verified}")
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Existing rebuild-out directory, not a new output directory')
    parser.add_argument('--amiri-font',type=Path,required=True)
    args=parser.parse_args()
    try:return finalize(args.output,args.amiri_font)
    except Exception as error:print(f'Finalization stopped; existing rebuild evidence retained: {error}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
