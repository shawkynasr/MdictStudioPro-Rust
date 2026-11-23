import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {textSizePreference,readabilityLabel} from '../src/readability.ts';
import {suggestedDictionaryPath} from '../src/output-path.ts';

test('stored text size accepts supported choices and defaults safely for old or invalid preferences',()=>{
  for(const size of ['standard','large','larger'])assert.equal(textSizePreference(size),size);
  for(const value of [undefined,null,'100px','compact',{},3])assert.equal(textSizePreference(value),'standard');
  for(const locale of ['en','zh','ar'])for(const key of ['textSize','standard','large','larger'])assert.ok(readabilityLabel(locale,key));
});

test('rebuilding exported text suggests a separate MDX without losing Unicode or parent directories',()=>{
  assert.equal(suggestedDictionaryPath('/data/词典.txt','mdx'),'/data/词典-rebuilt.mdx');
  assert.equal(suggestedDictionaryPath('C:\\data\\字.JSONL','mdx'),'C:\\data\\字-rebuilt.mdx');
  assert.equal(suggestedDictionaryPath('/data/dict.v2.txt','mdx'),'/data/dict.v2-rebuilt.mdx');
  assert.equal(suggestedDictionaryPath('/data/resources','mdd'),'/data/resources-rebuilt.mdd');
  assert.equal(suggestedDictionaryPath('','mdx'),'dictionary.mdx');
});

test('secondary UI text meets normal-text contrast on every light and dark surface',()=>{
  const css=readFileSync(new URL('../src/style.css',import.meta.url),'utf8');
  const linear=c=>{c=parseInt(c,16)/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;};
  const lum=hex=>.2126*linear(hex.slice(0,2))+.7152*linear(hex.slice(2,4))+.0722*linear(hex.slice(4,6));
  const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
  for(const selector of [':root','html[data-theme=dark]']) {
    const rule=css.slice(css.indexOf(selector+'{')).split('}')[0];
    const color=name=>{const value=rule.match(new RegExp('--'+name+':#([0-9a-f]{3,6})(?:;|$)'))?.[1];assert.ok(value,name);return value.length===3?[...value].map(c=>c+c).join(''):value;};
    for(const surface of ['window','sidebar','card','soft']) {
      for(const text of ['ink','muted'])assert.ok(ratio(color(text),color(surface))>=4.5,`${selector} ${text} on ${surface}`);
    }
  }
});
