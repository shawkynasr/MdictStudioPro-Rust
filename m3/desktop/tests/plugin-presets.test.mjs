import test from 'node:test';
import assert from 'node:assert/strict';
import {encodePluginPresets,decodePluginPresets,savePluginPreset,loadPluginPreset,deletePluginPreset} from '../src/plugin-options.ts';
const preset=(name='Demo')=>({name,python:'/venv/bin/python',plugin:'/plugins/demo.py',class_name:'OptionsPlugin',options:'{"prefix":"字 مرحبا","uppercase":true}'});
test('presets survive serialization and loading never restores trust or input/output',()=>{
  const original=savePluginPreset([],preset());const restored=decodePluginPresets(encodePluginPresets(original));
  assert.deepEqual(restored,original);const loaded=loadPluginPreset(restored,'Demo');
  assert.equal(loaded.trusted,false);assert.equal('source' in loaded,false);assert.equal('destination' in loaded,false);
  assert.equal('trusted' in JSON.parse(encodePluginPresets(restored)).items[0],false);
  loaded.options='{}';assert.notEqual(restored[0].options,'{}');
});
test('save-new refuses duplicate names; explicit update supports rename and deletion is isolated',()=>{
  const original=savePluginPreset([],preset());
  assert.throws(()=>savePluginPreset(original,preset()));
  const renamed=savePluginPreset(original,{...preset('Other'),options:'{}'},'Demo');
  assert.equal(original[0].name,'Demo');assert.equal(renamed[0].name,'Other');
  const both=savePluginPreset(renamed,preset());
  assert.throws(()=>savePluginPreset(both,preset('Other'),'Demo'));
  assert.throws(()=>savePluginPreset(both,preset(),'Missing'));
  assert.deepEqual(deletePluginPreset(both,'Demo'),renamed);assert.equal(both.length,2);
});
test('bad storage, injected trust and unsupported versions are refused without a write',()=>{
  for(const raw of ['', 'broken','null','[]','{}',JSON.stringify({version:2,items:[]}),JSON.stringify({version:1,items:[{...preset(),trusted:true}]}),JSON.stringify({version:1,items:[{...preset(),source:'/input'}]})])assert.throws(()=>decodePluginPresets(raw));
  assert.deepEqual(decodePluginPresets(null),[]);
});
test('field, count, Unicode and byte limits are enforced on saved and loaded presets',()=>{
  const eight=Array.from({length:8},(_,i)=>preset('p'+i));assert.equal(decodePluginPresets(encodePluginPresets(eight)).length,8);
  assert.throws(()=>savePluginPreset(eight,preset('ninth')));
  for(const bad of [{...preset(),name:'字'.repeat(65)},{...preset(),python:'x'.repeat(4097)},{...preset(),plugin:'bad\0path'},{...preset(),class_name:'A.b'},{...preset(),options:'{"nested":{}}'},{...preset(),name:'\ud800'}])assert.throws(()=>encodePluginPresets([bad]));
  const big=eight.map(p=>({...p,python:'x'.repeat(4096),plugin:'y'.repeat(4096)}));assert.throws(()=>encodePluginPresets(big));
});
