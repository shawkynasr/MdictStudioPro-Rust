import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseBrowser} from '../src/database-reader.ts';

function server() {
  const calls=[];let id=0,reader=null,job=null,reply=null,error=null,held=false;
  const page={source_sha256:'snapshot',rows:[{rowid:'4',key:'apple',text:'second'}],total:3,offset:2,next_offset:null};
  const send=async c=>{
    calls.push(c);
    switch(c.action) {
      case 'database_open':reader='reader-'+(++id);job='open-'+id;reply={operation:'opened',value:{}};error=null;return {reader_id:reader,job_id:job};
      case 'database_query':assert.equal(c.reader_id,reader);job='page-'+(++id);reply={operation:'page',value:page};error=null;return {job_id:job};
      case 'database_cancel':error={code:'cancelled',message:'cancelled'};reply=null;held=false;if(job.startsWith('open'))reader=null;return null;
      case 'database_poll':return {reader_id:reader,state:reader?'ready':'closed',job_id:job,job_state:held?'running':error?'cancelled':'succeeded',result_available:!held&&!!reply,error:held?null:error};
      case 'database_take':{const r=reply;reply=null;return r;}
      case 'database_forget':assert.equal(c.job_id,job);job=null;return null;
      case 'database_close':assert.equal(c.reader_id,reader);reader=null;job=null;reply=null;return null;
      default:throw Error('unexpected command '+c.action);
    }
  };
  return {send,calls,page,hold:()=>{held=true;},release:()=>{held=false;}};
}
const query={query:null,prefix:false,offset:0,limit:2};
test('search and pagination reuse a handle; source switch closes it before opening another',async()=>{
  const s=server(),b=new DatabaseBrowser(s.send,async()=>{});
  assert.deepEqual(await b.load('one.db',query),s.page);
  await b.load('one.db',{...query,query:'app',prefix:true,offset:2});
  assert.equal(s.calls.filter(c=>c.action==='database_open').length,1);
  await b.load('two.db',query);
  const changes=s.calls.filter(c=>['database_open','database_close'].includes(c.action));
  assert.deepEqual(changes.map(c=>c.action),['database_open','database_close','database_open']);
  assert.equal(s.calls.filter(c=>c.action==='database_forget').length,5);
  await b.close();await b.close();
  assert.equal(s.calls.filter(c=>c.action==='database_close').length,2);
});
test('an open response arriving after source invalidation is drained and closed',async()=>{
  const s=server();let release,seen;
  const started=new Promise(r=>seen=r);const gate=new Promise(r=>release=r);
  const b=new DatabaseBrowser(async c=>{const value=await s.send(c);if(c.action==='database_open'){seen();await gate;}return value;},async()=>{});
  const load=b.load('old.db',query);await started;const close=b.close();release();
  assert.equal(await load,null);await close;
  assert.equal(s.calls.filter(c=>c.action==='database_cancel').length,1);
  assert.equal(s.calls.filter(c=>c.action==='database_forget').length,1);
  assert.equal(s.calls.filter(c=>c.action==='database_query').length,0);
  await b.load('new.db',query);await b.close();
});
test('a page arriving after a changed query cannot become the displayed result',async()=>{
  const s=server();let reached,release;let delay=false;
  const started=new Promise(r=>reached=r);const gate=new Promise(r=>release=r);
  const b=new DatabaseBrowser(async c=>{const value=await s.send(c);if(delay&&c.action==='database_query'){reached();await gate;}return value;},async()=>{});
  await b.load('one.db',query);delay=true;
  const old=b.load('one.db',query);await started;await b.invalidate();release();
  assert.equal(await old,null);delay=false;
  assert.deepEqual(await b.load('one.db',{...query,query:'app',prefix:true}),s.page);
  assert.equal(s.calls.filter(c=>c.action==='database_open').length,1);
  await b.close();
});
test('cancelled page can be followed by a successful page on the same handle',async()=>{
  const s=server();let reached;
  const started=new Promise(r=>reached=r);
  const b=new DatabaseBrowser(s.send,async()=>{reached();await new Promise(r=>setTimeout(r,0));});
  await b.load('one.db',query);s.hold();
  const old=b.load('one.db',query);await started;await b.cancel();
  await assert.rejects(old,e=>e.code==='cancelled');
  assert.deepEqual(await b.load('one.db',query),s.page);
  assert.equal(s.calls.filter(c=>c.action==='database_open').length,1);await b.close();
});
test('cancelling a stale delayed submit does not cancel the newer queued load',async()=>{
  const s=server();let reached,release,first=true;
  const started=new Promise(r=>reached=r);const gate=new Promise(r=>release=r);
  const b=new DatabaseBrowser(async c=>{const value=await s.send(c);if(first&&c.action==='database_open'){first=false;reached();await gate;}return value;},async()=>{});
  const old=b.load('old.db',query);await started;
  const newer=b.load('new.db',query);release();
  assert.equal(await old,null);assert.deepEqual(await newer,s.page);await b.close();
});
test('letter-matching policy travels with each query without reopening the snapshot',async()=>{
  const s=server(),b=new DatabaseBrowser(s.send,async()=>{});
  await b.load('one.db',{...query,query:'aPp',prefix:true,matching:'literal'});
  await b.load('one.db',{...query,query:'aPp',prefix:true,matching:'unicode16_lower'});
  const requests=s.calls.filter(c=>c.action==='database_query');
  assert.deepEqual(requests.map(c=>c.request.matching),['literal','unicode16_lower']);
  assert.equal(requests[0].reader_id,requests[1].reader_id);
  assert.equal(s.calls.filter(c=>c.action==='database_open').length,1);await b.close();
});
test('wildcard syntax is an explicit query option and does not change literal queries',async()=>{
  const s=server(),b=new DatabaseBrowser(s.send,async()=>{});
  await b.load('one.db',{...query,query:'a?b',prefix:false,wildcard:true,matching:'unicode16_lower'});
  await b.load('one.db',{...query,query:'a?b',prefix:false,wildcard:false,matching:'literal'});
  await b.load('one.db',{...query,query:String.raw`a\?b`,prefix:false,wildcard:true,matching:'literal'});
  const requests=s.calls.filter(c=>c.action==='database_query');
  assert.deepEqual(requests.map(c=>c.request.wildcard),[true,false,true]);
  assert.equal(requests[2].request.query,String.raw`a\?b`);
  assert.equal(requests[0].request.query,'a?b');assert.equal(requests[0].reader_id,requests[1].reader_id);await b.close();
});
test('definition search keeps text and matching flags separate from headword modes',async()=>{
  const s=server(),b=new DatabaseBrowser(s.send,async()=>{});
  await b.load('one.db',{...query,query:'<div ? * % _',prefix:false,wildcard:false,definition:true,matching:'literal'});
  await b.load('one.db',{...query,query:'NEEDLE',prefix:false,wildcard:false,definition:true,matching:'unicode16_lower'});
  await b.load('one.db',{...query,query:'apple',prefix:false,definition:false});
  const requests=s.calls.filter(c=>c.action==='database_query');
  assert.deepEqual(requests.map(c=>c.request.definition),[true,true,false]);
  assert.equal(requests[0].request.query,'<div ? * % _');
  assert.equal(requests[1].request.matching,'unicode16_lower');
  assert.equal(s.calls.filter(c=>c.action==='database_open').length,1);await b.close();
});
