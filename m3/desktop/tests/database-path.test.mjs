import test from 'node:test';
import assert from 'node:assert/strict';
import {databaseOutputPath} from '../src/database-path.ts';
test('database outputs have the selected suffix and preserve the entered name',()=>{
  assert.equal(databaseOutputPath('/tmp/字','txt_to_db'),'/tmp/字.db');
  assert.equal(databaseOutputPath('/tmp/dict','mdx_to_db'),'/tmp/dict.db');
  assert.equal(databaseOutputPath('/tmp/dict','db_to_mdx'),'/tmp/dict.mdx');
  assert.equal(databaseOutputPath('/tmp/dict.MDX','db_to_mdx'),'/tmp/dict.MDX');
  assert.equal(databaseOutputPath('/tmp/字','db_to_jsonl'),'/tmp/字.jsonl');
  assert.equal(databaseOutputPath('/tmp/dict.JSONL','db_to_jsonl'),'/tmp/dict.JSONL');
  assert.equal(databaseOutputPath('/tmp/name.v2','db_to_jsonl'),'/tmp/name.v2.jsonl');
  assert.equal(databaseOutputPath('/tmp/dict.DB','txt_to_db'),'/tmp/dict.DB');
  assert.equal(databaseOutputPath('C:\\output','db_to_txt'),'C:\\output.txt');
  assert.equal(databaseOutputPath('/tmp/name.v2','db_to_txt'),'/tmp/name.v2.txt');
  assert.equal(databaseOutputPath('','db_to_txt'),'');
  assert.equal(databaseOutputPath('/tmp/','txt_to_db'),'');
});
