"""Verify Rust TXT profiles and the first converter port against captured Python."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import unicodedata

from patched_interop import ROOT,require,verify_candidate_source,legacy_fixture_records,read_python
from m2_foundation import check_layout,fingerprints,sha
from v2_audit import audit

GOLDENS=['cc_cedict','moe_revised','moe_revised_wfg','moe_concise','moe_idioms','moe_mini']
PROFILES=['canonical_v1','legacy_body_span_v1']


def reference_rows(data,profile):
    require(profile in PROFILES,'Unknown TXT reference profile')
    # Reference only for LF/CRLF fixture records; preserve legacy raw body span.
    text=data.decode('utf-8').removeprefix('\ufeff')
    rows=legacy_fixture_records(text)
    if profile=='canonical_v1':
        rows=[(key,body.replace('\r\n','\n')[:-1]) for key,body in rows]
    return [{'key':key,'text':body} for key,body in rows]


def boundary_source():
    rows=[('alias','@@@LINK=字')]+[('duplicate',f'DUP_{i:02d}\n\nlast') for i in range(1,9)]
    rows += [('empty',''),('مرحبا','<b dir="rtl">أهلاً</b>'),('字','中文'),('𠀀','supplementary')]
    return ''.join(f'{key}\n{body}\n</>\n' for key,body in rows).encode('utf-8')


def extended_cedict():
    definitions=['see 傳|传[Zhuan4] (old) CL: 個|个[ge4]', 'x|字abc a||字 a|字| a|字[foo|]',
        '(old) (slang) (coll.) (archaic) (bird species of China) (idiom) (Tw) (vulgar)',
        '(Internet slang) (loanword) (computing) (math.) (chemistry) (medicine)',
        '(Chinese medicine) (botany) (Buddhism) (dialect) (Cantonese) (Taiwanese)',
        'i.e. e.g. fig. lit. CL: CL (abbr.)', 'one//two', '中文 العربية <b>raw HTML</b>',
        'A|字 B|字 CL|字 字|字[zi4]']
    rows=['# Extended synthetic CC-CEDICT oracle fixture']
    rows.extend(f'繁{i} 简{i} [nu:3 lu:4 OU3 LIU2 NV5 MA0] /{definition}/' for i,definition in enumerate(definitions))
    rows += ['字 字 [zi4] /first duplicate/','字 字 [zi4] /second duplicate/',
             '女\t女\t[nu:3]\t/woman/', '甲\u001c乙\u001c[jia3]\u001c/Python whitespace/',
             ' # stripped comment', 'invalid intentionally skipped', 'a a [a1]/missing required space/', '']
    return ('\n'.join(rows)+'\n').encode('utf-8')


def load_oracle():
    manifest=json.loads((ROOT/'baseline/source-manifest.json').read_text())
    for name in ['plugins/cccedict_plugin.py','base_plugin.py']:
        require(sha(ROOT/'baseline/legacy'/name)==manifest['files'][name],f'Captured oracle changed: {name}')
    sys.path.insert(0,str(ROOT/'baseline/legacy'))
    spec=importlib.util.spec_from_file_location('studio_cedict_oracle',ROOT/'baseline/legacy/plugins/cccedict_plugin.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.CCCEDICTPlugin()


def oracle_convert(plugin,source,destination):
    plugin.convert(str(source),str(destination),'utf-8',lambda _:None,lambda _:None)
    comments=[];primary=0;traditional=0;skipped=0
    # File iteration uses only universal LF/CRLF/CR newlines, like the plugin.
    with source.open(encoding='utf-8') as stream:
        for raw in stream:
            line=raw.strip()
            if not line:continue
            if line.startswith('#'):comments.append(line);continue
            match=plugin.line_pattern.match(line)
            if match:primary+=1;traditional+=int(match[1]!=match[2])
            else:skipped+=1
    return {'primary_entries':primary,'traditional_entries':traditional,'skipped_lines':skipped,'comments':comments}


def compare_bytes(expected,actual,diff_path):
    if expected==actual:return
    offset=next((i for i,(a,b) in enumerate(zip(expected,actual)) if a!=b),min(len(expected),len(actual)))
    diff={'first_different_byte':offset,'expected_bytes':len(expected),'actual_bytes':len(actual),
          'expected_context':expected[max(0,offset-120):offset+240].decode('utf-8','replace'),
          'actual_context':actual[max(0,offset-120):offset+240].decode('utf-8','replace')}
    diff_path.write_text(json.dumps(diff,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise AssertionError(f'Output bytes differ; return {diff_path.name}')


def source_fingerprints():
    result=fingerprints()
    names=['scripts/m2_text.py','baseline/cases.json','baseline/source-manifest.json',
           'baseline/legacy/plugins/cccedict_plugin.py','baseline/legacy/base_plugin.py']
    names += [f'baseline/expected/{name}.txt' for name in GOLDENS]
    for name in names:result[name]=sha(ROOT/name)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=False,exist_ok=False)
    report={'status':'m2_text_failed','M1':'complete_unchanged','M2_complete':False,
            'python':sys.version,'platform':platform.platform(),'steps':[],'checks':{},
            'native_readers':'NOT_REQUESTED','Rust_XLSX_converters_ported':False,
            'scope':'TXT profiles, UTF8 CC-CEDICT port and bounded TXT/MDX pipelines'}
    def run(label,command,parse=False,refusal=None):
        log=out/(label+'.log');print(f'Running {label}; log: {log}',flush=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='strict')
        log.write_text(result.stdout+'\nSTDERR:\n'+result.stderr,encoding='utf-8')
        step={'name':label,'returncode':result.returncode,'log':log.name};report['steps'].append(step)
        if refusal:
            require(result.returncode==1 and not result.stdout.strip(),f'{label} was not controlled; return {log.name}')
            error=json.loads(result.stderr.strip().splitlines()[-1]);require(error.get('status')=='failed' and error['error']['code']==refusal,f'{label} wrong refusal; return {log.name}')
            step['expected_refusal']=refusal;return None
        require(result.returncode==0,f'{label} failed; return {log.name}')
        return json.loads(result.stdout) if parse else None
    try:
        check_layout();report['source_sha256']=source_fingerprints()
        require(unicodedata.unidata_version=='16.0.0','Use the existing Python Unicode16 .venv for the converter oracle')
        require(importlib.metadata.version('mdict-utils')=='1.3.14','Use existing mdict-utils==1.3.14')
        verify_candidate_source(ROOT/'vendor/mdictlib-0.2.8-studio-sort-v6',6)
        cargo=shutil.which('cargo');require(cargo is not None,'Run on the Rust-enabled Mac')
        command=[cargo,'run','--locked','--manifest-path','m2/Cargo.toml','-p','studio-cli','--']
        run('text-tests',[cargo,'test','--locked','--manifest-path','m2/Cargo.toml','--workspace'])
        report['checks']['golden_txt']=[]
        for name in GOLDENS:
            source=ROOT/f'baseline/expected/{name}.txt';data=source.read_bytes()
            for profile in PROFILES:
                label=f'{name}-{profile}'
                read=run('read-'+label,command+['txt-read',str(source),profile],parse=True)
                expected=reference_rows(data,profile);require(read['rows']==expected,f'{label} key/body span mismatch')
                request=out/(label+'.json');request.write_text(json.dumps(expected,ensure_ascii=False),encoding='utf-8')
                destination=out/(label+'.txt');run('write-'+label,command+['txt-write',str(request),str(destination),profile],parse=True)
                compare_bytes(data,destination.read_bytes(),out/(label+'-diff.json'))
                report['checks']['golden_txt'].append({'converter_output':name,'profile':profile,'records':len(expected),'bytes_exact':True})
        source=out/'boundary.txt';source.write_bytes(boundary_source())
        crlf=out/'bom-crlf.txt';crlf.write_bytes(b'\xef\xbb\xbf'+boundary_source().replace(b'\n',b'\r\n'))
        for profile in PROFILES:
            read=run('crlf-'+profile,command+['txt-read',str(crlf),profile],parse=True)
            require(read['rows']==reference_rows(crlf.read_bytes(),profile),'BOM/CRLF profile behavior differs')
        report['checks']['pipelines']=[]
        for profile in PROFILES:
            expected=reference_rows(source.read_bytes(),profile)
            # These fixture keys are already in the frozen policy's physical order.
            for encoding in ['utf8','utf16']:
                label=profile+'-'+encoding;mdx=out/(label+'.mdx');exported=out/(label+'-export.txt')
                run('pack-'+label,command+['txt-pack',str(source),str(mdx),profile,encoding],parse=True)
                require(read_python(mdx,'mdx')==[(r['key'],r['text']) for r in expected],'TXT->MDX independent rows differ')
                require(audit(mdx)['status']=='structural_audit_passed','TXT->MDX wire audit failed')
                run('export-'+label,command+['txt-export',str(mdx),str(exported),profile],parse=True)
                compare_bytes(source.read_bytes(),exported.read_bytes(),out/(label+'-diff.json'))
                report['checks']['pipelines'].append({'profile':profile,'encoding':encoding,'records':len(expected),'independent_python_rows':'passed','wire_audit':'passed','export_bytes_exact':True,'mdx_sha256':sha(mdx)})
        plugin=load_oracle();report['checks']['cedict']=[]
        baseline=json.loads((ROOT/'baseline/cases.json').read_text())['cedict'].encode('utf-8')
        for name,data in [('baseline',baseline),('extended',extended_cedict())]:
            directory=out/('oracle-'+name);directory.mkdir();input_path=directory/'input.u8';input_path.write_bytes(data)
            oracle=directory/'python.txt';actual=directory/'rust.txt';metrics=oracle_convert(plugin,input_path,oracle)
            converted=run('cedict-'+name,command+['cedict',str(input_path),str(actual)],parse=True)
            compare_bytes(oracle.read_bytes(),actual.read_bytes(),out/(name+'-cedict-diff.json'))
            require(all(converted[k]==value for k,value in metrics.items()),'CC-CEDICT counters/comments differ')
            if name=='baseline':compare_bytes((ROOT/'baseline/expected/cc_cedict.txt').read_bytes(),actual.read_bytes(),out/'baseline-cedict-diff.json')
            require(input_path.read_bytes()==data,'Converter modified its source')
            report['checks']['cedict'].append({'fixture':name,'records':converted['entries'],'sha256':sha(actual),'oracle_bytes_exact':True,'metrics_exact':True})
        words=['nu:3 lu:4 hao3 ma5','LU:4 NV5 MA0 OU3 LIU2',' ma6 NÜ4 Nv5 vowel7 ',
               'A2 E3 O4 UI1 IU2 IOU3','ΟΣ2','ΟΣ5','A꟎Σ2','  nu:3  ','ng2 m2 r5','ABC9 u: test']
        probe=out/'pinyin.json';probe.write_text(json.dumps(words,ensure_ascii=False),encoding='utf-8')
        converted=run('pinyin',command+['cedict-pinyin',str(probe)],parse=True)
        require(converted['results']==[{'input':w,'output':plugin.convert_pinyin(w)} for w in words],'Pinyin oracle mismatch')
        report['checks']['pinyin_words']=len(words)
        for name,data,reason in [('invalid-utf8',b'a\n\xff\n</>\n','invalid_encoding'),('incomplete',b'a\nbody\n','malformed_source')]:
            bad=out/(name+'.txt');bad.write_bytes(data);run(name+'-refused',command+['txt-read',str(bad),'canonical_v1'],refusal=reason)
        bad=out/'legacy-no-lf.json';bad.write_text(json.dumps([{'key':'a','text':'no newline'}]),encoding='utf-8')
        rejected=out/'legacy-no-lf.txt';run('legacy-no-lf-refused',command+['txt-write',str(bad),str(rejected),'legacy_body_span_v1'],refusal='unrepresentable_source');require(not rejected.exists(),'Unrepresentable export was published')
        existing=out/'existing.txt';existing.write_bytes(b'unchanged');valid=out/'valid.json';valid.write_text('[{"key":"a","text":"body"}]',encoding='utf-8')
        run('existing-refused',command+['txt-write',str(valid),str(existing),'canonical_v1'],refusal='destination_exists');require(existing.read_bytes()==b'unchanged','Existing export was changed')
        probe=out/'unsupported-pinyin.json';probe.write_text('["ma٢"]',encoding='utf-8')
        run('nonascii-tone-refused',command+['cedict-pinyin',str(probe)],refusal='unsupported_policy')
        require(source_fingerprints()==report['source_sha256'],'Source, oracle or lock changed during run')
        report['status']='m2_text_and_cedict_passed_remaining_M2_work_pending'
    except (Exception,KeyboardInterrupt) as error:report['error']=f'{type(error).__name__}: {error}'
    destination=out/'m2-text-report.json';destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['status']}: {destination}",flush=True)
    return 0 if report['status']=='m2_text_and_cedict_passed_remaining_M2_work_pending' else 1


if __name__=='__main__':raise SystemExit(main())
