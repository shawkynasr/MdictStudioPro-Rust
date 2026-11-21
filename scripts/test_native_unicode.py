import json
from pathlib import Path
import tempfile
import unittest
from native_unicode import read_reference,checklist,EXACT,OBSERVE
from integrated_casing import ROOT,fixture


class NativeUnicode(unittest.TestCase):
    def test_log_reader_rejects_truncation_or_extra_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'reference.log';path.write_text('{"contexts":[]}\n\nSTDERR:\n')
            self.assertEqual(read_reference(path),{'contexts':[]})
            for text in ['{"contexts":','{"contexts":[]} debug\nSTDERR:\n','{"contexts":[]}\nSTDERR:\nwarning']:
                path.write_text(text)
                with self.assertRaises((ValueError,AssertionError)):read_reference(path)

    def test_native_checks_require_payload_access_but_do_not_assert_studio_fallback(self):
        prior=json.loads((ROOT/'docs/evidence/unicode-version-user-run/unicode-profile-report.json').read_text())
        rows,queries=fixture(prior['lowercase_mapping']['differences'])
        # Identity normalization is sufficient to verify presentation semantics;
        # exact/fallback algorithm behavior has its own qualification tests.
        norms={k:k for k in [r['key'] for r in rows]+queries}
        checks=checklist(rows,norms)
        self.assertEqual(len(checks),len(EXACT)+len(OBSERVE))
        dup=next(c for c in checks if c['query']=='duplicate')
        self.assertEqual(dup['required_markers'],[f'DUP_{n:02d}' for n in range(1,9)])
        self.assertTrue(all(not c['required_markers'] for c in checks if c['kind']=='reader behavior observation'))
        self.assertEqual(next(c for c in checks if c['query']=='i\u0307')['codepoints'],'U+0069 U+0307')


if __name__=='__main__':unittest.main()
