import test from 'node:test';
import assert from 'node:assert/strict';
import { resourcePath, resourceCandidates, expandStylesheet, rewriteCSS, aborted, CHILD_CSP } from '../src/preview.ts';
test('resource paths resolve CSS relatives and reject schemes, escapes and malformed encodings',()=>{
  assert.equal(resourcePath('../images/a.png','css/main.css'),'images/a.png');
  assert.equal(resourcePath('\\fonts\\amiri-regular.ttf'),'fonts/amiri-regular.ttf');
  assert.equal(resourcePath('images/a%20b.png?v=2#x'),'images/a b.png');
  assert.equal(resourcePath('/images/字.png','css/main.css'),'images/字.png');
  for(const path of ['../../escape','https://example.com/a','//evil/a','file:///secret','tauri://localhost/a','javascript:alert(1)','%2e%2e/a','a%00b','%FF','data:image/svg+xml,x'])assert.equal(resourcePath(path),null,path);
  assert.deepEqual(resourceCandidates('images/a.png'),['\\images\\a.png','images/a.png','/images/a.png','images\\a.png']);
});
test('numeric stylesheet preserves unmarked text, marker boundaries and unknown markers',()=>{
  const sheet='1\n<b>\n</b>\n2\n<span style="color:blue">\n</span>\n';
  assert.equal(expandStylesheet('plain `1`bold`2`blue`99`unknown',sheet),'plain <b>bold</b><span style="color:blue">blue</span>`99`unknown');
  assert.equal(expandStylesheet('`1``2`blue',sheet),'<b></b><span style="color:blue">blue</span>');
  assert.equal(expandStylesheet('a`2`b',''),'a`2`b');
  assert.equal(expandStylesheet('`256`x`02`y','256\n<b>\n</b>\n02\n<i>\n</i>\n'),'<b>x</b><i>y</i>');
  for(const sheet of ['1\n<b>','x\na\nb','1\na\nb\n1\nc\nd'])assert.throws(()=>expandStylesheet('x',sheet));
  assert.throws(()=>expandStylesheet('x'.repeat(131073),''));
  assert.throws(()=>expandStylesheet('字'.repeat(43691),''));
  assert.throws(()=>expandStylesheet('`1`x'.repeat(2000),'1\n'+'a'.repeat(1000)+'\nb'));
});
test('CSS rewrites quoted and unquoted URLs relative to stylesheet and strips imports',async()=>{
  const urls=[],warnings=[];
  const result=await rewriteCSS('@import "other.css";/*comment*/a{background:url(../images/a.png)}@font-face{src:url("../fonts/a.ttf")}b{background:url(https://bad/x)}','css/main.css',async(url,base)=>{urls.push([url,base]);return resourcePath(url,base)?'data:allowed':'';},w=>warnings.push(w));
  assert.deepEqual(urls,[['../images/a.png','css/main.css'],['../fonts/a.ttf','css/main.css'],['https://bad/x','css/main.css']]);
  assert.ok(!result.includes('@import'));assert.ok(!result.includes('https://bad'));assert.ok(result.includes('url("data:allowed")'));assert.equal(warnings.length,1);
});
test('child CSP denies scripts, network, embedding, base changes and forms',()=>{
  for(const directive of ["default-src 'none'","script-src 'none'","connect-src 'none'","frame-src 'none'","object-src 'none'","base-uri 'none'","form-action 'none'"])assert.ok(CHILD_CSP.includes(directive));
  assert.ok(CHILD_CSP.includes('font-src data:'));assert.ok(!CHILD_CSP.includes('unsafe-eval'));
  const controller=new AbortController();controller.abort();assert.throws(()=>aborted(controller.signal),{name:'AbortError'});
});
