import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePluginCatalog,pluginDefaults,setPluginField,pluginFormValues} from '../src/plugin-catalog.ts';
const field=(key,type,value,choices=[])=>({key,type,label:key,default:value,choices});
const catalog=()=>({version:1,classes:[{class_name:'Demo',name:'字 مرحبا',description:'fixture',schema_error:null,fields:[field('prefix','string','字'),field('uppercase','boolean',false),field('count','number',2),field('mode','choice','a',['a','b'])]}]});
test('discovered scalar forms roundtrip options without removing manual keys',()=>{
  const c=parsePluginCatalog(catalog()).classes[0];
  let options=pluginDefaults(c);
  assert.equal(pluginFormValues(options,c).prefix,'字');
  options=setPluginField(options,c.fields[0],'مرحبا');
  options=setPluginField(options,c.fields[1],true);
  options=setPluginField(options,c.fields[2],3.25);
  options=setPluginField(options,c.fields[3],'b');
  assert.deepEqual(JSON.parse(options),{prefix:'مرحبا',uppercase:true,count:3.25,mode:'b'});
  assert.equal(JSON.parse(setPluginField('{"unknown":true}',c.fields[0],'x')).unknown,true);
  assert.equal(pluginFormValues('{"count":"broken"}',c),null);
});
test('catalog limits, duplicate keys, mismatched types, unsupported fields and choices are refused',()=>{
  for(const mutate of [v=>v.version=2,v=>v.extra=true,v=>v.classes.push(v.classes[0]),v=>v.classes[0].fields.push(v.classes[0].fields[0]),v=>v.classes[0].fields[1].default='true',v=>v.classes[0].fields[3].choices=['z'],v=>v.classes[0].fields[2].default=Infinity,v=>v.classes[0].fields[0].required=true,v=>v.classes[0].schema_error='unsupported',v=>v.classes=Array(17).fill(v.classes[0])]){
    const v=catalog();mutate(v);assert.throws(()=>parsePluginCatalog(v));
  }
  const c=parsePluginCatalog(catalog()).classes[0];
  assert.throws(()=>setPluginField('{}',c.fields[3],'z'));
  assert.throws(()=>setPluginField('{}',c.fields[2],NaN));
  assert.throws(()=>setPluginField('{}',c.fields[0],'字'.repeat(683)));
});
test('schema fallback and empty catalog are valid; defaults cannot pollute prototypes',()=>{
  assert.deepEqual(parsePluginCatalog({version:1,classes:[]}).classes,[]);
  const v=catalog();v.classes[0].fields=[];v.classes[0].schema_error='unsupported';assert.ok(parsePluginCatalog(v).classes[0].schema_error);
  const c=catalog().classes[0];c.fields=[field('__proto__','string','safe')];
  const checked=parsePluginCatalog({version:1,classes:[c]}).classes[0];
  assert.equal(JSON.parse(pluginDefaults(checked)).__proto__,'safe');
  assert.equal(JSON.parse(setPluginField('{}',checked.fields[0],'value')).__proto__,'value');
  assert.equal({}.safe,undefined);
});
