import hashlib
import json
from pathlib import Path
import unittest
from m3_shell import ROOT
from m3_pack_lock_edge import matches_reviewed_lock


class CompressorEdgeChecks(unittest.TestCase):
    def test_current_edge_must_reverse_to_exact_previously_bound_hash(self):
        bindings=json.loads((ROOT/'m3/packaging/mac-lock-bindings.json').read_text())['locks']
        for name in ['m3/native-adapter/Cargo.lock','m3/txt-runtime/Cargo.lock',
                     'm3/export-io/Cargo.lock','m3/indexed-sessions/Cargo.lock','m3/desktop/src-tauri/Cargo.lock']:
            data=(ROOT/name).read_bytes()
            self.assertTrue(matches_reviewed_lock(name,data,bindings[name]['accepted_sha256']),name)
            self.assertFalse(matches_reviewed_lock(name,data,['0'*64]),name)
            self.assertFalse(matches_reviewed_lock(name,data+b'\n# unrelated change\n',bindings[name]['accepted_sha256']),name)

    def test_only_one_exact_edge_and_no_other_changes_are_allowed(self):
        original=b'[[package]]\nname = "root"\n\n[[package]]\nname = "studio-export-io"\nversion = "0.1.0"\ndependencies = [\n "libc",\n "tempfile",\n]\n'
        accepted=[hashlib.sha256(original).hexdigest()]
        changed=original.replace(b' "tempfile",',b' "miniz_oxide 0.9.1",\n "tempfile",')
        self.assertTrue(matches_reviewed_lock('m3/export-io/Cargo.lock',changed,accepted))
        for bad in [changed.replace(b'0.9.1',b'0.9.2'),changed.replace(b' "libc",',b' "libc 99.0.0",'),changed.replace(b' "tempfile",',b' "miniz_oxide",\n "tempfile",')]:
            self.assertFalse(matches_reviewed_lock('m3/export-io/Cargo.lock',bad,accepted))
        self.assertFalse(matches_reviewed_lock('m2/cc-pack-runtime/Cargo.lock',changed,accepted))
