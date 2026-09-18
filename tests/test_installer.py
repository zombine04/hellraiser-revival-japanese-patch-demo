"""自作の小さなコンテナを使う。実ゲームにはアクセスしない。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NAMES = [f'Hellraiser_Japanese_P.{ext}' for ext in ('pak', 'utoc', 'ucas')]
ORIGINALS = ['global.utoc', 'global.ucas'] + [f'{stem}.{ext}' for stem in ('pakchunk0-Windows', 'pakchunk0optional-Windows') for ext in ('pak', 'utoc', 'ucas')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.name == 'nt', 'Windows導入スクリプトの検証')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='jp-installer-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.package = self.base / "配布 ZIP's folder"
        self.package.mkdir()
        self.game = self.base / "ゲーム 空白's folder"
        self.paks = self.game / 'Hellraiser/Content/Paks'
        self.paks.mkdir(parents=True)
        self.exe = self.game/'Hellraiser/Binaries/Win64/Hellraiser-Win64-Shipping.exe'
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b'self-made-executable-marker')
        for name in ORIGINALS:
            (self.paks / name).write_bytes(('自作の元データ:' + name).encode())
        for name in ('Patch.ps1', 'Install.cmd', 'Uninstall.cmd'):
            shutil.copyfile(ROOT / 'distribution' / name, self.package / name)
        for name in ('README.md', 'THIRD_PARTY_NOTICES.md'):
            (self.package / name).write_text('自作のテスト用説明', encoding='utf-8')
        self.manifest = dict(schema_version=1, product='hellraiser-revival-demo-japanese', patch_version='1.0.0', files=[], supported_builds=[dict(version='test-build', containers=[dict(name=n, size=(self.paks/n).stat().st_size, sha256=digest(self.paks/n)) for n in ORIGINALS])])
        self.manifest['supported_builds'][0]['executable'] = dict(name='Hellraiser/Binaries/Win64/Hellraiser-Win64-Shipping.exe',size=self.exe.stat().st_size,sha256=digest(self.exe))
        self.prepare('1.0.0')
        self.original_bytes = {n: (self.paks/n).read_bytes() for n in ORIGINALS}

    def prepare(self, version):
        self.manifest['patch_version'] = version
        for name in NAMES:
            (self.package/name).write_bytes(('自作パッチ:' + version + name).encode())
        self.manifest['files'] = [dict(name=n, sha256=digest(self.package/n)) for n in NAMES]
        self.checksums()

    def checksums(self):
        (self.package/'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        names = NAMES + ['Patch.ps1', 'Install.cmd', 'Uninstall.cmd', 'README.md', 'manifest.json', 'THIRD_PARTY_NOTICES.md']
        (self.package/'SHA256SUMS.txt').write_text(''.join(f'{digest(self.package/n)}  {n}\n' for n in sorted(names)), encoding='ascii')

    def run_patch(self, action='Install', success=True):
        result = subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.package/'Patch.ps1'),'-Action',action,'-GameDir',str(self.game),'-NonInteractive'], capture_output=True, timeout=30)
        self.assertEqual(result.returncode == 0, success, result.stdout.decode('utf-8', errors='replace') + result.stderr.decode('utf-8', errors='replace'))
        self.assertFalse((self.paks/'.hellraiser-japanese-patch.lock').exists())
        for n, data in self.original_bytes.items():
            self.assertEqual((self.paks/n).read_bytes(), data)

    def test_install_reinstall_update_remove(self):
        self.run_patch()
        self.run_patch()
        self.prepare('1.0.1')
        self.run_patch()
        for n in NAMES:
            self.assertEqual((self.paks/n).read_bytes(), (self.package/n).read_bytes())
        self.run_patch('Uninstall')
        self.run_patch('Uninstall')
        self.assertFalse(any((self.paks/n).exists() for n in NAMES))

    def test_unknown_file_is_preserved(self):
        target = self.paks/NAMES[0]
        target.write_bytes(b'other-mod')
        self.run_patch(success=False)
        self.assertEqual(target.read_bytes(), b'other-mod')

    def test_modified_patch_is_preserved(self):
        self.run_patch()
        target = self.paks/NAMES[1]
        target.write_bytes(b'modified')
        self.run_patch(success=False)
        self.run_patch('Uninstall', success=False)
        self.assertEqual(target.read_bytes(), b'modified')

    def test_package_corruption_is_rejected(self):
        (self.package/NAMES[0]).write_bytes(b'bad')
        self.run_patch(success=False)
        self.assertFalse((self.paks/NAMES[0]).exists())

    def test_unsupported_game_is_rejected(self):
        self.manifest['supported_builds'][0]['containers'][0]['sha256'] = '0'*64
        self.checksums()
        self.run_patch(success=False)

    def test_executable_only_update_is_rejected(self):
        self.exe.write_bytes(b'updated-executable')
        self.run_patch(success=False)

    def test_probe_patch_conflict_is_rejected(self):
        for stem in ('Hellraiser_Japanese_Probe_P', 'Hellraiser_Japanese_Font_P'):
            with self.subTest(stem=stem):
                trial=self.paks/(stem+'.pak')
                trial.write_bytes(b'trial')
                self.run_patch(success=False)
                self.assertEqual(trial.read_bytes(),b'trial')
                trial.unlink()

    def test_manifest_traversal_is_rejected(self):
        self.manifest['files'][0]['name'] = '../unrelated.txt'
        self.checksums()
        self.run_patch(success=False)

    def test_uninstall_after_game_update(self):
        self.run_patch()
        target = self.paks/ORIGINALS[0]
        target.write_bytes(b'game-update')
        self.original_bytes[ORIGINALS[0]] = b'game-update'
        self.run_patch('Uninstall')

    def test_missing_patch_fails_closed(self):
        self.run_patch()
        (self.paks/NAMES[1]).unlink()
        self.run_patch('Uninstall', success=False)
        self.assertTrue((self.paks/NAMES[0]).exists())

    def test_unrelated_mod_is_preserved(self):
        unrelated = self.paks/'OtherMod.pak'
        unrelated.write_bytes(b'unrelated')
        self.run_patch()
        self.run_patch('Uninstall')
        self.assertEqual(unrelated.read_bytes(), b'unrelated')

    def test_readonly_target_rolls_back(self):
        self.run_patch()
        target = self.paks/NAMES[1]
        old = {n:(self.paks/n).read_bytes() for n in NAMES}
        self.prepare('1.0.1')
        target.chmod(0o444)
        try:
            self.run_patch(success=False)
            for n, data in old.items():
                self.assertEqual((self.paks/n).read_bytes(), data)
        finally:
            target.chmod(0o666)


if __name__ == '__main__':
    unittest.main()
