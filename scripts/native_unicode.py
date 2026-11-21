"""Stage only hash-qualified Unicode dictionaries and a copyable native checklist.

Reuses integrated-out; no Cargo, dictionary building or native app launch.
"""
import argparse
from collections import Counter
import csv
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
from patched_interop import ROOT,require,read_python
from real_corpus import file_hash
from integrated_casing import fixture,expected_lookup,LEGACY,MODERN

EXACT=['ΟΣ','ος','οσ','duplicate','İ','i\u0307','é','e\u0301','Ａ','𐐀','꟎','꟏','A꟎Σ']
OBSERVE=['οΣ','Ος','aΣ','a꟏Σ','a?b','missing-policy']


def read_reference(path):
    # run() logs stdout then a literal STDERR separator. Never accept a
    # truncated JSON object, a second JSON result or trailing stdout chatter.
    text=path.read_text(encoding='utf-8');result,end=json.JSONDecoder().raw_decode(text)
    require(text[end:].strip()=='STDERR:','Unexpected reference log suffix; do not treat raw logs as a general IPC protocol')
    return result


def markers(rows):
    return [re.fullmatch(r'<p>([^<]+)</p>',r['text']).group(1) for r in rows]


def checklist(rows,norm):
    result=[]
    for query in EXACT:
        matches=[r for r in rows if r['key']==query];require(matches,f'Checklist raw key absent: {query}')
        result.append({'kind':'stored definition access','query':query,'codepoints':' '.join(f'U+{ord(c):04X}' for c in query),
            'required_markers':markers(matches),'adapter_reference':markers(expected_lookup(rows,query,norm))})
    for query in OBSERVE:
        result.append({'kind':'reader behavior observation','query':query,'codepoints':' '.join(f'U+{ord(c):04X}' for c in query),
            'required_markers':[],'adapter_reference':markers(expected_lookup(rows,query,norm))})
    return result


