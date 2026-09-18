from pathlib import Path
import tempfile
import unittest
import zipfile

from jp_patch.build import deterministic_zip


class PackageTests(unittest.TestCase):
    def test_zip_is_reproducible_and_order_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            first,second=Path(tmp)/'a.zip',Path(tmp)/'b.zip'
            deterministic_zip({'b.txt':b'B','a.txt':'自作'.encode()},first)
            deterministic_zip({'a.txt':'自作'.encode(),'b.txt':b'B'},second)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(),['a.txt','b.txt'])
                self.assertEqual(archive.read('a.txt'),'自作'.encode())

    def test_unsafe_zip_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                deterministic_zip({'../a.txt':b'B'},Path(tmp)/'a.zip')
