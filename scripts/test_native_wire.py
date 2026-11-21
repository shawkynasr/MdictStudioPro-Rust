"""Wire-level regression from the actual user-uploaded failing fixture."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from patched_interop import ROOT
from prepare_sort_experiment import NATIVE_WIRE_EDITS,native_wire_patch
from check_native_wire import wire_contract
from v2_audit import audit


class NativeWireRegression(unittest.TestCase):
    def test_actual_crashing_pair_is_not_qualified_by_structural_success(self):
        archive=ROOT/"docs/evidence/native-import-crash/mdict-crash-pair.zip"
        with tempfile.TemporaryDirectory() as tmp,zipfile.ZipFile(archive) as source:
            results={}
            for name in ["reader-utf16-mdxbuilder.mdx","reader-utf16-mdxbuilder.mdd"]:
                path=Path(tmp)/name
                data=source.read(name)
                self.assertLess(len(data),1024*1024)
                path.write_bytes(data)
                observed=audit(path)
                self.assertEqual(observed["status"],"structural_audit_passed")
                results[path.suffix]=(observed,wire_contract(path,observed))
            mdx,contract=results[".mdx"]
            self.assertEqual(mdx["records"],13)
            self.assertEqual(mdx["records_without_terminal_null"],13)
            self.assertEqual(contract["status"],"failed")
            self.assertFalse(contract["checks"]["all_MDX_records_have_encoded_terminal_NUL"])
            self.assertFalse(contract["checks"]["explicit_unencrypted_header"])
            self.assertFalse(results[".mdd"][1]["checks"]["MDD_legacy_metadata_present"])

    def test_revision4_edits_are_exactly_reversible_and_refuse_double_application(self):
        # Source anchor contract only; this does not compile or execute Rust.
        source="\n".join(before for before,after in NATIVE_WIRE_EDITS)
        patched=native_wire_patch(source)
        self.assertEqual(native_wire_patch(patched,reverse=True),source)
        with self.assertRaises(ValueError):native_wire_patch(patched)
        with self.assertRaises(ValueError):native_wire_patch(source.replace('encoding.encode(body, "entry body")','unexpected()'))


if __name__=="__main__":unittest.main()
