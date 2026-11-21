"""Synthetic branch coverage and narrowly scoped legacy set-order comparison."""
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'baseline'))
from capture import workbook,load_plugins
KINDS=['moe_revised','moe_revised_wfg','moe_concise','moe_idioms','moe_mini']
LABELS=('相似詞','相反詞','多音參見','辭條別名','異體字')


def parse_txt(data):
    """Fixture-only canonical framing, independent of Rust implementation."""
    text=data.decode('utf-8');records=[]
    while text:
        key,sep,text=text.partition('\n')
        if not sep:raise AssertionError('Missing fixture headword separator')
        body,sep,text=text.partition('\n</>\n')
        if not sep:raise AssertionError('Missing fixture delimiter')
        records.append({'key':key,'text':body})
    return records


def normalized(entries,kind):
    """Only original Python set iteration is unordered; everything else exact.

    Alias records remain associated with their immediately preceding main entry.
    Duplicate main entries, reference values, HTML and all other order survive.
    """
    result=[];aliases=[]
    def flush():
        result.extend(sorted(aliases,key=lambda e:(e['key'],e['text'])));aliases.clear()
    for entry in entries:
        entry=dict(entry)
        if kind=='moe_revised' and entry['text'].startswith('@@@LINK='):
            if not result:raise AssertionError('Alias before a main entry')
            aliases.append(entry);continue
        flush()
        if kind in ('moe_revised','moe_concise'):
            for label in LABELS:
                pattern=r'(<span class="polyref"><b>'+re.escape(label)+r'：</b>)(.*?)(</span>)'
                # A nested image span is not accepted by this comparator. These
                # synthetic set-valued fields contain plain values / img tags.
                entry['text']=re.sub(pattern,lambda m:m[1]+'；'.join(sorted(m[2].split('；')))+m[3],entry['text'],flags=re.S)
        result.append(entry)
    flush();return result


def compare(actual,expected,kind):
    if normalized(actual,kind)!=normalized(expected,kind):
        raise AssertionError(f'{kind}: converter content or deterministic ordering differs beyond documented set order')


def extended_rows():
    rows=[]
    # Eleven polyphones exercise Chinese numeral fallback, stable duplicate
    # sorting, zero/negative ordering, variants and first-row metadata.
    for i,sort in enumerate(['2','-2','0','+1','1_0','bad','2','999999999999999999999999','-999999999999999999999999','6','7']):
        rows.append({'字詞名':'試','單字':'試','成語':'同心協力','多音排序':sort,'字數':'1',
            '部首字':'言','部首':'言','部首外筆畫數':'6','部首外筆畫':'6','總筆畫數':'13',
            '注音一式':'ㄕˋ' if i%2 else 'ㄕ','注音':'ㄕˋ','漢語拼音':'shì',
            '變體注音':'ㄕˊ','變體漢語拼音':'shí','變體類型 1:變 2:又音 3:語音 4:讀音':['1','2','3','4','語音','custom'][i%6],
            '釋義':'「[名]\n1. 試一試。\n2. 如：「測試」。《書》：「試」。\n[動] 使用。\n21. 作者．《書》：「引文」。\n21. 普通說明。\n[形] 第三詞性。\n9868._104_0.gif 9b46._104_0.gif &4E00_.png; &sample.PNG;\n」',
            '解釋':'&&試ㄕˋ&&\n&sample.png;\r獨立換行_x000D_',
            '相似詞':'乙' if i%2 else '甲','相反詞':'反乙' if i%2 else '反甲',
            '多音參見訊息':'參乙\n行' if i%2 else '參甲','異體字':'異乙' if i%2 else '異甲',
            '辭條別名':'別乙；別甲；試；別乙' if i%2 else '別丙；別甲',
            '主條成語／非主條成語':'主條成語','編號':'007',
            '典源文獻名稱':'《書》','典源文獻內容':'第一行\n第二行*1* *20* *21* *0002*',
            '典源注解':'1. 注一\n2. 注二','典故說明':'首行\n次行','書證':'書證*1*\n*21*',
            '用法說明-語義說明':'同心協力。','用法說明-使用類別':'類別','用法說明-例句':'*1* 同心協力成功。\n*2* 第二句。',
            '辨識-同':'同','辨識-異':'異','辨識-例句':'同心協力 一字千金\n○ ㄨ 大家  齊心努力。\n○\nㄨ ○ 正確例句',
            '近義成語':'甲、乙、、甲','反義成語':'丙、丁','參考詞語':'參甲、參乙'})
    rows.extend([
        {'字詞名':'首尾','單字':'首尾','成語':'首尾','釋義':'"1. 首尾\n[名]\n單一\n[動]\n1. 尾"','解釋':'尾ㄨㄟˇ','辭條別名':'別甲'},
        {'字詞名':'空釋','單字':'空釋','成語':'空釋','釋義':'','解釋':'','典源注解':'_x000D_','主條成語／非主條成語':'非主條成語'},
        {'字詞名':'','單字':'','成語':'','釋義':'Skip this row'},
    ])
    return rows


def generate(destination):
    destination.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((ROOT/'baseline/cases.json').read_text())['moe_rows']
    cases=[]
    for name,rows in [('baseline',baseline),('extended',extended_rows())]:
        file=destination/(name+'.xlsx');workbook(file,rows);cases.append({'name':name,'file':file})
    for name,row,kind,code in [
        ('no-headwords',{'irrelevant':'value'},'moe_revised','malformed_source'),
        ('newline-key',{'字詞名':'bad\nkey'},'moe_revised','unrepresentable_source'),
        ('nonascii-image',{'字詞名':'字','釋義':'&圖.png;'},'moe_revised','unsupported_policy'),
        ('nonascii-number',{'字詞名':'字','多音排序':'٢'},'moe_concise','unsupported_policy'),
    ]:
        file=destination/(name+'.xlsx');workbook(file,[row]);cases.append({'name':name,'file':file,'kind':kind,'refusal':code})
    return cases


def oracle(file,kind,output):
    plugin=load_plugins()[kind];plugin.convert(str(file),str(output),'utf-8',lambda _:None,lambda _:None)
    return parse_txt(output.read_bytes())
