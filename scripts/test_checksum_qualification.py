"""Keep checksum mutations isolated and reject unrelated failures as false passes."""
from pathlib import Path
import struct
import tempfile
import unittest
import zlib
from checksum_qualification import geometry,mutate,check_rejection,comparable


def wrapped(data):return b'\x02\0\0\0'+struct.pack('>I',zlib.adler32(data)&0xffffffff)+zlib.compress(data)


def fixture(is_mdd=False):
    encoding='utf-16le' if is_mdd else 'utf-8';unit=2 if is_mdd else 1
    names=['a','b'];payloads=[b'first',b'second'];record_blocks=[wrapped(p) for p in payloads]
    key_blocks=[];offset=0
    for name,payload in zip(names,payloads):
        key_blocks.append(wrapped(struct.pack('>Q',offset)+name.encode(encoding)+b'\0'*unit));offset+=len(payload)
    info=b''
    for name,packed in zip(names,key_blocks):
        summary=struct.pack('>H',1)+name.encode(encoding)+b'\0'*unit
        info+=struct.pack('>Q',1)+summary+summary+struct.pack('>QQ',len(packed),8+2*unit)
    packed_info=wrapped(info)
    xml='<Dictionary GeneratedByEngineVersion="2.0" Encoding="UTF-8"/>\r\n\0'.encode('utf-16le')
    header=struct.pack('>I',len(xml))+xml+struct.pack('<I',zlib.adler32(xml)&0xffffffff)
    key_header=struct.pack('>5Q',2,2,len(info),len(packed_info),sum(map(len,key_blocks)))
    records=struct.pack('>4Q',2,2,32,sum(map(len,record_blocks)))
    records+=b''.join(struct.pack('>QQ',len(b),len(p)) for b,p in zip(record_blocks,payloads))
    return header+key_header+struct.pack('>I',zlib.adler32(key_header)&0xffffffff)+packed_info+b''.join(key_blocks)+records+b''.join(record_blocks)


class ChecksumQualification(unittest.TestCase):
    def test_each_site_changes_exactly_one_checksum_byte_and_no_geometry(self):
        for is_mdd in [False,True]:
            original=fixture(is_mdd);sites=geometry(original,is_mdd)
            self.assertEqual(len(sites),8)
            self.assertEqual(len(set(sites.values())),8)
            for name,offset in sites.items():
                changed=mutate(original,name,sites)
                self.assertEqual(len(changed),len(original))
                self.assertEqual([i for i,(a,b) in enumerate(zip(original,changed)) if a!=b],[offset])

    def test_unrelated_parse_error_or_incomplete_record_scan_is_not_checksum_pass(self):
        check_rejection('last_record_checksum',{'status':'rejected','error_kind':'ChecksumMismatch','phase':'records'})
        with self.assertRaises(AssertionError):check_rejection('xml_checksum',{'status':'rejected','error_kind':'Other'})
        with self.assertRaises(AssertionError):check_rejection('last_record_checksum',{'status':'rejected','error_kind':'ChecksumMismatch','phase':'open'})
        with self.assertRaises(AssertionError):check_rejection('first_key_checksum',{'status':'validated'})

    def test_comparison_requires_full_payload_observations(self):
        result={'records':2,'payload_bytes':11,'diagnostic_fingerprint_fnv1a64':'abc','checksum_policy':'Verify'}
        self.assertEqual(comparable(result),{'records':2,'payload_bytes':11,'diagnostic_fingerprint_fnv1a64':'abc'})
        with self.assertRaises(KeyError):comparable({'records':2})


if __name__=='__main__':unittest.main()
