"""Notice recovery is pinned, allowlisted and hash checked; gaps are not filled with templates."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ci_upstream_notices import UpstreamNotices, eligible, pinned, repository, save_recovered


class UpstreamNoticeTests(unittest.TestCase):
    def test_no_branch_or_arbitrary_repository_can_be_used(self):
        for value in ['main','v1.0','', 'a'*39, '../LICENSE']:
            with self.assertRaises(ValueError): pinned(value)
        for value in ['https://example.org/a/b', 'file:///LICENSE', 'http://github.com/madsmtm/objc2', 'https://github.com/unapproved/project']:
            with self.assertRaises(ValueError):repository(value)
        self.assertEqual(repository({'url':'git+https://github.com/madsmtm/objc2.git'}),('github.com','madsmtm/objc2'))
        self.assertTrue(eligible('LICENSE-MIT.txt','crates/objc2'))
        self.assertTrue(eligible('crates/objc2/LICENSE','crates/objc2'))
        self.assertFalse(eligible('other-crate/LICENSE','crates/objc2'))
        self.assertFalse(eligible('../LICENSE','crates/objc2'))

    def test_github_blob_must_match_tree_checksum(self):
        data=b'Copyright fixture\nMIT fixture text\n'
        digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        resolver=UpstreamNotices()
        def request(url):
            if '/trees/' in url:return {'tree':[{'path':'LICENSE','type':'blob','sha':digest}]}
            return {'encoding':'base64','content':base64.b64encode(data).decode()}
        with patch.object(resolver,'request',side_effect=request):
            files=list(resolver.files('https://github.com/madsmtm/objc2','a'*40,'crates/objc2'))
        self.assertEqual(files[0][1],data)
        with patch.object(resolver,'request',side_effect=[{'tree':[{'path':'LICENSE','type':'blob','sha':'0'*40}]},{'encoding':'base64','content':base64.b64encode(data).decode()}]):
            with self.assertRaisesRegex(ValueError,'checksum'):list(resolver.files('https://github.com/madsmtm/objc2','a'*40))

    def test_npm_commit_requires_matching_locked_integrity(self):
        resolver=UpstreamNotices()
        metadata={'ecosystem':'npm','name':'is-reference','version':'3.0.3','repository':'https://github.com/Rich-Harris/is-reference'}
        with patch.object(resolver,'request',return_value={'name':'is-reference','version':'3.0.3','gitHead':'a'*40,'dist':{'integrity':'wrong'}}):
            with self.assertRaisesRegex(ValueError,'integrity'):resolver.recover(Path('.'),metadata,{'integrity':'sha512-pinned'})

    def test_saving_does_not_replace_omitted_files_with_templates(self):
        with tempfile.TemporaryDirectory() as temp:
            p={'id':'fixture','notice_files':[],'license_text_missing':True}
            save_recovered(Path(temp),p,[])
            self.assertTrue(p['license_text_missing'])
            with self.assertRaises(ValueError):save_recovered(Path(temp),p,[('LICENSE',b'<html>not found</html>',{})])
            save_recovered(Path(temp),p,[('LICENSE',b'original notice text',{'commit':'a'*40})])
            self.assertFalse(p['license_text_missing'])
            self.assertEqual((Path(temp)/p['notice_files'][0]['path']).read_bytes(),b'original notice text')


if __name__=='__main__':unittest.main()
