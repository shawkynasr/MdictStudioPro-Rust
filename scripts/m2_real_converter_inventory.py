"""Read-only preflight of selected original CC-CEDICT/MOE converter sources.

No conversion, sampling, source editing, plugin execution or limit increase.
Only file identities, counts, recognized columns and profile blockers are saved.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
import traceback
import zipfile
from openpyxl import load_workbook
from openpyxl.cell.read_only import ReadOnlyCell
from m2_sizing import ROOT,require,sha
from converter_runtime_lock import LOCK,check_lock

PROFILE={'input_bytes':32*1024*1024,'entries':100000,'source_lines':4_000_000,'line_bytes':1024*1024,'workbook_parts':2048,'workbook_uncompressed_bytes':128*1024*1024,'workbook_part_bytes':32*1024*1024,'workbook_rows':32000,'workbook_columns':64,'workbook_cells':512000,'workbook_decoded_bytes':32*1024*1024}
CC_LINE=re.compile(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/$')
HEADS={'字詞名':['moe_revised','moe_revised_wfg','moe_concise'],'成語':['moe_idioms'],'單字':['moe_mini']}
KNOWN=set(HEADS)|{'釋義','解釋','注音一式','注音','漢語拼音','多音排序','辭條別名','相似詞','相反詞','變體注音','變體漢語拼音','部首字','部首','總筆畫數','部首外筆畫數','編號','主條成語／非主條成語','典源文獻內容','典源注解'}
def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-real-readers-user-run/m2-real-readers-report.json').read_text());result={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in result.items():require(sha(ROOT/n)==h,f'Qualified source changed: {n}')
    return result
def fingerprints():return {n:sha(ROOT/n) for n in ['scripts/m2_real_converter_inventory.py','scripts/test_real_converter_inventory.py']}
def file_hash(path,cap=512*1024*1024):
    total=0;h=hashlib.sha256()
    with path.open('rb') as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode),'Expected a regular source file')
        while block:=f.read(65536):
            total+=len(block);require(total<=cap,'Source identity hashing exceeded 512 MiB preflight cap');h.update(block)
    return h.hexdigest()
def text_profile(path,limits=PROFILE):
    result={'type':'cc_cedict_text','possible_converters':[],'scan_complete':True,'observed_lines':0,'matching_lines':0,'traditional_extra_records':0,'comments':0,'skipped_nonempty_lines':0,'estimated_output_records':0,'blockers':[]}
    with path.open('rb') as binary:
        if binary.read(3)==b'\xef\xbb\xbf':result['blockers'].append('utf8_bom_outside_native_profile')
        binary.seek(0)
        with io.TextIOWrapper(binary,encoding='utf-8',errors='strict',newline=None) as stream:
            while line:=stream.readline(limits['line_bytes']+1):
                result['observed_lines']+=1
                if result['observed_lines']>limits['source_lines'] or len(line.encode())>limits['line_bytes']:result['blockers'].append('source_line_or_line_byte_cap');result['scan_complete']=False;break
                if '\0' in line:result['blockers'].append('nul_in_source');result['scan_complete']=False;break
                value=line.strip()
                if not value:continue
                if value.startswith('#'):result['comments']+=1;continue
                match=CC_LINE.fullmatch(value)
                if match:result['matching_lines']+=1;result['traditional_extra_records']+=int(match[1]!=match[2])
                else:result['skipped_nonempty_lines']+=1
    result['estimated_output_records']=result['matching_lines']+result['traditional_extra_records']
    if result['matching_lines']:result['possible_converters']=['cc_cedict']
    else:result['blockers'].append('no_matching_cc_cedict_records')
    if result['estimated_output_records']>limits['entries']:result['blockers'].append('converted_entry_cap')
    if result['comments']>limits['entries']:result['blockers'].append('comment_count_cap')
    result['output_bytes_checked']=False;return result
def worksheet_profile(sheet,limits):
    result={'worksheet':sheet.title,'declared_rows':sheet.max_row,'declared_columns':sheet.max_column,'scan_complete':True,'observed_row_coordinates':0,'observed_cells':0,'estimated_decoded_value_bytes':0,'recognized_columns':[],'possible_converters':[],'blockers':[],'unsupported_scalar_cells':0}
    if result['declared_rows'] and result['declared_columns']:
        result['declared_rectangle_cells']=result['declared_rows']*result['declared_columns']
        if result['declared_rectangle_cells']>limits['workbook_cells']:result['blockers'].append('workbook_rectangle_cell_cap')
    sheet.reset_dimensions()
    for number,row in enumerate(sheet.iter_rows(),1):
        result['observed_row_coordinates']=number
        if number>limits['workbook_rows']:result['blockers'].append('workbook_row_cap');result['scan_complete']=False;break
        if len(row)>limits['workbook_columns']:result['blockers'].append('workbook_column_cap');result['scan_complete']=False;break
        for cell in row:
            if isinstance(cell,ReadOnlyCell):result['observed_cells']+=1
            value=cell.value
            if value is None:continue
            if getattr(cell,'data_type',None)=='e' or not isinstance(value,(str,int,float,bool)) or isinstance(value,float) and not math.isfinite(value):result['unsupported_scalar_cells']+=1;continue
            text=str(value).strip();result['estimated_decoded_value_bytes']+=len(text.encode())
            if number==1 and text in KNOWN:result['recognized_columns'].append(text)
        if result['observed_cells']>limits['workbook_cells'] or result['estimated_decoded_value_bytes']>limits['workbook_decoded_bytes']:result['blockers'].append('workbook_cell_or_decoded_value_cap');result['scan_complete']=False;break
    result['recognized_columns']=sorted(set(result['recognized_columns']));result['possible_converters']=sorted({kind for header in result['recognized_columns'] for kind in HEADS.get(header,[])})
    if result['unsupported_scalar_cells']:result['blockers'].append('unsupported_scalar_cells_need_native_profile_review')
    if not result['possible_converters']:result['blockers'].append('no_recognized_moe_headword_column')
    result['output_entries_and_bytes_checked']=False;return result
def workbook_profile(path,limits=PROFILE):
    result={'type':'moe_xlsx','possible_converters':[],'blockers':[],'worksheets':[]}
    with zipfile.ZipFile(path) as z:
        parts=z.infolist();result.update(zip_parts=len(parts),zip_advertised_uncompressed_bytes=sum(p.file_size for p in parts),largest_advertised_part_bytes=max((p.file_size for p in parts),default=0))
        if len(parts)>limits['workbook_parts']:result['blockers'].append('workbook_part_count_cap')
        if result['zip_advertised_uncompressed_bytes']>limits['workbook_uncompressed_bytes']:result['blockers'].append('workbook_zip_expansion_cap')
        if result['largest_advertised_part_bytes']>limits['workbook_part_bytes']:result['blockers'].append('workbook_part_byte_cap')
        if len({p.filename for p in parts})!=len(parts) or any(p.flag_bits&1 for p in parts):result['blockers'].append('duplicate_or_encrypted_zip_parts')
    if result['blockers']:result['worksheet_scan']='not_started_outside_current_profile';return result
    book=load_workbook(path,read_only=True,data_only=True,keep_links=False)
    try:
        if len(book.worksheets)>16:result['blockers'].append('preflight_worksheet_count_cap');return result
        for sheet in book.worksheets:result['worksheets'].append(worksheet_profile(sheet,limits))
    finally:book.close()
    result['possible_converters']=sorted({kind for sheet in result['worksheets'] for kind in sheet['possible_converters']});result['worksheet_scan']='complete' if all(s['scan_complete'] for s in result['worksheets']) else 'bounded_scan_stopped';return result
def inventory(inputs,limits=PROFILE):
    inputs=inputs.resolve();require(inputs.is_dir(),'Create the selected source directory and place original text/XLSX files inside it');paths=[]
    for path in inputs.rglob('*'):
        if path.suffix.lower() in {'.txt','.u8','.xlsx'}:
            resolved=path.resolve();require(resolved.is_relative_to(inputs),'Source symlink escapes selected directory');require(resolved.is_file(),'Selected source must be a regular file');paths.append((path,resolved));require(len(paths)<=16,'At most 16 selected source files in this preflight')
    require(paths,'No .u8, .txt or .xlsx source files found in selected directory');results=[]
    for path,resolved in sorted(paths):
        print(f'Inspecting selected converter source: {path.name}',flush=True);size=resolved.stat().st_size;item={'file':str(path.relative_to(inputs)),'source_bytes':size,'source_sha256':None,'blockers':[]}
        if size>512*1024*1024:item['blockers'].append('above_preflight_hashing_cap');item['analysis']='metadata_only'
        else:
            before=file_hash(resolved);item['source_sha256']=before
            if size>limits['input_bytes']:item['blockers'].append('input_snapshot_byte_cap');item['analysis']='not_parsed_outside_current_profile'
            else:
                try:item['profile']=workbook_profile(resolved,limits) if path.suffix.lower()=='.xlsx' else text_profile(resolved,limits)
                except (ValueError,UnicodeError,zipfile.BadZipFile,KeyError) as e:item['blockers'].append('source_parse_error');item['error_type']=type(e).__name__
            require(file_hash(resolved)==before,'Source changed during read-only preflight')
        results.append(item)
    return results
def selection_template(files):
    cases=[]
    for i,item in enumerate(files,1):
        profile=item.get('profile',{});sheets=profile.get('worksheets')
        candidates=sheets if sheets is not None else [{'worksheet':None,'possible_converters':profile.get('possible_converters',[]),'blockers':profile.get('blockers',[])}]
        for j,sheet in enumerate(candidates,1):
            for kind in sheet['possible_converters']:cases.append({'id':f'source-{i:02d}-sheet-{j:02d}-{kind}','converter':kind,'input':item['file'],'worksheet':sheet['worksheet'],'selected':False,'preflight_blockers':sorted(set(item['blockers']+profile.get('blockers',[])+sheet.get('blockers',[])))})
    return {'purpose':'Draft mapping only; all cases start unselected. This inventory does not run conversions. Header compatibility does not identify the intended dictionary dataset.','cases':cases}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();require(out.name.startswith('m2-real-converters-out'),'Use an m2-real-converters-out prefix for private outputs');out.mkdir(exist_ok=False)
    report={'status':'real_converter_inventory_failed','stage':'preflight','M2_complete':False,'conversion_qualification_passed':False,'conversions_run':0,'profile_ceilings':PROFILE,'files':[]}
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints();report['dependency_packages']=check_lock();report['dependency_lock_sha256']=sha(ROOT/LOCK);report['files']=inventory(a.inputs);template=selection_template(report['files']);(out/'converter-selection-draft.json').write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n');report['selection_candidates']=len(template['cases']);report['status']='real_converter_inventory_complete_selection_and_profile_review_required';report['stage']='complete';require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Qualified/new source changed during inventory')
    except (Exception,KeyboardInterrupt) as e:report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
    path=out/'m2-real-converter-inventory.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='real_converter_inventory_failed')
if __name__=='__main__':raise SystemExit(main())
