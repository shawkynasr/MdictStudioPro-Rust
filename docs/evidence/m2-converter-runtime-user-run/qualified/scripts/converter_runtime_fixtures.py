"""Deterministic larger converter sources, captured-plugin oracles and digests."""
import json
import shutil
from pathlib import Path
from moe_fixtures import KINDS,workbook,normalized,compare,load_plugins
from m2_text import load_oracle,oracle_convert
from large_io_oracle import digest

def parse_txt(data):
    """Linear fixture parser; preserve empty bodies and final body newlines."""
    blocks=data.decode('utf-8').split('\n</>\n')
    if blocks[-1]!='':raise AssertionError('Missing final canonical delimiter')
    result=[]
    for block in blocks[:-1]:
        key,sep,text=block.partition('\n')
        if not sep or not key:raise AssertionError('Missing canonical head/body separator')
        result.append({'key':key,'text':text})
    return result

def moe_rows(count):
    for i in range(count):
        group=i//2;head=f'詞{group:05d}'
        yield {'字詞名':head,'單字':head,'成語':head,'多音排序':i%2+1,'注音一式':'ㄕˋ','注音':'ㄕˋ','漢語拼音':'shì','釋義':f'[名]\n1. 測試{i}，字 العربية。\n2. 如：「測試」。 &sample.png;','解釋':f'&&字ㄗˋ&&\n解釋{i}。','部首字':'言','部首':'言','總筆畫數':13,'部首外筆畫數':6,'部首外筆畫':6,'辭條別名':f'別{group:05d}','相似詞':'同一' if i%2 else '同二','相反詞':'反義','編號':group,'主條成語／非主條成語':'主條成語','典源文獻內容':'《書》：「測試。」*1*','典源注解':'1. 測試。'}
def generate(directory,moe_count=12000,cedict_count=16000):
    directory.mkdir(exist_ok=True);xlsx=directory/'larger.xlsx';workbook(xlsx,list(moe_rows(moe_count)));cedict=directory/'larger-cedict.txt'
    with cedict.open('w',encoding='utf-8',newline='\n') as f:
        f.write('# Larger synthetic CC-CEDICT fixture\n')
        for i in range(cedict_count):f.write(f'傳{i:05d} 简{i:05d} [nu:3 hao3] /definition {i}/(old) 字 العربية/\n')
    return [{'kind':'cc_cedict','source':cedict,'input_rows':cedict_count}]+[{'kind':k,'source':xlsx,'input_rows':moe_count} for k in KINDS]
def original(source,kind,destination):
    if kind=='cc_cedict':
        # The captured plugin writes INPUT_log.txt. Run it on an exact-byte
        # oracle-side copy so this legacy side effect cannot alter input trees.
        oracle_source=destination.with_name(destination.stem+'-source.txt');shutil.copyfile(source,oracle_source);metrics=oracle_convert(load_oracle(),oracle_source,destination);entries=parse_txt(destination.read_bytes());summary={'primary_entries':metrics['primary_entries'],'alias_redirects':0,'traditional_entries':metrics['traditional_entries'],'skipped_rows_or_lines':metrics['skipped_lines']};comments=len(metrics['comments'])
    else:
        load_plugins()[kind].convert(str(source),str(destination),'utf-8',lambda _:None,lambda _:None);entries=parse_txt(destination.read_bytes());primary=sum(not e['text'].startswith('@@@LINK=') for e in entries);summary={'primary_entries':primary,'alias_redirects':len(entries)-primary,'traditional_entries':0,'skipped_rows_or_lines':0};comments=0
    return entries,summary,comments
def record_digest(entries,kind):
    entries=entries if kind=='cc_cedict' else normalized(entries,kind)
    return digest((e['key'],e['text'].encode('utf-8')) for e in entries)
def compare_output(path,expected,kind):
    actual=parse_txt(path.read_bytes())
    if kind=='cc_cedict':
        if actual!=expected:raise AssertionError('CC-CEDICT output records differ from captured Python')
    else:compare(actual,expected,kind)
    got=record_digest(actual,kind);want=record_digest(expected,kind)
    if got!=want:raise AssertionError('Normalized converter record digest differs')
    return got
