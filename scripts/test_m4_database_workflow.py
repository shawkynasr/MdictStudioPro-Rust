"""Test the combined oracle against tampered but self-consistent stage databases."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_m4_database_metadata import write
from verify_database_entry import inspect
from m4_database_workflow import verify_case,DESCRIPTION,EDITED,ADDED


def prepare(directory,label):
    fixture=json.loads((Path(__file__).resolve().parents[1]/'m3/fixtures/database-stylesheet.json').read_text())
    rows=[(r['key'],r['text']) for r in fixture['entries']]
    attrs={'Title':f'Combined workflow source · {label}','Description':fixture['description'],
           'Encoding':label,'StyleSheet':fixture['stylesheet'],'Format':'Html','Compact':'Yes'}
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'original.mdx').write_bytes(b'original-mdx');(directory/'rebuilt.mdx').write_bytes(b'rebuilt-mdx')
    write(directory/'dictionary.db',rows,attrs,sha(directory/'original.mdx'))
    final_attrs={**attrs,'Title':f'Combined database workflow · {label}','Description':DESCRIPTION}
    write(directory/'metadata.db',rows,final_attrs,sha(directory/'dictionary.db'))
    edited=rows.copy();edited[2]=('duplicate',EDITED)
    write(directory/'definition.db',edited,final_attrs,sha(directory/'metadata.db'))
    renamed=edited.copy();renamed[4]=('renamed 字',rows[4][1])
    write(directory/'renamed.db',renamed,final_attrs,sha(directory/'definition.db'))
    added=renamed+[('duplicate',ADDED)]
    write(directory/'added.db',added,final_attrs,sha(directory/'renamed.db'))
    final=added.copy();del final[5]
    write(directory/'final.db',final,final_attrs,sha(directory/'added.db'))
    rebuilt=sorted(final,key=lambda r:r[0].lower())
    write(directory/'roundtrip.db',rebuilt,final_attrs,sha(directory/'rebuilt.mdx'))
    receipts={'encoding':label.lower().replace('-','')}
    for name,op,source,dest,sid,oid in [
        ('import','mdx_to_db','original.mdx','dictionary.db',None,None),
        ('metadata','db_edit_metadata','dictionary.db','metadata.db',None,None),
        ('edit','db_edit_entry','metadata.db','definition.db','3','3'),
        ('rename','db_edit_entry','definition.db','renamed.db','5','5'),
        ('add','db_add_entry','renamed.db','added.db',None,'8'),
        ('delete','db_delete_entry','added.db','final.db','6',None),
        ('back','mdx_to_db','rebuilt.mdx','roundtrip.db',None,None)]:
        found,meta,_=inspect(directory/dest)
        value={'records':len(found),'source_sha256':sha(directory/source),'rows_sha256':meta['rows_sha256']}
        if sid is not None:value['source_rowid']=sid
        if oid is not None:value['output_rowid']=oid
        receipts[name]={'receipt':{'operation':op,'value':value}}
    receipts['rebuild']={'receipt':{'operation':'db_to_mdx','value':{'records':7,'source_sha256':sha(directory/'final.db')}}}
    def reader(path):
        return sha(path), (rows.copy() if path.name=='original.mdx' else rebuilt.copy()), (attrs.copy() if path.name=='original.mdx' else final_attrs.copy())
    return fixture,receipts,reader


class WorkflowOracleTests(unittest.TestCase):
    def test_complete_workflow_each_encoding(self):
        for label in ['UTF-8','UTF-16']:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as d:
                directory=Path(d);fixture,receipts,reader=prepare(directory,label)
                with patch('m4_database_workflow.read_mdx',side_effect=reader):
                    result=verify_case(directory,fixture,label,receipts)
                self.assertEqual(result['records'],7)
                self.assertTrue(result['three_duplicate_definitions_preserved'])

    def test_regenerated_stage_digest_cannot_hide_wrong_duplicate_or_metadata(self):
        for tamper in ['row','metadata','receipt']:
            with self.subTest(tamper=tamper),tempfile.TemporaryDirectory() as d:
                directory=Path(d);fixture,receipts,reader=prepare(directory,'UTF-16')
                rows,meta,attrs=inspect(directory/'definition.db')
                values=[(k,t) for _,k,t in rows]
                if tamper=='row':values[1]=('duplicate','changed sibling')
                elif tamper=='metadata':attrs['Description']='changed'
                else:receipts['add']['receipt']['value']['output_rowid']='3'
                if tamper!='receipt':write(directory/'definition.db',values,attrs,meta['source_sha256'])
                with patch('m4_database_workflow.read_mdx',side_effect=reader),self.assertRaises(AssertionError):
                    verify_case(directory,fixture,'UTF-16',receipts)

    def test_rebuild_must_preserve_duplicate_order_metadata_and_sort(self):
        for tamper in ['duplicate','metadata','sort']:
            with self.subTest(tamper=tamper),tempfile.TemporaryDirectory() as d:
                directory=Path(d);fixture,receipts,reader=prepare(directory,'UTF-8')
                def bad_reader(path):
                    digest,rows,attrs=reader(path)
                    if path.name=='rebuilt.mdx':
                        if tamper=='duplicate':rows[1],rows[2]=rows[2],rows[1]
                        elif tamper=='metadata':attrs['Title']='wrong'
                        else:rows.reverse()
                    return digest,rows,attrs
                with patch('m4_database_workflow.read_mdx',side_effect=bad_reader),self.assertRaises(AssertionError):
                    verify_case(directory,fixture,'UTF-8',receipts)
