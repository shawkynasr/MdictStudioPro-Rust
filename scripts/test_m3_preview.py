"""Static boundary contracts; browser/WebKit and native Rust execution remain distinct."""
import json
import re
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'m3/desktop'
class PreviewContracts(unittest.TestCase):
    def test_untrusted_frame_has_no_parent_permissions(self):
        app=(D/'src/App.svelte').read_text()
        self.assertIn('sandbox=""',app)
        self.assertIn('srcdoc={preview.document}',app)
        frames=re.findall(r'<iframe\b[^>]*>',app)
        self.assertGreaterEqual(len(frames),2)
        for frame in frames:
            self.assertIn('sandbox=""',frame)
            self.assertIn('referrerpolicy="no-referrer"',frame)
            self.assertIn('srcdoc=',frame)
        self.assertIn('srcdoc={databasePreview.document}',app)
        self.assertNotIn('{@html',app)
        self.assertNotIn('allow-scripts',app)
        self.assertNotIn('allow-same-origin',app)
        cap=json.loads((D/'src-tauri/capabilities/main.json').read_text())
        self.assertEqual(cap['windows'],['main'])
        self.assertNotIn('remote',cap)
        for policy in ['csp','devCsp']:
            csp=json.loads((D/'src-tauri/tauri.conf.json').read_text())['app']['security'][policy]
            self.assertIn('frame-src about:',csp)
            self.assertIn("script-src 'self'",csp)
            self.assertNotIn('frame-src *',csp)
    def test_renderer_is_detached_passive_and_bounded(self):
        source=(D/'src/preview.ts').read_text()
        self.assertIn("createElement('template')",source)
        self.assertNotIn('DOMParser',source)
        for unsafe in ['invoke(', 'fetch(', 'window.__TAURI', 'document.body.innerHTML']:
            self.assertNotIn(unsafe,source)
        self.assertIn('MAX_RESOURCES = 32',source)
        self.assertIn('MAX_BUNDLE = 4194304',source)
        self.assertIn('nodes.length>4000',source)
        self.assertIn('signal.aborted',source)
        self.assertIn("frame-src 'none'",source)
    def test_reader_metadata_has_close_and_digest_binding(self):
        adapter=(ROOT/'m3/native-adapter/src/lib.rs').read_text()
        detail=(ROOT/'m3/native-adapter/src/details.rs').read_text()
        self.assertIn('r.task.start()?',adapter)
        self.assertIn('r.task.wait()',adapter)
        self.assertIn('r.closing && !r.task.busy()',adapter)
        self.assertIn('r.task.cancel()',adapter)
        self.assertIn('sha256::hex(&hash.finish())!=expected',detail)
        self.assertIn('const CAP:u64=512*1024*1024',detail)
        self.assertIn('len%2!=0',detail)
        self.assertIn('task.check()?',detail)
    def test_resource_jobs_retain_single_consumer_ownership(self):
        app=(D/'src/App.svelte').read_text()
        self.assertIn('job.job_id!==mddOpenJob && !resourceWaiters.has(job.job_id)',app)
        self.assertIn('resourceWaiters.set(result.job_id',app)
        self.assertIn('waiter.cleanup();resourceWaiters.delete(job.job_id)',app)
        self.assertIn("request:{source:mddSource,artifact:mddIndex,kind:'mdd',policy:'raw_exact'}",app)
        self.assertIn("if(sessionId || mddId) throw",app)
if __name__=='__main__':unittest.main()
