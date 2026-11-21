"""First larger owned-builder packing and streaming MDX export qualification."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import traceback
from m2_sizing import ROOT,require,sha,timed_run,peak_rss,RSS_TARGET,CommandTimeout
from large_io_lock import MANIFEST,LOCK,check_lock
from large_io_oracle import row,ordered,digest,wire_rows,attrs,compare_export,json_line
from v2_audit import audit

def protected_sources():
    r=json.loads((ROOT/'docs/evidence/m2-extraction-jobs-user-run/m2-extraction-jobs-report.json').read_text());expected={**r['protected_source_sha256'],**r['source_sha256']}
    for n,h in expected.items():require(sha(ROOT/n)==h,f'Previously qualified source changed: {n}')
    return expected
def fingerprints(include_lock=True):
    directory=ROOT/'m2/large-io';paths=[p for p in directory.rglob('*') if p.is_file() and 'target' not in p.relative_to(directory).parts and p.suffix in {'.rs','.toml','.lock'} and (include_lock or p.name!='Cargo.lock')]
    paths += [ROOT/'scripts'/n for n in ['large_io_lock.py','large_io_oracle.py','m2_large_io.py','test_m2_large_io.py']]
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
METADATA={'title':'Larger 字 العربية & "title"','description':'Line one\nLine two\tأهلاً','stylesheet':'1\n<span style="color:blue">\n</span>\n','extra':{'Copyright':'Example\n2026','CustomNote':'保持 & حفظ'}}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(exist_ok=False)
    report={'status':'m2_large_io_failed','stage':'preflight','M2_complete':False,'production_readiness':False,'python':sys.version,'platform':platform.platform(),'steps':[],'checks':[],'native_readers':'NOT_REQUESTED','scope':'32 MiB aggregate owned-builder input; disk-spooled JSONL packing, per-record MDX exports, no shared runtime integration','RSS_observation_target_bytes':RSS_TARGET,'RSS_is_OS_limit':False}
    try:
        report['protected_source_sha256']=protected_sources();report['source_sha256']=fingerprints(False);report['seed_lock_sha256']=sha(ROOT/LOCK);check_lock();cargo=shutil.which('cargo');require(cargo is not None,'Run on Rust-enabled Mac');system=platform.system();require(system in {'Darwin','Linux'},'This gate targets Unix resource descriptors');require(Path('/usr/bin/time').is_file(),'Require process RSS measurement')
        def build(name,command):
            report['stage']=name;print(f'Running {name}',flush=True);r=timed_run(command);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode};report['steps'].append(step)
            if r.returncode:step['failure_log_tail']=log[-64000:]
            require(r.returncode==0,f'{name} failed; embedded log tail available')
        build('refresh-large-io',[cargo,'clean','--offline','--manifest-path',MANIFEST,'--package','studio-large-io'])
        try:build('large-io-tests',[cargo,'test','--offline','--manifest-path',MANIFEST,'--workspace'])
        finally:report['dependency_lock_contents']=(ROOT/LOCK).read_text();report['dependency_packages']=check_lock();report['source_sha256'][LOCK]=sha(ROOT/LOCK)
        build('build-large-io',[cargo,'build','--locked','--offline','--manifest-path',MANIFEST,'--bin','studio-large-io'])
        binary=ROOT/'m2/large-io/target/debug/studio-large-io';report['binary_sha256']=sha(binary);inputs=out/'inputs';inputs.mkdir();outputs=out/'outputs';outputs.mkdir();scratch=out/'private-scratch';scratch.mkdir();resources=inputs/'resources';resources.mkdir();(resources/'data.bin').write_bytes(bytes(range(256)));(resources/'empty.bin').write_bytes(b'');(resources/'link.bin').symlink_to('data.bin');env=dict(os.environ,TMPDIR=str(scratch))
        def invoke(name,request,code=None,tighten=None,cancel=None,after=0):
            report['stage']=name;print(f'Checking {name}',flush=True);q=out/(name+'-request.json');envelope={'request':{k:str(v) if isinstance(v,Path) else v for k,v in request.items()}}
            if tighten is not None:envelope['tighten']=tighten
            if cancel is not None:envelope.update(cancel_phase=cancel,cancel_after=after)
            q.write_text(json.dumps(envelope,ensure_ascii=False));source=Path(request['source']);source_before=sha(source);destination=Path(request['destination']);before=set(outputs.iterdir());old=sha(destination) if destination.is_file() else None;command=['/usr/bin/time','-l' if system=='Darwin' else '-v',str(binary),str(q)];r=timed_run(command,env);log=r.stdout+'\nSTDERR:\n'+r.stderr;(out/(name+'.log')).write_text(log);step={'name':name,'returncode':r.returncode,'request':envelope,'input_sha256':source_before};report['steps'].append(step);require(sha(source)==source_before,'Operation changed public input bytes')
            if code is None:
                if r.returncode:step['failure_log_tail']=log[-64000:]
                require(r.returncode==0,f'{name} failed; embedded log tail available');value=json.loads(r.stdout);require(value['status']=='succeeded' and destination.is_file(),'Missing successful file publication');require(set(outputs.iterdir())==before|{destination},'Publication staging residue');step['file_sha256']=sha(destination)
            else:
                require(r.returncode!=0 and not r.stdout.strip(),'Expected typed refusal without success stdout');values=[json.loads(line) for line in r.stderr.splitlines() if line.startswith('{')];require(len(values)==1,'Expected one typed error reply');value=values[0];require(value['status']=='failed' and value['error']['code']==code,f'{name} expected {code}: {value}');require(set(outputs.iterdir())==before,'Refusal left destination/staging');require((sha(destination) if destination.is_file() else None)==old,'Refusal changed existing destination')
            step['reply']=value;step['peak_RSS_bytes']=peak_rss(r.stderr,system);require(step['peak_RSS_bytes']<=RSS_TARGET,'Provisional RSS observation threshold exceeded');require(not list(scratch.iterdir()),'Private snapshot/spool residue');return value.get('summary')
        def pack_request(kind,source,destination,encoding='utf8',metadata=None):
            req={'operation':'pack_'+kind,'source':source,'destination':destination,'metadata':metadata or METADATA}
            if kind=='mdx':req['encoding']=encoding
            else:req.update(resource_root=resources,metadata={**METADATA,'stylesheet':''})
            return req
        def verify_file(path,kind,expected,summary,metadata):
            require(summary['profile']=='large-dictionary-io-v1','Wrong IO profile');got=digest(wire_rows(path,kind));require(got==digest(expected),'Independent wire records differ');require(all(summary[k]==v for k,v in got.items()),'Thin receipt differs from wire records');require(summary['file_bytes']==path.stat().st_size,'Receipt file size differs');header=attrs(path);require(header==summary['metadata'],'Wire and summary metadata differ')
            for k,v in {'Title':metadata['title'],'Description':metadata['description'],'StyleSheet':metadata['stylesheet'],**metadata['extra'],'KeyCaseSensitive':'No','StripKey':'No'}.items():require(header.get(k)==v,f'Wire metadata differs: {k}')
            structural=audit(path);require(structural['status']=='structural_audit_passed','Independent checksum/section audit failed')
            if kind=='mdd':require(len(structural['resources'])==got['records'],'Audit MDD count differs');structural.pop('resources')
            report['checks'].append({'case':path.name,'wire_record_digest':got,'file_sha256':sha(path),'structural_audit':structural})
        count=65536;report['stage']='fixtures'
        manifests={}
        for kind in ['mdx','mdd']:
            path=inputs/(kind+'.jsonl')
            with path.open('wb') as f:
                for i in range(count):
                    key,data=row(i,kind)
                    if kind=='mdx':f.write(json_line(key,data))
                    else:f.write(json.dumps({'key':key,'file':'data.bin' if data else 'empty.bin'},ensure_ascii=False,separators=(',',':')).encode()+b'\n')
            manifests[kind]=path
        for encoding in ['utf8','utf16']:
            path=outputs/('large-'+encoding+'.mdx');req=pack_request('mdx',manifests['mdx'],path,encoding);summary=invoke('pack-'+encoding,req);require(summary['source_sha256']==sha(manifests['mdx']),'Manifest snapshot hash differs');expected=ordered(count,'mdx');verify_file(path,'mdx',expected,summary,METADATA)
            for txt in [False,True]:
                exported=outputs/(encoding+('.txt' if txt else '.jsonl'));op='export_txt' if txt else 'export_jsonl';s=invoke(op+'-'+encoding,{'operation':op,'source':path,'destination':exported});require(all(s[k]==v for k,v in digest(expected).items()),'Export digest differs');require(s['source_sha256']==sha(path) and s['metadata']==summary['metadata'],'Export source metadata/hash differs');file_check=compare_export(exported,expected,txt);report['checks'].append({'case':exported.name,'independent_export_bytes':file_check})
            repacked=outputs/('repacked-'+encoding+'.mdx');s=invoke('repack-'+encoding,pack_request('mdx',outputs/(encoding+'.jsonl'),repacked,encoding));require(s['framed_records_sha256']==summary['framed_records_sha256'],'Export/repack physical digest differs');verify_file(repacked,'mdx',expected,s,METADATA)
        path=outputs/'large.mdd';s=invoke('pack-mdd',pack_request('mdd',manifests['mdd'],path));verify_file(path,'mdd',ordered(count,'mdd'),s,{**METADATA,'stylesheet':''})
        boundary=inputs/'boundary.jsonl';boundary.write_bytes(json_line('boundary',b'x'*(1024*1024)));s=invoke('pack-boundary',pack_request('mdx',boundary,outputs/'boundary.mdx','utf16'));verify_file(outputs/'boundary.mdx','mdx',[('boundary',b'x'*(1024*1024))],s,METADATA)
        small=inputs/'small.jsonl';small.write_bytes(json_line('one',b'body')+json_line('two',b''))
        for field,value in [('records',1),('decoded_bytes',2),('entry_bytes',1),('plan_charge',1),('input_bytes',1),('output_bytes',8)]:invoke('limit-'+field,pack_request('mdx',small,outputs/('limit-'+field)),code='limit_exceeded',tighten={field:value})
        invoke('limits-cannot-grow',pack_request('mdx',small,outputs/'grow'),code='invalid_input',tighten={'decoded_bytes':32*1024*1024+1})
        bads=[('bad-json',b'{\n','invalid_input'),('bad-utf8',b'\xff\n','invalid_encoding'),('missing-lf',b'{"key":"a","text":"b"}','invalid_input'),('missing-text',b'{"key":"a"}\n','invalid_input'),('nul',json_line('a',b'a\0b'),'invalid_input'),('unknown-style',json_line('a',b'`9`undefined'),'invalid_input'),('over-entry',json_line('a',b'x'*(1024*1024+1)),'limit_exceeded')]
        for name,data,code in bads:
            src=inputs/name;src.write_bytes(data);invoke(name,pack_request('mdx',src,outputs/name),code=code)
        for name in ['../escape','/data.bin','link.bin']:
            label={'../escape':'escape','/data.bin':'absolute','link.bin':'symlink'}[name];src=inputs/(label+'.jsonl');src.write_text(json.dumps({'key':'a','file':name})+'\n');invoke('resource-'+label,pack_request('mdd',src,outputs/label),code='unsafe_path' if label=='escape' else 'invalid_input' if label=='absolute' else 'io')
        override={**METADATA,'extra':{'StripKey':'Yes'}};invoke('metadata-override',pack_request('mdx',small,outputs/'override',metadata=override),code='invalid_input')
        existing=outputs/'existing';existing.write_bytes(b'KEEP');invoke('existing',pack_request('mdx',small,existing),code='destination_exists')
        for phase in ['input_snapshot','load_records','builder_entries','encode_dictionary','encoded_dictionary','verify_records','publish_file']:invoke('cancel-'+phase,pack_request('mdx',small,outputs/('cancel-'+phase)),code='cancelled',cancel=phase)
        for phase in ['export_records','publish_file']:invoke('cancel-export-'+phase,{'operation':'export_jsonl','source':outputs/'large-utf8.mdx','destination':outputs/('cancel-export-'+phase)},code='cancelled',cancel=phase,after=10 if phase=='export_records' else 0)
        for label,key,body in [('key-newline','two\nlines','body'),('delimiter-body','key','first\n</>\nlast'),('cr-body','key','a\rb')]:
            src=inputs/(label+'.jsonl');src.write_bytes(json_line(key,body.encode()));dictionary=outputs/(label+'.mdx');invoke('pack-'+label,pack_request('mdx',src,dictionary));invoke('txt-refuse-'+label,{'operation':'export_txt','source':dictionary,'destination':outputs/(label+'.txt')},code='unrepresentable_source');exported=outputs/(label+'.jsonl');invoke('json-preserve-'+label,{'operation':'export_jsonl','source':dictionary,'destination':exported});compare_export(exported,[(key,body.encode())])
        require(protected_sources()==report['protected_source_sha256'] and fingerprints()==report['source_sha256'],'Sources changed during qualification');check_lock();report['status']='m2_larger_packing_export_first_gate_passed_runtime_integration_pending';report['stage']='complete'
    except (Exception,KeyboardInterrupt) as e:
        report['error']=f'{type(e).__name__}: {e}';report['python_traceback']=traceback.format_exc()
        if isinstance(e,CommandTimeout):report['timed_out_command_output_tail']=e.output_tail
    path=out/'m2-large-io-report.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(f"{report['status']}: {path}");return int(report['status']=='m2_large_io_failed')
if __name__=='__main__':raise SystemExit(main())
