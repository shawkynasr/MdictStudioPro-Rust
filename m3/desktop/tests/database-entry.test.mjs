import test from 'node:test';
import assert from 'node:assert/strict';
import {entryCopyRequest,entryDeleteRequest,entryAddRequest} from '../src/database-entry.ts';
const hash='a'.repeat(64);
test('definition edit targets exact row ID without relying on headword or JS number precision',()=>{
  for(const rowid of ['7','-2','0','9007199254740993','9223372036854775807']) {
    const row={rowid,key:'字',text:'before'};
    const r=entryCopyRequest('in.db','out.db',hash,row,'edited\r\n\0');
    assert.equal(r.request.rowid,rowid);assert.equal(r.request.expected_source_sha256,hash);
    assert.equal(r.request.text,'edited\r\n\0');assert.equal(row.text,'before');
    assert.equal('key' in r.request,false);
  }
  assert.equal(entryCopyRequest('in','out',hash,{rowid:'1',key:'a',text:'old'},'').request.text,'');
});
test('entry editor refuses stale identities and oversized UTF-8 commands before releasing snapshot',()=>{
  for(const rowid of ['+7','07','-0','9223372036854775808'])assert.throws(()=>entryCopyRequest('in','out',hash,{rowid,key:'a',text:'old'},'x'));
  const row={rowid:'1',key:'a',text:'old'};
  assert.throws(()=>entryCopyRequest('in','in',hash,row,'x'));
  assert.throws(()=>entryCopyRequest('in','out','stale',row,'x'));
  assert.throws(()=>entryCopyRequest('in','out',hash,row,'字'.repeat(2731)));
  assert.throws(()=>entryCopyRequest('in','out',hash,row,'\ud800'));
  assert.throws(()=>entryCopyRequest('x'.repeat(65000),'out',hash,row,'x'.repeat(8192)));
});

test('optional headword edits preserve literal text and reject invalid UTF-8 boundaries',()=>{
  const row={rowid:'2',key:'字',text:'second'};
  for(const key of ['字',' renamed مرحبا 字 %_*? ','😀'.repeat(1024)]) {
    const r=entryCopyRequest('in','out',hash,row,row.text,key);
    assert.equal(r.request.key,key);assert.equal(r.request.text,'second');assert.equal(r.request.rowid,'2');
    assert.deepEqual(row,{rowid:'2',key:'字',text:'second'});
  }
  for(const key of ['', '</>', 'a\n', 'a\r', 'a\0', '\ud800', '😀'.repeat(1025)])
    assert.throws(()=>entryCopyRequest('in','out',hash,row,row.text,key));
});

test('delete request targets one exact row without transmitting large definitions or edits',()=>{
  const row={rowid:'9007199254740993',key:'字',text:'x'.repeat(9000)};
  assert.deepEqual(entryDeleteRequest('in','out',hash,row),{kind:'database',request:{operation:'db_delete_entry',source:'in',destination:'out',expected_source_sha256:hash,rowid:row.rowid}});
  assert.equal(row.text.length,9000);
  for(const rowid of ['+7','07','-0','9223372036854775808'])assert.throws(()=>entryDeleteRequest('in','out',hash,{...row,rowid}));
  assert.throws(()=>entryDeleteRequest('in','in',hash,row));
  assert.throws(()=>entryDeleteRequest('in','out','stale',row));
  assert.throws(()=>entryDeleteRequest('x'.repeat(66000),'out',hash,row));
});

test('addition is explicit, literal and independent of any selected source row',()=>{
  for(const [key,text] of [['duplicate','`1`new'],[' 字 مرحبا %_*? ',''],['😀'.repeat(1024),'x'.repeat(8192)]]) {
    assert.deepEqual(entryAddRequest('in','out',hash,key,text),{kind:'database',request:{operation:'db_add_entry',source:'in',destination:'out',expected_source_sha256:hash,key,text}});
  }
  for(const key of ['', '</>', 'a\n', 'a\r', 'a\0', '\ud800', '😀'.repeat(1025)])assert.throws(()=>entryAddRequest('in','out',hash,key,''));
  assert.throws(()=>entryAddRequest('in','out',hash,'new','x'.repeat(8193)));
  assert.throws(()=>entryAddRequest('in','out',hash,'new','\ud800'));
  assert.throws(()=>entryAddRequest('in','in',hash,'new',''));
  assert.throws(()=>entryAddRequest('in','out','stale','new',''));
  assert.throws(()=>entryAddRequest('x'.repeat(66000),'out',hash,'new',''));
});
