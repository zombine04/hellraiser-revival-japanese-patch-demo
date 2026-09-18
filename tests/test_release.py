from pathlib import Path
import tempfile
import unittest

from jp_patch.release import publish


class FakeGitHub:
    def __init__(self):
        self.current=None
        self.reference=None
        self.assets={}
        self.creates=0
        self.publications=0
        self.corrupt=False
    def tag_commit(self,tag): return self.reference
    def release(self,tag): return self.current
    def create_draft(self,tag,commit):
        self.creates+=1
        self.current=dict(draft=True,target_commitish=commit,assets=[])
    def upload(self,tag,files):
        self.assets={file.name:file.read_bytes() for file in files}
        self.current['assets']=[dict(name=name) for name in self.assets]
    def download(self,tag,names,folder):
        for name in names: (folder/name).write_bytes(b'bad' if self.corrupt else self.assets[name])
    def publish(self,tag):
        self.publications+=1
        self.current['draft']=False
        self.reference=self.current['target_commitish']


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.files=[Path(self.temp.name)/name for name in ('sample.zip','sample.sha256')]
        for file in self.files: file.write_bytes(b'self-made')
        self.github=FakeGitHub()

    def run_publish(self): return publish(self.github,'v1.0.0','a'*40,self.files)

    def test_rerun_is_idempotent(self):
        self.run_publish(); self.run_publish()
        self.assertEqual((self.github.creates,self.github.publications),(1,1))

    def test_failure_stays_draft_and_retry_recovers(self):
        self.github.corrupt=True
        with self.assertRaises(ValueError): self.run_publish()
        self.assertEqual(self.github.publications,0)
        self.assertTrue(self.github.current['draft'])
        self.github.corrupt=False
        self.run_publish()
        self.assertEqual((self.github.creates,self.github.publications),(1,1))

    def test_existing_tag_other_commit_is_rejected(self):
        self.github.reference='b'*40
        with self.assertRaises(ValueError): self.run_publish()
        self.assertEqual(self.github.creates,0)

    def test_published_assets_are_not_replaced(self):
        self.run_publish()
        self.files[0].write_bytes(b'changed')
        with self.assertRaises(ValueError): self.run_publish()
        self.assertEqual(self.github.assets[self.files[0].name],b'self-made')
