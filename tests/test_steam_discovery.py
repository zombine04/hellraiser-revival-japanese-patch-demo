"""レジストリを変更せず、自作のSteamライブラリ構成で検出を検証する。"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GAME = "steamapps/common/Clive Barker's Hellraiser Revival Demo"


@unittest.skipUnless(os.name == 'nt', 'WindowsのSteamパス検出')
class SteamDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='jp-discovery-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.steam = self.root/"Steam 日本語's folder"
        (self.steam/GAME/'Hellraiser/Content/Paks').mkdir(parents=True)
        # 配布スクリプトから検出関数だけを読み、導入処理やレジストリ参照は実行しない。
        self.runner = self.root/'discovery.ps1'
        self.runner.write_text('''param([string]$Patch,[string]$InputFile)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$tokens=$null; $errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Patch,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw '検出スクリプトの構文エラー' }
$function=$ast.Find({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Get-SteamGameCandidates'},$false)
Invoke-Expression $function.Extent.Text
$roots=Get-Content -LiteralPath $InputFile -Raw -Encoding UTF8 | ConvertFrom-Json
ConvertTo-Json -InputObject @(Get-SteamGameCandidates $roots)
''', encoding='utf-8-sig')

    def discover(self, roots, libraries):
        vdf = '"libraryfolders"\n{\n'+''.join('"path" "'+str(p).replace('\\','\\\\')+'"\n' for p in libraries)+'}\n'
        (self.steam/'steamapps/libraryfolders.vdf').write_text(vdf, encoding='utf8')
        input_file = self.root/'roots.json'
        input_file.write_text(json.dumps([str(p) for p in roots]), encoding='utf8')
        result = subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.runner),
                                 '-Patch',str(ROOT/'distribution/Patch.ps1'),'-InputFile',str(input_file)],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8',errors='replace'))
        return json.loads(result.stdout.decode('utf-8-sig'))

    def test_same_library_with_case_slashes_and_dot_segments(self):
        variants = [str(self.steam), str(self.steam).upper().replace('\\','/'), str(self.steam)+'\\.\\']
        found = self.discover(variants, variants)
        self.assertEqual(len(found), 1)
        self.assertTrue(Path(found[0]).samefile(self.steam/GAME))

    def test_separate_installations_remain_separate(self):
        second = self.root/'別のライブラリ'
        (second/GAME/'Hellraiser/Content/Paks').mkdir(parents=True)
        found = self.discover([self.steam], [self.steam, second])
        # CIではTEMPが8.3形式になるため、表記ではなく実体で比較する。
        self.assertEqual({Path(p).resolve() for p in found}, {(self.steam/GAME).resolve(), (second/GAME).resolve()})

    def test_missing_library_does_not_create_a_candidate(self):
        found = self.discover([self.steam], [self.root/'存在しない保存先'])
        self.assertEqual(len(found), 1)
