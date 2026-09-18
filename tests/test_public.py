import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('check_public', Path(__file__).parents[1] / 'scripts/check_public.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicFilesTests(unittest.TestCase):
    def test_safe_translation(self):
        self.assertEqual(module.inspect('translations/ui.json', '{"ja":"設定"}'.encode()), [])

    def test_assets_and_local_files(self):
        for path in ['original.pak', '.local/source.json', 'a.uasset', '.env.production']:
            self.assertTrue(module.inspect(path, b'test'))

    def test_secrets_without_printing_them(self):
        samples = [b'github_' + b'pat_' + b'x' * 30,
                   b'https://' + b'user:password@example.test',
                   b'-----BEGIN ' + b'PRIVATE KEY-----',
                   b'C:' + b'/Users/example/test']
        for sample in samples:
            self.assertTrue(module.inspect('data.txt', sample))


if __name__ == '__main__':
    unittest.main()
