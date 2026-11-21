"""Stress gate distinguishes smoke coverage, watchdog events and format mutations."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from stress_qualification import rss_bytes,monitored,damaged_copy,PRESETS,key_block_offset


class StressQualification(unittest.TestCase):
    def test_mac_and_linux_peak_RSS_units_and_preset_scope(self):
        self.assertEqual(rss_bytes(1024,'darwin'),1024)
        self.assertEqual(rss_bytes(1024,'linux'),1024*1024)
        self.assertGreater(PRESETS['standard']['entries']*PRESETS['standard']['body_bytes'],32*1024*1024)
        self.assertLess(PRESETS['quick']['entries']*PRESETS['quick']['body_bytes'],32*1024*1024)

    @unittest.skipUnless(hasattr(os,'wait4'),'Requires POSIX wait4')
    def test_monitor_measures_actual_child_and_distinguishes_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            success=monitored([sys.executable,'-c','print(123)'],root/'ok',10,256*1024*1024)
            self.assertEqual(success['returncode'],0)
            self.assertIsNone(success['termination'])
            self.assertGreater(success['peak_rss_bytes'],0)
            timeout=monitored([sys.executable,'-c','import time; time.sleep(5)'],root/'timeout',0.1,256*1024*1024)
            self.assertEqual(timeout['termination'],'timeout')
            self.assertLess(timeout['returncode'],0)

    def test_fault_mutations_target_known_bounded_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'seed.mdx'
            header=b'<\x00/\x00>\x00\0\0'
            prefix=struct.pack('>I',len(header))+header+b'\0'*4
            key_header=struct.pack('>5Q',1,5,64,8,32)+b'\0'*4
            source.write_bytes(prefix+key_header+b'\0'*8+b'\x02\0\0\0'+b'\0'*96)
            pos,offset=key_block_offset(source.read_bytes())
            for kind in ['truncated','invalid_compression','oversized_declaration','checksum_only']:
                target=root/(kind+'.mdx');damaged_copy(source,target,kind)
                self.assertNotEqual(source.read_bytes(),target.read_bytes())
                if kind=='invalid_compression':self.assertEqual(target.read_bytes()[offset:offset+4],b'\xff'*4)
                if kind=='oversized_declaration':self.assertEqual(struct.unpack_from('>Q',target.read_bytes(),pos)[0],2**64-1)
            with self.assertRaises(ValueError):damaged_copy(source,root/'bad','unknown')


if __name__=='__main__':unittest.main()
