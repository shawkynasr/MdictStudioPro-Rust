import test from 'node:test';
import assert from 'node:assert/strict';
import {exportFilePath,sourceParent,resourceFolderName,resourceDestination} from '../src/extract-path.ts';
test('MDX exports get exactly the selected TXT or JSONL suffix',()=>{
  assert.equal(exportFilePath('/tmp/dict','txt'),'/tmp/dict.txt');assert.equal(exportFilePath('/tmp/dict.MDX','jsonl'),'/tmp/dict.jsonl');assert.equal(exportFilePath('/tmp/dict.TXT','txt'),'/tmp/dict.TXT');assert.equal(exportFilePath('dict.v2','jsonl'),'dict.v2.jsonl');assert.equal(exportFilePath('/tmp/','txt'),'/tmp/');
});
test('resource destinations stay within one selected parent component',()=>{
  assert.equal(resourceDestination('/','资源'),'/资源');assert.equal(resourceDestination('/tmp/','dict_resources'),'/tmp/dict_resources');assert.equal(resourceDestination('C:\\','resources'),'C:\\resources');assert.equal(resourceDestination('\\\\server\\share\\','resources'),'\\\\server\\share\\resources');
  for(const name of ['','..','../escape','a/b','a\\b','CON','COM1.txt','bad.','bad ','x\0y','字'.repeat(86)])assert.equal(resourceDestination('/tmp',name),null,name);
  assert.equal(resourceDestination('','resources'),null);
});
test('MDD source names suggest bounded portable output directories',()=>{
  assert.equal(sourceParent('/dict/test.mdd'),'/dict/');assert.equal(sourceParent('C:\\test.mdd'),'C:\\');assert.equal(resourceFolderName('/dict/test.mdd'),'test_resources');assert.equal(resourceFolderName('bad:name.mdd'),'bad-name_resources');assert.ok(new TextEncoder().encode(resourceFolderName('字'.repeat(100)+'.mdd')).length<256);
});