def write_checklists(stage,cases):
    with (stage/'checklist.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['folder','file','check_kind','query','codepoints','required_stored_markers','studio_adapter_reference_only','MDict_actual','GoldenDict_actual'])
        for case in cases:
            for row in case['checks']:writer.writerow([case['folder'],case['file'],row['kind'],row['query'],row['codepoints'],' | '.join(row['required_markers']),
                ' | '.join(row['adapter_reference']) or 'NO ENTRY','',''])
    parts=['<!doctype html><meta charset="utf-8"><title>Unicode native checks</title>',
        '<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;color:#18212d}table{border-collapse:collapse;width:100%;margin-bottom:40px}th,td{border:1px solid #ccd4df;padding:10px;text-align:left;vertical-align:top}th{background:#eef2f7}input{font:20px system-ui;width:12em;max-width:100%;padding:5px}code{font-size:13px}small{color:#536171}</style>',
        '<h1>Native Unicode compatibility</h1><p>Import one numbered folder at a time. Start with Unicode16 UTF-8, then UTF-16. Test Unicode17 comparison files afterward. Keep the other folders out of the reader group.</p>',
        '<p>Click a query box and copy it exactly. Code points distinguish visually similar text. Unsupported font glyphs are separate from missing dictionary content: identify the PINNED/DUP payload marker.</p>',
        '<p><b>Stored definition access:</b> the listed markers must remain accessible. Extra case-grouped definitions are allowed. For duplicate, check DUP_01 through DUP_08. Greek ΟΣ has two distinct definitions.</p>',
        '<p><b>Reader behavior observation:</b> record what the native reader returns. The studio adapter result is a reference, not a universal native-reader requirement. In particular, native readers may ignore the custom casing policy tags. Distinguish real results from approximate suggestions.</p>',
        '<p>Restart each reader and reopen representative entries. Record any crash, inaccessible stored marker, or changed result after restart in checklist.csv. If something fails, include the exact folder, query/code points and visible markers.</p>']
    for case in cases:
        parts.append('<h2>'+html.escape(case['folder'])+'</h2><p><code>'+html.escape(case['file'])+'</code></p><table><tr><th>Check</th><th>Copy query</th><th>Code points</th><th>Required stored markers</th><th>Studio reference only</th></tr>')
        for row in case['checks']:
            parts.append('<tr><td>'+html.escape(row['kind'])+'</td><td><input readonly dir="auto" onfocus="this.select()" value="'+html.escape(row['query'],quote=True)+'"></td><td><code>'+html.escape(row['codepoints'])+'</code></td><td>'+html.escape(', '.join(row['required_markers']) or 'Record actual behavior')+'</td><td>'+html.escape(', '.join(row['adapter_reference']) or 'NO ENTRY')+'</td></tr>')
        parts.append('</table>')
    (stage/'checklist.html').write_text('\n'.join(parts),encoding='utf-8')


def prepare(source,out):
    evidence=ROOT/'docs/evidence/integrated-casing-user-run/integrated-casing-report.json'
    require(file_hash(source/'integrated-casing-report.json')==file_hash(evidence),'Select the exact qualified integrated-out report')
    report=json.loads(evidence.read_text(encoding='utf-8'))
    for path,expected in report['source_sha256'].items():require(file_hash(ROOT/path)==expected,f'Qualified source changed: {path}')
    prior=json.loads((ROOT/'docs/evidence/unicode-version-user-run/unicode-profile-report.json').read_text(encoding='utf-8'))
    expected_rows,queries=fixture(prior['lowercase_mapping']['differences'])
    reference=read_reference(source/'reference.log')
    require(reference['scalar_scan_skipped'] is True,'Unexpected original normalization reference scope')
    normal={LEGACY:{r['word']:r['legacy16'] for r in reference['contexts']},MODERN:{r['word']:r['modern17'] for r in reference['contexts']}}
    require(all(k in normal[p] for p in normal for k in [r['key'] for r in expected_rows]+queries),'Incomplete normalization reference')
    out.mkdir(parents=True,exist_ok=False);cases=[]
    with tempfile.TemporaryDirectory(prefix='staging-',dir=out) as tmp:
        stage=Path(tmp);ready=stage/'ready';ready.mkdir()
        for number,(profile,encoding) in enumerate([(LEGACY,'utf8'),(LEGACY,'utf16'),(MODERN,'utf8'),(MODERN,'utf16')],1):
            name=f'{profile}-{encoding}';check=report['checks'][name];path=source/name/'integrated.mdx'
            require(check['status']=='passed' and file_hash(path)==check['sha256'],'Qualified dictionary bytes changed')
            physical=read_python(path,'mdx');require(Counter(physical)==Counter((r['key'],r['text']) for r in expected_rows),'Independent native input inventory differs')
            rows=[{'key':k,'text':v} for k,v in physical]
            require(rows==sorted(expected_rows,key=lambda r:normal[profile][r['key']]),'Native input physical order differs from reference')
            label='unicode16' if profile==LEGACY else 'unicode17-comparison';folder=f'{number:02d}-{label}-{encoding}';file=f'09-{label}-{encoding}.mdx'
            dest=ready/folder;dest.mkdir();shutil.copyfile(path,dest/file)
            require(file_hash(dest/file)==check['sha256'],'Staged dictionary bytes differ')
            cases.append({'folder':folder,'file':file,'profile':profile,'encoding':encoding,'sha256':check['sha256'],'records':len(rows),'checks':checklist(rows,normal[profile])})
        write_checklists(stage,cases)
        with (stage/'full-inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f);writer.writerow(['query','codepoints','payload_marker'])
            for row in expected_rows:writer.writerow([row['key'],' '.join(f'U+{ord(c):04X}' for c in row['key']),markers([row])[0]])
        manifest={'status':'native_unicode_inputs_prepared_native_untested','source_report_sha256':file_hash(evidence),'dictionaries_rebuilt':False,
            'native_apps_launched':False,'native_observations':'PENDING','cases':cases}
        (stage/'native-unicode-report.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        # Publish only after all four files and checklists have been validated.
        for name in ['checklist.html','checklist.csv','full-inventory.csv','native-unicode-report.json']:(stage/name).rename(out/name)
        ready.rename(out/'ready')
    return out/'checklist.html'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'integrated-out');p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    try:result=prepare(args.source.resolve(),args.output.resolve());print(f'Ready: {result}');return 0
    except Exception as error:print(f'Native staging failed: {error}');return 1


if __name__=='__main__':raise SystemExit(main())
