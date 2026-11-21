"""Recompute recipe/digest consistency of the source-bound Mac IO report.

The reviewer has the report, not the user's dictionary/export files or successful
Rust test stdout. File publication/cleanup and full wire decoding were checked
by the exact-source-bound harness; this is not a second inspection of those files.
"""
import hashlib
import json
from pathlib import Path
from large_io_oracle import ordered,row,digest,json_line
from m2_large_io import METADATA

def require(ok,message):
    if not ok:raise AssertionError(message)
def stream_hash(chunks):
    h=hashlib.sha256();n=0
    for b in chunks:h.update(b);n+=len(b)
    return {'bytes':n,'sha256':h.hexdigest()}
def review(r):
    require(r['status']=='m2_larger_packing_export_first_gate_passed_runtime_integration_pending' and r['stage']=='complete','Large IO batch incomplete')
    require(not r['M2_complete'] and not r['production_readiness'] and not r['RSS_is_OS_limit'] and r['native_readers']=='NOT_REQUESTED','Large IO scope expanded')
    require(r['RSS_observation_target_bytes']==384*1024*1024,'RSS observation threshold differs')
    steps=r['steps'];by={s['name']:s for s in steps};checks={c['case']:c for c in r['checks']}
    require(len(steps)==len(by)==50 and len(checks)==len(r['checks'])==10,'Large IO command/check inventory differs')
    require([(s['name'],s['returncode']) for s in steps[:3]]==[('refresh-large-io',0),('large-io-tests',0),('build-large-io',0)],'Rust command receipts differ')
    bad={**{'limit-'+n:'limit_exceeded' for n in ['records','decoded_bytes','entry_bytes','plan_charge','input_bytes','output_bytes']},'limits-cannot-grow':'invalid_input','bad-json':'invalid_input','bad-utf8':'invalid_encoding','missing-lf':'invalid_input','missing-text':'invalid_input','nul':'invalid_input','unknown-style':'invalid_input','over-entry':'limit_exceeded','resource-escape':'unsafe_path','resource-absolute':'invalid_input','resource-symlink':'io','metadata-override':'invalid_input','existing':'destination_exists',**{'cancel-'+p:'cancelled' for p in ['input_snapshot','load_records','builder_entries','encode_dictionary','encoded_dictionary','verify_records','publish_file']},**{'cancel-export-'+p:'cancelled' for p in ['export_records','publish_file']},**{'txt-refuse-'+n:'unrepresentable_source' for n in ['key-newline','delimiter-body','cr-body']}}
    success={'pack-utf8','repack-utf8','export_jsonl-utf8','export_txt-utf8','pack-utf16','repack-utf16','export_jsonl-utf16','export_txt-utf16','pack-mdd','pack-boundary',*('pack-'+n for n in ['key-newline','delimiter-body','cr-body']),*('json-preserve-'+n for n in ['key-newline','delimiter-body','cr-body'])}
    require(set(by)==set(bad)|success|{s['name'] for s in steps[:3]},'Large IO case names differ')
    sources={};max_rss=0
    for name,s in by.items():
        if name in bad:
            require(s['returncode']==1 and s['reply']['status']=='failed' and s['reply']['error']['code']==bad[name] and 'file_sha256' not in s,'Typed refusal differs')
            if name.startswith('cancel-'):require(s['request']['cancel_phase']==name.removeprefix('cancel-export-') if name.startswith('cancel-export-') else s['request']['cancel_phase']==name.removeprefix('cancel-'),'Cancellation checkpoint differs')
        elif name in success:
            require(s['returncode']==0 and s['reply']['status']=='succeeded','Successful publication receipt differs');request=s['request']['request'];summary=s['reply']['summary'];require(summary['profile']=='large-dictionary-io-v1' and summary['operation']==request['operation'] and summary['source_sha256']==s['input_sha256'],'Source/profile/operation binding differs');sources[request['destination']]=s['file_sha256']
        else:continue
        require(0<s['peak_RSS_bytes']<=384*1024*1024,'RSS outside provisional observation threshold');max_rss=max(max_rss,s['peak_RSS_bytes'])
    for name in success:
        s=by[name];request=s['request']['request']
        if request['source'] in sources:require(s['input_sha256']==sources[request['source']],'Pipeline file hash link differs')
    count=65536;rows={k:ordered(count,k) for k in ['mdx','mdd']};expected={k:digest(v) for k,v in rows.items()};manifest_hash={}
    manifest_hash['mdx']=stream_hash(json_line(*row(i,'mdx')) for i in range(count))['sha256']
    manifest_hash['mdd']=stream_hash(json.dumps({'key':row(i,'mdd')[0],'file':'empty.bin' if i==3 else 'data.bin'},ensure_ascii=False,separators=(',',':')).encode()+b'\n' for i in range(count))['sha256']
    def summary(name,want):
        value=by[name]['reply']['summary'];require({k:value[k] for k in want}==want,'Reported record count/bytes/framing differ from recipe');return value
    wire_count=0;export_hashes=0
    def wire(name,case,kind,want):
        nonlocal wire_count
        value=summary(name,want);c=checks[case];a=c['structural_audit'];require(c['wire_record_digest']==want and c['file_sha256']==by[name]['file_sha256']==a['sha256']==a['sha256_after'],'Wire/audit file identity differs');require(a['status']=='structural_audit_passed' and a['file']==case and a['records']==want['records'] and a['size_bytes']==value['file_bytes'],'Structural audit outcome differs');require(all(value['metadata'][k]==v for k,v in a['header'].items()),'Audit and receipt header differ')
        metadata={**METADATA,'stylesheet':''} if kind=='mdd' else METADATA
        require(by[name]['request']['request']['metadata']==metadata,'Requested metadata profile differs')
        for k,v in {'Title':metadata['title'],'Description':metadata['description'],'StyleSheet':metadata['stylesheet'],**metadata['extra'],'KeyCaseSensitive':'No','StripKey':'No'}.items():require(value['metadata'].get(k)==v,'Preserved metadata differs')
        if kind=='mdx':
            unit=2 if value['metadata']['Encoding']=='UTF-16' else 1
            recipe=rows['mdx'] if want['records']==count else [('boundary',b'x'*(1024*1024))]
            encoded=sum(len(data.decode().encode('utf-16le' if unit==2 else 'utf-8'))+unit for _,data in recipe)
            require(a['uncompressed_record_bytes']==encoded and a['records_without_terminal_null']==0,'Encoded MDX payload extent differs')
            require(a['duplicate_headwords']==(1 if want['records']==count else 0) and a['empty_bodies']==(1 if want['records']==count else 0) and a['style_markers']==(count-1 if want['records']==count else 0),'Definition/duplicate audit counters differ')
        else:require(a['uncompressed_record_bytes']==want['payload_bytes'],'Binary payload extent differs')
        require(a['key_blocks']>0 and a['record_blocks']>0,'Missing dictionary blocks');wire_count+=want['records'];return value
    for encoding in ['utf8','utf16']:
        packed=wire('pack-'+encoding,'large-'+encoding+'.mdx','mdx',expected['mdx']);require(by['pack-'+encoding]['input_sha256']==manifest_hash['mdx'],'Original MDX JSONL recipe hash differs')
        for txt in [False,True]:
            name=('export_txt-' if txt else 'export_jsonl-')+encoding;case=encoding+('.txt' if txt else '.jsonl');value=summary(name,expected['mdx']);want=stream_hash(k.encode()+b'\n'+data+b'\n</>\n' if txt else json_line(k,data) for k,data in rows['mdx']);require(checks[case]['independent_export_bytes']==want and by[name]['file_sha256']==want['sha256'] and value['file_bytes']==want['bytes'],'Export bytes/hash differ from independent recipe');require(value['metadata']==packed['metadata'],'Export metadata differs');export_hashes+=1
        wire('repack-'+encoding,'repacked-'+encoding+'.mdx','mdx',expected['mdx'])
    wire('pack-mdd','large.mdd','mdd',expected['mdd']);require(by['pack-mdd']['input_sha256']==manifest_hash['mdd'],'Original MDD JSONL recipe hash differs')
    boundary=digest([('boundary',b'x'*(1024*1024))]);wire('pack-boundary','boundary.mdx','mdx',boundary)
    require(by['pack-boundary']['input_sha256']==hashlib.sha256(json_line('boundary',b'x'*(1024*1024))).hexdigest(),'Boundary source recipe differs')
    for label,key,body in [('key-newline','two\nlines','body'),('delimiter-body','key','first\n</>\nlast'),('cr-body','key','a\rb')]:
        want=digest([(key,body.encode())]);a=summary('pack-'+label,want);b=summary('json-preserve-'+label,want);require(a['metadata']==b['metadata'],'Special JSON export metadata differs');require(by['json-preserve-'+label]['file_sha256']==hashlib.sha256(json_line(key,body.encode())).hexdigest(),'Special JSON export bytes differ');export_hashes+=1
    require(by['cancel-export-export_records']['request']['cancel_after']==10,'Mid-export cancellation receipt differs')
    return {'process_cases':47,'successful_publications':len(success),'expected_refusals':len(bad),'wire_records_recomputed':wire_count,'export_file_hashes_recomputed':export_hashes,'large_MDX_records_each_encoding':count,'MDD_resources':count,'boundary_definition_bytes':1048576,'max_observed_RSS_bytes':max_rss,'max_export_RSS_bytes':max(s['peak_RSS_bytes'] for n,s in by.items() if n.startswith('export_')),'review':'reported recipe digests and export hashes recomputed; successful Rust stdout and user output files not attached; cleanup/full wire checks represented by exact-source-bound harness'}
if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
