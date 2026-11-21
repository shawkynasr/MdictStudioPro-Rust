import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePluginOptions} from '../src/plugin-options.ts';
test('options preserve multilingual scalars and legacy empty input',()=>{
  assert.deepEqual(parsePluginOptions(''),{});
  assert.deepEqual(parsePluginOptions('{"prefix":"字 مرحبا","uppercase":true,"count":2}'),{prefix:'字 مرحبا',uppercase:true,count:2});
});
test('invalid objects, unsafe numbers, UTF-8 and scalar limits are refused',()=>{
  for(const input of ['[1]','null','false','broken','{"x":1e999}','{"x":9007199254740992}','{"x":null}','{"x":{}}','{"x":[]}','{"bad-key":true}',JSON.stringify({x:'字'.repeat(683)}),JSON.stringify({x:'\ud800'}),JSON.stringify(Object.fromEntries(Array.from({length:65},(_,i)=>['k'+i,true]))),JSON.stringify(Object.fromEntries(Array.from({length:5},(_,i)=>['k'+i,'x'.repeat(2048)])))])assert.throws(()=>parsePluginOptions(input));
});
