import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePluginFolder,folderChoices,selectFolderChoice} from '../src/plugin-folder.ts';
const converter=()=>({class_name:'Demo',name:'Repeated name',description:'字 مرحبا',fields:[],schema_error:null});
const entry=name=>({filename:name,source:'/plugins/'+name,plugin_sha256:'a'.repeat(64),catalog:{version:1,classes:[converter()]},error:null});
const fixture=()=>({profile:'trusted-python-folder-v1',folder:'/plugins',destination:'/output',ignored_entries:1,entries:[entry('a.py'),entry('b.py'),{filename:'broken.py',source:'/plugins/broken.py',plugin_sha256:null,catalog:null,error:{code:'engine',message:'fixture failure'}}]});
test('folder selections preserve duplicate display names and class identities across files',()=>{
  const parsed=parsePluginFolder(fixture());const choices=folderChoices(parsed);
  assert.equal(choices.length,2);assert.notEqual(choices[0].id,choices[1].id);
  assert.equal(selectFolderChoice(parsed,choices[1].id).entry.source,'/plugins/b.py');
  const again=parsePluginFolder(JSON.parse(JSON.stringify(parsed)));
  assert.deepEqual(folderChoices(again).map(c=>c.id),choices.map(c=>c.id));
  assert.equal(parsed.entries[2].error.message,'fixture failure');
  assert.throws(()=>selectFolderChoice(parsed,'not a discovered identity'));
});
test('folder catalogs reject escapes, duplicates, inconsistent error states and resource excess',()=>{
  for(const change of [v=>v.entries[0].source='/outside/a.py',v=>v.entries[0].filename='../a.py',v=>v.entries[0].filename='a\\b.py',v=>v.entries[0].filename='__init__.py',v=>v.entries.push(v.entries[0]),v=>v.entries[0].plugin_sha256=null,v=>v.entries[0].catalog=null,v=>v.entries[0].error={code:'engine',message:'bad'},v=>v.entries[0].catalog.classes.push(converter()),v=>v.ignored_entries=257,v=>v.ignored_entries='1',v=>v.entries[2].error.message='字'.repeat(683),v=>v.entries[0].catalog.classes[0].fields=[{key:'x',type:'file',default:'',choices:[],label:'file'}],v=>v.entries=Array(17).fill(entry('a.py'))]){
    const raw=fixture();change(raw);assert.throws(()=>parsePluginFolder(raw));
  }
});
test('empty and failed-only inventories are valid without a selectable converter',()=>{
  const raw=fixture();raw.entries=[];assert.deepEqual(folderChoices(parsePluginFolder(raw)),[]);
  raw.entries=[fixture().entries[2]];assert.deepEqual(folderChoices(parsePluginFolder(raw)),[]);
  raw.entries[0].error.message='x'.repeat(2048);assert.equal(parsePluginFolder(raw).entries.length,1);
});
test('aggregate catalog cap is enforced independently of individual metadata limits',()=>{
  const raw=fixture();raw.entries=Array.from({length:16},(_,i)=>{const e=entry(`file-${i}.py`);e.catalog.classes=Array.from({length:16},(_,j)=>({...converter(),class_name:`C${j}`,description:'x'.repeat(512)}));return e;});
  assert.ok(new TextEncoder().encode(JSON.stringify(raw)).length>131072);
  assert.throws(()=>parsePluginFolder(raw));
});
