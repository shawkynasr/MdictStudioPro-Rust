import test from 'node:test';
import assert from 'node:assert/strict';
import {databasePreviewInput} from '../src/database-preview.ts';
import {expandStylesheet} from '../src/preview.ts';

test('database HTML previews use stored numeric styles without changing source',()=>{
  const source='`2`blue <b>字 العربية</b>';
  const metadata={Format:'Html',StyleSheet:'2\n<span style="color:blue">\n</span>\n'};
  const input=databasePreviewInput(source,metadata);
  assert.equal(input.text,source);
  assert.equal(expandStylesheet(input.text,input.sheet),'<span style="color:blue">blue <b>字 العربية</b></span>');
  assert.equal(metadata.StyleSheet,'2\n<span style="color:blue">\n</span>\n');
  assert.deepEqual(databasePreviewInput('',metadata),{text:'',sheet:metadata.StyleSheet});
});

test('stored plain text cannot acquire HTML semantics or numeric styles',()=>{
  const source='</pre><script>bad()</script>&amp;\n`2`literal';
  const input=databasePreviewInput(source,{FORMAT:'Text',STYLESHEET:'2\n<b>\n</b>\n'});
  assert.equal(input.sheet,'');
  assert.equal(input.text,'<pre>&lt;/pre&gt;&lt;script&gt;bad()&lt;/script&gt;&amp;amp;\n`2`literal</pre>');
  assert.deepEqual(databasePreviewInput('<b>HTML</b>'),{text:'<b>HTML</b>',sheet:''});
});
