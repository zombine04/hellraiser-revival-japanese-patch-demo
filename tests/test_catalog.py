import json
from pathlib import Path
import tempfile
import unittest

from jp_patch.catalog import compare, metadata, read_json, validate
from jp_patch.locres import Entry


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.entry = Entry('Sample',1,'sample',2,3,'Use {Action}\n<Strong>here</>')
        self.catalog = dict(schema_version=1,game_version='self-made',entries=[metadata(self.entry)])
        self.row = self.entry.metadata() | dict(ja='{Action}を使う\n<Strong>ここ</>',status='reviewed')

    def test_valid_translation(self):
        self.assertEqual(validate(self.catalog,[self.row],release=True)['reviewed'],1)

    def test_missing_and_unreviewed_block_release(self):
        with self.assertRaises(ValueError): validate(self.catalog,[],release=True)
        with self.assertRaises(ValueError): validate(self.catalog,[self.row | {'status':'needs_review'}],release=True)

    def test_source_hash_and_duplicate_keys(self):
        with self.assertRaises(ValueError): validate(self.catalog,[self.row | {'source_hash':4}])
        with self.assertRaises(ValueError): validate(self.catalog,[self.row,self.row])

    def test_placeholder_tag_and_newline_damage(self):
        for text in ('使う\n<Strong>ここ</>','{Action}を使う\n<Strong>ここ','{Action}を使う<Strong>ここ</>'):
            with self.subTest(text=text), self.assertRaises(ValueError): validate(self.catalog,[self.row | {'ja':text}])

    def test_original_and_unknown_fields(self):
        with self.assertRaises(ValueError): validate(self.catalog,[self.row | {'ja':self.entry.text}])
        with self.assertRaises(ValueError): validate(self.catalog,[self.row | {'source':'not-publishable'}])
        catalog=self.catalog | {'entries':[metadata(self.entry) | {'source':'not-publishable'}]}
        with self.assertRaises(ValueError): validate(catalog,[self.row])

    def test_exclusion_needs_evidence(self):
        row=dict(namespace='Sample',key='sample',reason='デモ範囲外',evidence='自作の検証結果')
        self.assertEqual(validate(self.catalog,[],[row],release=True)['excluded'],1)
        with self.assertRaises(ValueError): validate(self.catalog,[],[row | {'evidence':''}],release=True)

    def test_update_diff(self):
        new=self.catalog | {'entries':[metadata(Entry('Sample',1,'sample',2,8,'Changed'))]}
        diff=compare(self.catalog,new)
        self.assertEqual(diff['changed'],[dict(namespace='Sample',key='sample')])

    def test_duplicate_json_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.json'
            path.write_text('{"ja":"一","ja":"二"}',encoding='utf-8')
            with self.assertRaises(ValueError): read_json(path)
