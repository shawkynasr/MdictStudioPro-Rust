import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zlib
from v2_import_fixtures import ROWS,lookup,resolve,rewrite,generate,read_legacy_physical,raw_wire_keys
from m2_v2_import import protected_sources,compare_query
from v2_import_lock import check_lock

class V2ImportContracts(unittest.TestCase):
    def test_fixture_oracle_reads_base_before_stylesheet_header_mutations(self):
        calls=[];resources=[]
        class Writer:
            def __init__(self,records,**options):
                self.mdd=options['is_mdd'];self.records=sorted(records,key=lambda r:r['key']) if self.mdd else records
                self.encoding='utf-16le' if self.mdd or options['encoding']=='utf16' else 'utf-8'
                if self.mdd:resources.extend((r['key'],Path(r['path']).read_bytes()) for r in self.records)
            def write(self,stream):
                root='Library_Data' if self.mdd else 'Dictionary'
                raw=(f'<{root} GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" Encoding="{self.encoding}" StripKey="No"/>\0').encode('utf-16le')
                def compressed(data):return struct.pack('<I',2)+struct.pack('>I',zlib.adler32(data)&0xffffffff)+zlib.compress(data)
                keys=b'';offset=0;count=len(self.records);unit=2 if self.encoding=='utf-16le' else 1
                for record in self.records:
                    keys+=struct.pack('>Q',offset)+(record['key']+'\0').encode(self.encoding);offset+=record['size']
                packed=compressed(keys);info=struct.pack('>Q',count)
                for record in (self.records[0],self.records[-1]):
                    key=record['key'].encode(self.encoding);info+=struct.pack('>H',len(key)//unit)+key+b'\0'*unit
                info+=struct.pack('>QQ',len(packed),len(keys));packed_info=compressed(info)
                summary=struct.pack('>5Q',1,count,len(info),len(packed_info),len(packed))
                bodies=b''.join(Path(r['path']).read_bytes()[r['pos']:r['pos']+r['size']] for r in self.records);packed_bodies=compressed(bodies)
                sections=summary+struct.pack('>I',zlib.adler32(summary)&0xffffffff)+packed_info+packed+struct.pack('>4Q',1,count,16,len(packed_bodies))+struct.pack('>QQ',len(packed_bodies),len(bodies))+packed_bodies
                stream.write(struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff)+sections)
        def reader(path,kind):
            calls.append(path.name)
            if kind=='mdd':return resources[:-1] # legacy EOF loop omits trailing empty
            self.assertTrue(path.name.endswith('-base.mdx'))
            return [(r['key'].strip(),r['text']) for r in ROWS]
        with tempfile.TemporaryDirectory() as tmp,patch('v2_import_fixtures.custom_writer_class',return_value=Writer),patch('v2_import_fixtures.read_python',side_effect=reader):
            cases=generate(Path(tmp)/'inputs')
            self.assertEqual(calls,['utf8-base.mdx','utf16-base.mdx','foreign.mdd'])
            self.assertGreater(len(cases),20)
            data=cases[0]['path'].read_bytes();n=struct.unpack_from('>I',data)[0]
            self.assertIn('StyleSheet="1&#10;',data[4:n+4].decode('utf-16le'))
            self.assertEqual(cases[0]['rows'],ROWS)
            archive=Path(tmp)/'inputs/foreign.mdd'
            self.assertEqual(len(cases[-4]['resources']),4)
            self.assertEqual(cases[-4]['resources'][-1],{'key':'empty.bin','bytes':[]})
            with patch('v2_import_fixtures.read_python',return_value=resources):
                self.assertEqual(read_legacy_physical(archive,'mdd'),resources)
            for wrong in [resources[:1],resources[:-1]+[('empty.bin',b'changed')]]:
                with patch('v2_import_fixtures.read_python',return_value=wrong):
                    with self.assertRaisesRegex(AssertionError,'resource mismatch'):read_legacy_physical(archive,'mdd')
            for name in ['utf8-base.mdx','utf16-base.mdx']:
                path=Path(tmp)/'inputs'/name
                self.assertIn(' spaced ',raw_wire_keys(path,'mdx'))
                with patch('v2_import_fixtures.read_python',return_value=[('wrong','body')]):
                    with self.assertRaisesRegex(AssertionError,'record count mismatch'):read_legacy_physical(path,'mdx')
                changed=[(r['key'].strip(),r['text']) for r in ROWS];changed[0]=('wrong',changed[0][1])
                with patch('v2_import_fixtures.read_python',return_value=changed):
                    with self.assertRaisesRegex(AssertionError,'projection mismatch'):read_legacy_physical(path,'mdx')
                data=bytearray(path.read_bytes());n=struct.unpack_from('>I',data)[0];data[n+8+40]^=1
                bad=path.with_name('bad-keys.mdx');bad.write_bytes(data)
                with self.assertRaisesRegex(AssertionError,'key-section checksum'):raw_wire_keys(bad,'mdx')
    def test_explicit_lookup_preserves_exact_priority_and_duplicate_order(self):
        self.assertEqual([e['text'] for e in lookup(ROWS,'apple','header_ascii_v1')],['first','second'])
        self.assertEqual(len(lookup(ROWS,'aPpLe','header_ascii_v1')),3)
        self.assertEqual(lookup(ROWS,'aPpLe','raw_exact'),[])
        self.assertEqual(len(lookup(ROWS,'a?b','header_ascii_v1',False,True)),4)
        self.assertEqual(lookup(ROWS,'a?b','header_ascii_v1',False,False),[])
    def test_redirect_oracle_handles_duplicates_and_discards_partial_results(self):
        self.assertEqual([r['entry']['text'] for r in resolve(ROWS,'alias','raw_exact')],['first','second'])
        self.assertEqual(resolve(ROWS,'space-alias','raw_exact')[0]['entry']['key'],' spaced ')
        for query,detail in [('cycle-a','redirect_cycle'),('missing-alias','redirect_missing'),('bad-alias','redirect_target'),('multiline-alias','redirect_target'),('branch','redirect_cycle')]:
            with self.assertRaisesRegex(ValueError,detail):resolve(ROWS,query,'raw_exact')
        with self.assertRaisesRegex(ValueError,'redirect_depth'):resolve(ROWS,'chain','raw_exact',max_hops=1)
        with self.assertRaisesRegex(ValueError,'limit_exceeded'):resolve(ROWS,'alias','raw_exact',max_results=1)
    def test_header_fixture_rewrite_preserves_sections_and_checksums(self):
        raw='<Dictionary GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0" StripKey="No"/>\0'.encode('utf-16le')
        original=struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff)+b'BINARY SECTIONS'
        result=rewrite(original,{'Description':'line1\nline2 & <tag>'},aliases={'StripKey':'Stripkey'})
        n=struct.unpack_from('>I',result)[0];self.assertEqual(result[n+8:],b'BINARY SECTIONS');self.assertEqual(zlib.adler32(result[4:n+4])&0xffffffff,struct.unpack_from('<I',result,n+4)[0])
        self.assertIn('&#10;',result[4:n+4].decode('utf-16le'))
    def test_mdd_fixture_rewrite_preserves_library_data_root(self):
        raw='<Library_Data GeneratedByEngineVersion="2.0" RequiredEngineVersion="2.0"/>\0'.encode('utf-16le')
        data=struct.pack('>I',len(raw))+raw+struct.pack('<I',zlib.adler32(raw)&0xffffffff)+b'MDD RECORDS'
        changed=rewrite(data,{'Title':'Resource archive'})
        n=struct.unpack_from('>I',changed)[0];xml=changed[4:n+4].decode('utf-16le')
        self.assertTrue(xml.startswith('<Library_Data '));self.assertEqual(changed[n+8:],b'MDD RECORDS')
    def test_independent_query_comparison_rejects_changed_or_missing_duplicates(self):
        expected=lookup(ROWS,'apple','raw_exact');compare_query({'entries':expected},lambda:expected)
        for bad in [expected[:1],list(reversed(expected)),[{'key':'apple','text':'changed'}]]:
            with self.assertRaises(AssertionError):compare_query({'entries':bad},lambda:expected)
    def test_prior_sources_and_registry_graph_stay_pinned(self):
        self.assertGreater(len(protected_sources()),95);self.assertEqual(len(check_lock()),61)

if __name__=='__main__':unittest.main()
