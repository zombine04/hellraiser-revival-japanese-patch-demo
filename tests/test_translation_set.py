import unittest
from jp_patch.translation_set import select_rows


def row(key, ja, status='reviewed'):
    return dict(namespace='自作', key=key, namespace_hash=1, key_hash=2, source_hash=3, ja=ja, status=status)


class TranslationSetTests(unittest.TestCase):
    def test_preview_prefers_formal_and_keeps_only_missing_probe(self):
        formal=[row('a','改訂した訳'),row('b','新しい訳')]
        probe=[row('a','古い試作'),row('c','試作だけの訳')]
        selected=select_rows(formal,probe,preview=True)
        self.assertEqual([r['ja'] for r in selected],['改訂した訳','新しい訳','試作だけの訳'])

    def test_release_never_uses_probe(self):
        self.assertEqual(select_rows([], [row('a','試作')]), [])

    def test_untranslated_formal_is_not_hidden_by_probe(self):
        formal=row('a','',status='untranslated')
        self.assertEqual(select_rows([formal],[row('a','古い試作')],preview=True),[formal])

    def test_duplicate_formal_is_rejected(self):
        with self.assertRaises(ValueError):
            select_rows([row('a','第一稿'),row('a','第二稿')],preview=True)
