"""Recompute reported extraction file hashes from independent byte recipes.

This checks source-bound report consistency; actual output files are on the
user's Mac and are not inspected by this reviewer.
"""
import hashlib
import json
from pathlib import Path
import struct

def require(ok,message):
    if not ok:raise AssertionError(message)
def recipe_hash(size,seed):
    pattern=bytes((seed+i)%256 for i in range(256));h=hashlib.sha256();block=pattern*4096
    while size>=len(block):h.update(block);size-=len(block)
    h.update(block[:size]);return h.digest()
def review(report):
    require(report['status']=='m2_streaming_MDD_extraction_passed_larger_integration_pending' and report['stage']=='complete','Extraction batch did not complete')
    require(not report['M2_complete'] and not report['production_readiness'] and report['native_readers']=='NOT_REQUESTED','Do not expand extraction scope')
    steps=report['steps'];checks=report['checks'];step={s['name']:s for s in steps}
    require(len(steps)==33 and len(step)==33 and len(checks)==30 and len({c['case'] for c in checks})==30,'Extraction command/case inventory differs')
    require([(s['name'],s['returncode']) for s in steps[:3]]==[('refresh-extract-artifacts',0),('stream-extract-tests',0),('build-stream-extract',0)],'Extraction Rust command receipts differ')
    positive={c['case']:c for c in checks if c['status']=='streamed_files_verified'};negative={c['case']:c for c in checks if c['status']=='expected_refusal'}
    require(set(positive)=={'cross-block','large-resource','plain-blocks','many-files'} and len(negative)==26,'Extraction outcome inventory differs')
    refused={**{n:'unsafe_path' for n in ['traversal','device','unc']},**{n:'path_collision' for n in ['case-alias','duplicate','prefix-conflict']},**{n:'limit_exceeded' for n in ['count-cap','per-resource-cap','output-cap','plan-cap','node-cap','file-cap','working-cap','block-cap','bad-record_declared_decoded']},**{'cancel-'+p:'cancelled' for p in ['snapshot','plan_paths','copy_resource','verify_file','publish_directory']},'bad-key_block_checksum':'integrity','bad-record_block_checksum':'integrity','bad-truncated':'engine','v3':'unsupported_policy','encrypted':'unsupported_policy','existing-destination':'destination_exists'}
    require({n:c['error']['code'] for n,c in negative.items()}==refused,'Expected typed refusals differ')
    for c in checks:
        s=step[c['case']];require(s['returncode']==(0 if c['case'] in positive else 1),'Extraction case exit differs')
        require(0<c['peak_RSS_bytes']==s['peak_RSS_bytes']<=384*1024*1024,'Extraction RSS observation differs')
    files_count=0;total_payload=0
    for name,c in positive.items():
        if name=='many-files':recipes=[(f'files/r{i:05d}.bin',256,i) for i in range(4096)];blocks=16
        else:
            size,blocks={'cross-block':(200000,4),'large-resource':(32*1024*1024+7,513),'plain-blocks':(8*1024*1024+3,129)}[name]
            recipes=[('\\assets\\prefix.bin',17,11),('assets/字-مرحبا-𠀀.bin',size,37),('empty.bin',0,0)]
        files={};framed=hashlib.sha256()
        for ordinal,(key,size,seed) in enumerate(recipes):
            digest=recipe_hash(size,seed);relative=key.replace('\\','/').removeprefix('/');files[relative]={'bytes':size,'sha256':digest.hex()};raw=key.encode();framed.update(struct.pack('<QQ',ordinal,len(raw))+raw+struct.pack('<Q',size)+digest)
        require(c['files']==files and c['record_blocks']==blocks,'Reported file paths/bytes/hashes or block count differ from recipes')
        require(c['actual']['status']=='published','Missing publication receipt');r=c['actual']['receipt'];size=sum(size for _,size,_ in recipes)
        require(r['source_sha256']==c['source_sha256'] and r['profile']=='mdd-stream-extract-v1','Source/profile binding differs')
        require(r['resources']==len(recipes) and r['payload_bytes']==size and r['largest_resource_bytes']==max(size for _,size,_ in recipes) and r['framed_resources_sha256']==framed.hexdigest(),'Extraction summary/framed digest differs')
        require(r['materialized_record_limit']==r['locator_bytes']==0 and r['parser_peak_bytes']<=r['parser_budget_bytes']==64*1024*1024,'Record materialization/locator/parser accounting differs')
        require(r['plan_charge']<=16*1024*1024 and r['planned_nodes']==(4097 if name=='many-files' else 4),'Plan budget/node count differs')
        files_count+=len(files);total_payload+=size
    maximum=max(c['peak_RSS_bytes'] for c in checks);require(maximum==4792320 and files_count==4105 and total_payload==43191677,'Extraction review totals differ')
    return {'successful_extractions':4,'expected_refusals':26,'file_hashes_recomputed':files_count,'payload_bytes':total_payload,'largest_resource_bytes':33554439,'max_observed_RSS_bytes':maximum,'review':'reported file hashes/framed receipts recomputed; Rust and user output files not executed/inspected by reviewer'}

if __name__=='__main__':
    import sys
    print(json.dumps(review(json.loads(Path(sys.argv[1]).read_text())),indent=2))
