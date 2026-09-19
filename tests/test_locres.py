import struct
import unittest

from jp_patch.locres import Entry, dumps, loads


class LocresTests(unittest.TestCase):
    def setUp(self):
        self.entries = [Entry('Test', 12, 'b', 22, 32, '漢字・かな・カナ！？\n{Count}'),
                        Entry('Test', 12, 'a', 21, 31, '漢字・かな・カナ！？\n{Count}'),
                        Entry('', 0, 'c', 23, 33, '日本語😀')]

    def test_roundtrip_preserves_identity_hashes_and_unicode(self):
        self.assertEqual(loads(dumps(self.entries)), sorted(self.entries, key=lambda e: e.identity))

    def test_deterministic(self):
        self.assertEqual(dumps(self.entries), dumps(list(reversed(self.entries))))

    def test_empty(self):
        self.assertEqual(loads(dumps([])), [])

    def test_truncated_or_invalid(self):
        data = dumps(self.entries)
        for corrupted in [data[:10], data[:-1], data[:16] + b'\x04' + data[17:], data[:17] + struct.pack('<q', -1) + data[25:]]:
            with self.assertRaises(ValueError):
                loads(corrupted)

    def test_duplicate_identity_and_conflicting_namespace(self):
        with self.assertRaises(ValueError):
            dumps([self.entries[0], self.entries[0]])
        with self.assertRaises(ValueError):
            dumps([self.entries[0], Entry('Test', 100, 'other', 1, 2, '確認')])


if __name__ == '__main__':
    unittest.main()
