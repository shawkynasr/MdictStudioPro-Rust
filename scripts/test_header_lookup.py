"""Header edits must not disguise sort mismatches or duplicate lookup loss."""
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from header_lookup import entries,expected_lookup,normalized,rewrite_header,sections,diagnostics,block_membership,conflict_rejected
from test_checksum_qualification import fixture


class HeaderLookupContract(unittest.TestCase):
    def test_engine_and_wrapper_conflict_rejections_both_pass_without_weakening_errors(self):
        for message in [b'ERROR: invalid data: conflicting aliases for header attribute StripKey',b'ERROR: Conflicting StripKey aliases']:
            self.assertTrue(conflict_rejected(1,b'',message+b'\n'))
            self.assertFalse(conflict_rejected(0,b'',message))
            self.assertFalse(conflict_rejected(-9,b'',message))
            self.assertFalse(conflict_rejected(1,b'{"rows":[]}',message))
        for message in [b'ERROR: invalid data: truncated file',b'ERROR: checksum mismatch',b'thread panicked',b'']:
            self.assertFalse(conflict_rejected(1,b'',message))

    def test_exact_rows_win_and_case_fallback_preserves_all_duplicates(self):
        rows=entries()
        self.assertEqual([r['text'] for r in expected_lookup(rows,'apple',False)],['<p>LOWER_ONE</p>','<p>LOWER_TWO</p>'])
        self.assertEqual(len(expected_lookup(rows,'aPpLe',False)),4)
        self.assertEqual(len(expected_lookup(rows,'duplicate',False)),12)
        self.assertEqual(expected_lookup(rows,'missing',True),[])

    def test_strip_flag_changes_fallback_but_not_stored_keys(self):
        rows=entries()
        self.assertEqual(expected_lookup(rows,'a?b',False),[])
        self.assertEqual({r['key'] for r in expected_lookup(rows,'a?b',True)},{'ab','a-b','a b','a.b','a!b','a\\b'})
        self.assertEqual(normalized('中，文\u00a0字',True),'中，文\u00a0字')

    def test_alias_edits_preserve_sections_and_regenerate_header_checksum(self):
        raw=fixture();n=struct.unpack_from('>I',raw)[0]
        changed=rewrite_header(raw,[(' Encoding="UTF-8"',' Encoding="UTF-8" Stripkey="Yes"')])
        self.assertEqual(sections(raw),sections(changed))
        size=struct.unpack_from('>I',changed)[0]
        self.assertEqual(struct.unpack_from('<I',changed,size+4)[0],zlib.adler32(changed[4:size+4])&0xffffffff)
        with self.assertRaises(AssertionError):rewrite_header(raw,[(' StripKey="No"',' StripKey="Yes"')])
        damaged=bytearray(raw);damaged[n+4]^=1
        with self.assertRaises(AssertionError):rewrite_header(bytes(damaged),[])

    def test_flag_only_negative_control_is_actually_out_of_order(self):
        rows=sorted(entries(),key=lambda e:e['key'].lower())
        observed={'rows':rows,'lookups':[],'attributes':{},'resolved_strip':True}
        self.assertFalse(diagnostics(observed,True)['ordering_monotonic_under_reference_lookup'])
        self.assertTrue(diagnostics(observed,False)['ordering_monotonic_under_reference_lookup'])

    def test_independent_key_block_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.mdx';path.write_bytes(fixture())
            keys,members=block_membership(path)
            self.assertEqual(keys,['a','b']);self.assertEqual(members,[0,1])


if __name__=='__main__':unittest.main()
