"""Synthetic XLSX compatibility cases; no user dictionary data or GUI imports."""
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import random
import xml.etree.ElementTree as ET
import zipfile
from openpyxl import Workbook, load_workbook

ROOT=Path(__file__).resolve().parents[1]
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
TYPES='http://schemas.openxmlformats.org/package/2006/content-types'


def original_reader():
    spec=importlib.util.spec_from_file_location('studio_excel_oracle',ROOT/'baseline/legacy/excel_utils.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.read_excel_as_dicts


def oracle(path,sheet=None):
    rows=original_reader()(str(path),sheet)
    wb=load_workbook(path,read_only=True,data_only=True)
    try:
        ws=wb[sheet] if sheet else wb.active
        raw=next(ws.iter_rows(values_only=True),())
        headers=[str(value).strip() if value is not None else f'col_{i}' for i,value in enumerate(raw)]
        return {'sheet_name':ws.title,'headers':headers,'rows':rows}
    finally:wb.close()


def workbook(path,rows):
    wb=Workbook();ws=wb.active
    for row in rows:ws.append(row)
    wb.save(path);wb.close()


def mutate(path,edits,extra=None):
    with zipfile.ZipFile(path) as archive:
        parts={item.filename:archive.read(item) for item in archive.infolist()}
    for name,edit in edits.items():
        tree=ET.fromstring(parts[name]);edit(tree);parts[name]=ET.tostring(tree,encoding='utf-8',xml_declaration=True)
    parts.update(extra or {})
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in parts.items():archive.writestr(name,data)


def cell(tree,address):
    result=tree.find(f'.//{{{NS}}}c[@r="{address}"]')
    if result is None:raise AssertionError(f'Missing synthetic cell {address}')
    return result


def value(tree,address,kind,text):
    target=cell(tree,address)
    for child in list(target):
        if child.tag in {f'{{{NS}}}v',f'{{{NS}}}is'}:target.remove(child)
    target.set('t',kind)
    if kind=='inlineStr':
        inline=ET.SubElement(target,f'{{{NS}}}is');ET.SubElement(inline,f'{{{NS}}}t').text=text
    else:ET.SubElement(target,f'{{{NS}}}v').text=text


def generate(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);cases=[]
    def add(name,path,sheet=None,refusal=None):cases.append({'name':name,'file':path.name,'sheet':sheet,'refusal':refusal})
    path=directory/'normalization.xlsx'
    workbook(path,[[' label ',None,'number','flag',' padded '],[' 字 ',' 001 ',1.0,True,' value '],
                   [None]*5,['\u2000甲\u3000','\t002\u00a0',1.25,False,'\u200bkeep\u200b']])
    add('normalization',path)
    path=directory/'headers.xlsx'
    workbook(path,[['dup',' dup ',None,'','col_2',True,1,1,' '],['left','right','fallback','empty header','explicit',False,1.0,'x','space']])
    mutate(path,{'xl/worksheets/sheet1.xml':lambda root:(value(root,'D1','inlineStr',''),value(root,'G1','n','1.0'),value(root,'H1','n','1E-5'))})
    add('duplicate-and-typed-headers',path)
    path=directory/'active.xlsx';wb=Workbook();first=wb.active;first.title='First';first.append(['wrong']);first.append(['ignored'])
    ws=wb.create_sheet('العربية & 字');ws['C1']='詞';ws['D1']=' 注音 ';ws['E1']='值';ws['C2']='字';ws['D2']='ㄗˋ';ws['E2']=1.0;ws['C5']='和';ws['E5']=True
    wb.active=1;wb.save(path);wb.close();add('active-sheet',path);add('named-first-sheet',path,'First');add('missing-sheet',path,'missing','sheet_not_found')
    path=directory/'leading.xlsx';wb=Workbook();ws=wb.active;ws['C3']='詞';ws['D3']='值';ws['C4']='字';ws['D4']='中文';wb.save(path);wb.close();add('leading-blank-row-and-columns',path)
    path=directory/'formulas.xlsx'
    workbook(path,[['word','integer','fraction','uncached','string-cache','error-cache','raw-str'],
        ['字','=1+1','=3/2','=NOW()','=A2','=1/0','=A2'],[None,None,None,'=NOW()',None,None,None],
        [None,None,None,None,'=A2',None,None]])
    def formulas(root):
        for address,kind,text in [('B2','n','2'),('C2','n','1.5'),('E2','str',' padded '),('F2','e','#DIV/0!'),('G2','str','_x000D_'),('E4','str',' ')]:value(root,address,kind,text)
    mutate(path,{'xl/worksheets/sheet1.xml':formulas});add('cached-and-uncached-formulas',path)
    path=directory/'shared.xlsx';workbook(path,[['value'],['one'],['two'],['three'],['four']])
    sst=ET.Element(f'{{{NS}}}sst',{'count':'4','uniqueCount':'4'})
    for text in [' padded ','Literal _x000D_ and _x005F_x000D_']:
        ET.SubElement(ET.SubElement(sst,f'{{{NS}}}si'),f'{{{NS}}}t').text=text
    si=ET.SubElement(sst,f'{{{NS}}}si')
    for text in [' rich ','& 字']:
        ET.SubElement(ET.SubElement(si,f'{{{NS}}}r'),f'{{{NS}}}t').text=text
    ET.SubElement(ET.SubElement(si,f'{{{NS}}}rPh',{'sb':'0','eb':'1'}),f'{{{NS}}}t').text='PHONETIC_IGNORED'
    ET.SubElement(ET.SubElement(sst,f'{{{NS}}}si'),f'{{{NS}}}t').text=''
    def shared_cells(root):
        for index in range(4):value(root,f'A{index+2}','s',str(index))
    def shared_rel(root):ET.SubElement(root,f'{{{REL}}}Relationship',{'Id':'rIdShared','Type':'http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings','Target':'sharedStrings.xml'})
    def shared_type(root):ET.SubElement(root,f'{{{TYPES}}}Override',{'PartName':'/xl/sharedStrings.xml','ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml'})
    mutate(path,{'xl/worksheets/sheet1.xml':shared_cells,'xl/_rels/workbook.xml.rels':shared_rel,'[Content_Types].xml':shared_type},
           {'xl/sharedStrings.xml':ET.tostring(sst,encoding='utf-8',xml_declaration=True)})
    add('shared-rich-and-empty-strings',path)
    path=directory/'inline.xlsx';workbook(path,[['value'],['x'],['y'],['z'],['plain']])
    def inline(root):
        value(root,'A2','inlineStr',' literal _x000D_ _x005F_ ')
        value(root,'A3','inlineStr','');value(root,'A4','inlineStr',' ')
    mutate(path,{'xl/worksheets/sheet1.xml':inline});add('inline-escapes-and-blank-looking-rows',path)
    path=directory/'numbers.xlsx'
    numbers=['1','1.0','1.5','-0.0','1e-5','1e-4','1e16','1e23','1e308','9007199254740993',
             '1.2345678901234567','2.2250738585072014e-308','4.9406564584124654e-324','-1e-30']
    randomizer=random.Random(617)
    numbers += [repr(randomizer.uniform(-1e6,1e6)) for _ in range(128)]
    workbook(path,[['id','value']]+[[i,0] for i in range(len(numbers))])
    mutate(path,{'xl/worksheets/sheet1.xml':lambda root:[value(root,f'B{i+2}','n',number) for i,number in enumerate(numbers)]});add('numeric-lexemes',path)
    path=directory/'empty.xlsx';workbook(path,[]);add('empty-workbook',path)
    path=directory/'moe-rows.xlsx';moe=json.loads((ROOT/'baseline/cases.json').read_text())['moe_rows']
    headers=list(dict.fromkeys(key for row in moe for key in row));workbook(path,[headers]+[[row.get(key) for key in headers] for row in moe]);add('captured-MOE-input-rows',path)
    path=directory/'moderate.xlsx';rows=[['字詞名','字數','多音排序','漢語拼音','釋義','flag','id','empty']]
    for index in range(2000):
        if index%257==0:rows.append([None]*8)
        rows.append([f'字{index}',1,index%3,'zi4','文字。\n說明',bool(index%2),f'{index:05d}',None])
    workbook(path,rows);add('moderate-2000-row-table',path)
    for name,number,fmt in [('date',datetime(2020,1,2,3,4,5),'yyyy-mm-dd hh:mm:ss'),('duration',timedelta(hours=27),'[hh]:mm:ss')]:
        path=directory/(name+'.xlsx');wb=Workbook();ws=wb.active;ws.append(['value']);ws.append([number]);ws['A2'].number_format=fmt;wb.save(path);wb.close();add(name+'-refused',path,refusal='unsupported_cell')
    path=directory/'oversized.xlsx';workbook(path,[['value'],['字']]);mutate(path,{'xl/worksheets/sheet1.xml':lambda root:root.find(f'{{{NS}}}dimension').set('ref','A1:XFD1048576')});add('oversized-rectangle',path,refusal='limit_exceeded')
    path=directory/'no-dimension.xlsx';workbook(path,[['value'],['字']]);mutate(path,{'xl/worksheets/sheet1.xml':lambda root:root.remove(root.find(f'{{{NS}}}dimension'))});add('dimension-required',path,refusal='unsupported_workbook')
    path=directory/'external.xlsx';workbook(path,[['value'],['字']])
    def external(root):
        for rel in root:
            if rel.get('Type','').endswith('/worksheet'):rel.set('TargetMode','External');rel.set('Target','https://example.invalid/sheet.xml')
    mutate(path,{'xl/_rels/workbook.xml.rels':external});add('external-sheet-refused',path,refusal='unsupported_workbook')
    path=directory/'invalid.xlsx';path.write_bytes(b'not a zip');add('invalid-workbook',path,refusal='malformed_workbook')
    return cases


def write_unit_kit(directory):
    directory=Path(directory);cases=generate(directory)
    expected={}
    for case in cases:
        if case['name'] in {'normalization','duplicate-and-typed-headers','active-sheet','shared-rich-and-empty-strings','numeric-lexemes','inline-escapes-and-blank-looking-rows','leading-blank-row-and-columns','cached-and-uncached-formulas','empty-workbook'}:
            expected[case['name']]={'file':case['file'],'sheet':case['sheet'],**oracle(directory/case['file'],case['sheet'])}
    (directory/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return cases
