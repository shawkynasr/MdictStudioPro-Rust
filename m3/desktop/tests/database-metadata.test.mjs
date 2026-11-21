import test from 'node:test';
import assert from 'node:assert/strict';
import {metadataCopyRequest,editorStylesheet} from '../src/database-metadata.ts';
const hash='a'.repeat(64),metadata={Title:'before',Description:'original',StyleSheet:'2\n<b>\n</b>\n'};
test('metadata copy edits only selected fields and binds the snapshot hash',()=>{
  const r=metadataCopyRequest('source.db','copy.db',hash,metadata,{title:''});
  assert.equal(r.request.expected_source_sha256,hash);
  assert.deepEqual(r.request.edits,{title:''});
  assert.equal(metadata.Title,'before');assert.equal(metadata.Description,'original');
  assert.throws(()=>metadataCopyRequest('source.db','source.db',hash,metadata,{title:'x'}));
  assert.throws(()=>metadataCopyRequest('source.db','copy.db',hash,null,{title:'x'}));
  assert.throws(()=>metadataCopyRequest('source.db','copy.db','stale',metadata,{title:'x'}));
});
test('metadata byte and transport bounds include multibyte text and JSON escapes',()=>{
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{}));
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{title:'字'.repeat(1366)}));
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{description:'x'.repeat(8193)}));
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{description:'bad\0'}));
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{title:'\ud800'}));
  assert.throws(()=>metadataCopyRequest('x'.repeat(64000),'out',hash,metadata,{title:'x'.repeat(4096)}));
  const r=metadataCopyRequest('in','out',hash,metadata,{title:'字 / مرحبا & <title>',description:'new\nworld'});
  assert.equal(r.request.edits.description,'new\nworld');
});
test('stylesheet-only replacement is explicit and preserves exact LF text',()=>{
  const style='2\n<span style="color:#008000">\n</span>\n';
  const r=metadataCopyRequest('in','out',hash,metadata,{stylesheet:style});
  assert.deepEqual(r.request.edits,{stylesheet:style});
  assert.equal(metadata.StyleSheet,'2\n<b>\n</b>\n');
  assert.deepEqual(metadataCopyRequest('in','out',hash,metadata,{stylesheet:''}).request.edits,{stylesheet:''});
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{stylesheet:'x'.repeat(16385)}));
});

test('pasted styles without a final newline produce the exact canonical fixture',()=>{
  const style='1\n<strong>\n</strong>\n2\n<span style="color:#008000">\n</span>\n';
  for(const pasted of [style,style.slice(0,-1),style.replaceAll('\n','\r\n'),style.slice(0,-1).replaceAll('\n','\r')]) {
    const edits={stylesheet:pasted};
    assert.equal(metadataCopyRequest('in','out',hash,metadata,edits).request.edits.stylesheet,style);
    assert.equal(edits.stylesheet,pasted,'Draft must not be mutated');
  }
  assert.equal(editorStylesheet('2\n <b> \n\n'),'2\n <b> \n\n','Whitespace and empty closing fragment are preserved');
  assert.equal(editorStylesheet(''),'');
});
test('editor preflight rejects broken triplets and preserves command caps after normalization',()=>{
  for(const pasted of ['2\n<b>','2\n<b>\n','x\n<b>\n</b>','2\n<b>\n</b>\n2\n<i>\n</i>','2\n<b>\t\n</b>']) {
    assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{stylesheet:pasted}));
  }
  const atCap='2\n'+'x'.repeat(16376)+'\n</b>\n';
  assert.equal(metadataCopyRequest('in','out',hash,metadata,{stylesheet:atCap.slice(0,-1)}).request.edits.stylesheet,atCap);
  assert.throws(()=>metadataCopyRequest('in','out',hash,metadata,{stylesheet:'2\n'+'x'.repeat(16377)+'\n</b>'}));
});
