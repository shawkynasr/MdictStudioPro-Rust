import test from 'node:test';
import assert from 'node:assert/strict';
import {checkedPythonPath,pluginDrop,pluginOutputSelection,samePluginImport,importedPlugin} from '../src/plugin-simple.ts';
const cls=name=>({class_name:name,name:'Converter '+name,description:'fixture',fields:[{key:'uppercase',type:'boolean',label:'Uppercase',default:false,choices:[]}],schema_error:null});
const receipt=classes=>({kind:'python_probe',receipt:{profile:'trusted-python-probe-v1',plugin_sha256:'a'.repeat(64),catalog:{version:1,classes}}});
test('single-file drops select paths only and reject ambiguous batches',()=>{
  assert.deepEqual(pluginDrop(['/字/options.py']),{kind:'plugin',path:'/字/options.py'});
  assert.deepEqual(pluginDrop(['/data/source.txt']),{kind:'source',path:'/data/source.txt'});
  for(const paths of [[],['a.py','b.py'],[''],['a\0.py']])assert.throws(()=>pluginDrop(paths));
});
test('one converter selects itself with schema defaults; multiple converters require a choice',()=>{
  const one=importedPlugin(receipt([cls('Options')]));assert.equal(one.className,'Options');assert.deepEqual(JSON.parse(one.options),{uppercase:false});
  assert.equal(importedPlugin(receipt([cls('A'),cls('B')])).className,'');
  assert.equal(importedPlugin(receipt([])).className,'');
  for(const bad of [{kind:'python_inspection',receipt:{}},receipt([cls('A'),cls('A')]),{kind:'python_probe',receipt:{profile:'trusted-python-probe-v1',plugin_sha256:'wrong',catalog:{version:1,classes:[]}}}])assert.throws(()=>importedPlugin(bad));
});
test('late imports are invalidated even when the user switches A to B and back to A',()=>{
  const captured={python:'/python',plugin:'/a.py',revision:1};
  assert.equal(samePluginImport(captured,{...captured}),true);
  assert.equal(samePluginImport(captured,{...captured,plugin:'/b.py'}),false);
  assert.equal(samePluginImport(captured,{...captured,revision:3}),false);
  assert.equal(samePluginImport(captured,{...captured,python:'/other-python'}),false);
});
test('one save dialog maps to the existing no-clobber folder request and Python preference is bounded',()=>{
  assert.deepEqual(pluginOutputSelection('/Users/test/Downloads/result-2'),{parent:'/Users/test/Downloads/',folder:'result-2'});
  for(const path of ['/x/CON','/x/..','/x/','bare-name','/x/result?'])assert.throws(()=>pluginOutputSelection(path));
  assert.equal(checkedPythonPath('/project/.venv/bin/python'),'/project/.venv/bin/python');
  for(const path of [null,'','x\ny','x\0y','字'.repeat(1366),'\ud800'])assert.throws(()=>checkedPythonPath(path));
});
