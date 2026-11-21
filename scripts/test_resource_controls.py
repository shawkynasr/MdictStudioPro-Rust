"""MDD tests must detect missing dependency edges and altered binary payloads."""
import copy
import struct
import unittest
from resource_controls import specification, validate_asset_graph, validate_resources


class ResourceControls(unittest.TestCase):
    def test_resource_graph_resolves_CSS_font_and_refuses_missing_assets(self):
        case = specification()['cases'][0]
        graph = validate_asset_graph(case)
        self.assertEqual(graph['resolved_font_key'],'fonts/studio-probe.ttf')
        broken = copy.deepcopy(case)
        broken['resources'] = [r for r in broken['resources'] if not r['key'].endswith('.ttf')]
        with self.assertRaises(AssertionError): validate_asset_graph(broken)

    def test_binary_zero_and_ff_bytes_are_not_text_normalized(self):
        case = specification()['cases'][0]
        expected = sorted(case['resources'],key=lambda r:r['key'].lower())
        rows = [(r['key'],bytes(r['bytes'])) for r in expected]
        result = {'rows':expected,'key_blocks':4,'record_blocks':4,
            'lookups':[{'query':r['key'],'rows':[r]} for r in case['resources']]+[
                {'query':'\\missing-resource.bin','rows':[]}]}
        self.assertEqual(validate_resources(case,result,rows)['resources'],4)
        broken = copy.deepcopy(result)
        sentinel = next(r for r in broken['rows'] if r['key'].endswith('.bin'))
        sentinel['bytes'] = list(bytes(sentinel['bytes']).rstrip(b'\0'))
        with self.assertRaises(AssertionError): validate_resources(case,broken,rows)
        broken = copy.deepcopy(result); broken['lookups'][-1]['rows'] = [expected[0]]
        with self.assertRaises(AssertionError): validate_resources(case,broken,rows)

    def test_font_has_embedding_permissions_and_no_external_sidecars(self):
        case = specification()['cases'][0]
        data = bytes(next(r for r in case['resources'] if r['key'].endswith('.ttf'))['bytes'])
        self.assertEqual(data[:4],b'\0\1\0\0')
        count = struct.unpack_from('>H',data,4)[0]
        tables = {}
        for index in range(count):
            tag,checksum,offset,size = struct.unpack_from('>4sIII',data,12+16*index)
            self.assertLessEqual(offset+size,len(data)); tables[tag] = (offset,size)
        self.assertTrue({b'cmap',b'glyf',b'loca',b'head',b'OS/2'} <= set(tables))
        self.assertEqual(struct.unpack_from('>H',data,tables[b'OS/2'][0]+8)[0],0)
        self.assertFalse(validate_asset_graph(case)['sidecar_assets_required'])


if __name__ == '__main__': unittest.main()
