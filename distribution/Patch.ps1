# Windows PowerShell 5.1 / PowerShell 7
[CmdletBinding()]
param([ValidateSet('Install','Uninstall')][string]$Action='Install', [string]$GameDir, [switch]$NonInteractive)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$product = 'hellraiser-revival-demo-japanese'
$managedNames = @('Hellraiser_Japanese_P.pak','Hellraiser_Japanese_P.utoc','Hellraiser_Japanese_P.ucas')
$stateName = '.hellraiser-japanese-patch.json'
$utf8 = New-Object System.Text.UTF8Encoding($false)
function Fail([string]$Message) { throw [InvalidOperationException]::new($Message) }
function Read-Json([string]$Path) {
    try { return [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8) | ConvertFrom-Json }
    catch { Fail '必要なJSONファイルを読み込めません。ZIPを再展開してください。' }
}
function Hash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
}
function Assert-NoLink([string]$Path) {
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        if ((Test-Path -LiteralPath $current) -and ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail 'リンクやジャンクションを含む場所には適用できません。実体のパスを指定してください。'
        }
        $parent = [IO.Directory]::GetParent($current)
        if ($null -eq $parent) { break }
        $current = $parent.FullName
    }
}
function Assert-GameStopped {
    if (@(Get-Process -Name 'Hellraiser','Hellraiser-Win64-Shipping' -ErrorAction SilentlyContinue).Count) { Fail 'ゲームを終了してから実行してください。' }
}
function Find-Game {
    $steamRoots = @()
    foreach ($key in @('HKCU:\Software\Valve\Steam','HKLM:\SOFTWARE\WOW6432Node\Valve\Steam')) {
        $settings = Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue
        if ($null -eq $settings) { continue }
        foreach ($prop in @('SteamPath','InstallPath')) {
            if ($settings.PSObject.Properties[$prop]) { $steamRoots += [string]$settings.$prop }
        }
    }
    $libraries = @($steamRoots)
    foreach ($steamRoot in $steamRoots) {
        $vdf = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf -PathType Leaf) {
            foreach ($match in [regex]::Matches([IO.File]::ReadAllText($vdf), '"path"\s+"((?:\\.|[^"\\])*)"')) {
                $libraries += $match.Groups[1].Value.Replace('\\','\')
            }
        }
    }
    $found = @($libraries | Select-Object -Unique | ForEach-Object {
        $candidate = Join-Path $_ "steamapps\common\Clive Barker's Hellraiser Revival Demo"
        if (Test-Path -LiteralPath (Join-Path $candidate 'Hellraiser\Content\Paks') -PathType Container) { $candidate }
    })
    if ($found.Count -eq 1) { return $found[0] }
    if ($NonInteractive) { Fail 'ゲームを一意に検出できません。-GameDirで指定してください。' }
    return Read-Host 'ゲームのインストール先フォルダーを入力してください'
}
function Assert-FileList($Files) {
    if (@($Files).Count -ne 3) { Fail 'パッチファイル一覧が不正です。' }
    $seen = @{}
    foreach ($file in $Files) {
        if ($file.name -cnotin $managedNames -or $seen.ContainsKey([string]$file.name)) { Fail '管理対象外のファイルが指定されています。' }
        if ($file.sha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'ハッシュの形式が不正です。' }
        $seen[[string]$file.name] = $true
    }
}
function Assert-Package {
    Assert-NoLink $PSScriptRoot
    $checksumPath = Join-Path $PSScriptRoot 'SHA256SUMS.txt'
    if (!(Test-Path -LiteralPath $checksumPath -PathType Leaf)) { Fail 'チェックサム一覧がありません。配布ZIP全体を展開してください。' }
    $expected = @($managedNames) + @('Patch.ps1','Install.cmd','Uninstall.cmd','README.md','manifest.json','THIRD_PARTY_NOTICES.md')
    $seen = @{}
    foreach ($line in [IO.File]::ReadAllLines($checksumPath)) {
        if ($line -cnotmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$') { Fail 'チェックサム一覧の形式が不正です。' }
        $digest, $name = $Matches[1], $Matches[2]
        if ($name -cnotin $expected -or $seen.ContainsKey($name)) { Fail '配布ファイル一覧が不正です。' }
        $path = Join-Path $PSScriptRoot $name
        Assert-NoLink $path
        if (!(Test-Path -LiteralPath $path -PathType Leaf) -or (Hash $path) -cne $digest) { Fail '配布ファイルの整合性確認に失敗しました。ZIPを再取得してください。' }
        $seen[$name] = $true
    }
    if ($seen.Count -ne $expected.Count) { Fail '配布ファイルが不足しています。' }
}
$lock = $null
$lockPath = $null
try {
    Assert-GameStopped
    if (!$GameDir) { $GameDir = Find-Game }
    if (!$GameDir) { Fail 'ゲームのインストール先が指定されていません。' }
    $GameDir = [IO.Path]::GetFullPath($GameDir.Trim('"'))
    $pakDir = Join-Path $GameDir 'Hellraiser\Content\Paks'
    Assert-NoLink $pakDir
    if (!(Test-Path -LiteralPath $pakDir -PathType Container)) { Fail '対象のゲームフォルダーではありません。' }
    $statePath = Join-Path $pakDir $stateName
    Assert-NoLink $statePath
    $lockPath = Join-Path $pakDir '.hellraiser-japanese-patch.lock'
    try { $lock = [IO.File]::Open($lockPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None) }
    catch { Fail '書き込み権限がないか、別の処理が実行中です。ロックが残る場合はREADMEを参照してください。' }
    $oldState = $null
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        $oldState = Read-Json $statePath
        if ($oldState.schema_version -ne 1 -or $oldState.product -cne $product) { Fail '既存の管理情報を確認できません。' }
        Assert-FileList $oldState.files
    }
    foreach ($name in $managedNames) {
        $path = Join-Path $pakDir $name
        Assert-NoLink $path
        if (Test-Path -LiteralPath $path) {
            if ($null -eq $oldState) { Fail '同名の未知ファイルがあります。上書きせず中止します。' }
            $known = @($oldState.files | Where-Object { $_.name -ceq $name })[0]
            if (!(Test-Path -LiteralPath $path -PathType Leaf) -or (Hash $path) -cne $known.sha256) { Fail '導入済みファイルが変更されています。上書き・削除せず中止します。' }
        } elseif ($null -ne $oldState) { Fail '導入済みファイルが不足しています。READMEの復旧手順を確認してください。' }
    }
    if ($Action -eq 'Uninstall' -and $null -eq $oldState) { Write-Output 'このパッチは導入されていません。' }
    else {
        if ($Action -eq 'Install') {
            Assert-Package
            $manifest = Read-Json (Join-Path $PSScriptRoot 'manifest.json')
            if ($manifest.schema_version -ne 1 -or $manifest.product -cne $product -or $manifest.patch_version -cnotmatch '^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$') { Fail '配布物の対応情報が不正です。' }
            Assert-FileList $manifest.files
            foreach ($file in $manifest.files) {
                if ((Hash (Join-Path $PSScriptRoot $file.name)) -cne $file.sha256) { Fail 'パッチのハッシュが対応情報と一致しません。' }
            }
            $supported = $false
            foreach ($build in $manifest.supported_builds) {
                $matched = $true
                $requiredOriginals = @('global.utoc','global.ucas','pakchunk0-Windows.pak','pakchunk0-Windows.utoc','pakchunk0-Windows.ucas','pakchunk0optional-Windows.pak','pakchunk0optional-Windows.utoc','pakchunk0optional-Windows.ucas')
                if (@($build.containers).Count -ne $requiredOriginals.Count) { Fail '対応版のコンテナ情報が不足しています。' }
                $originalSeen = @{}
                foreach ($file in $build.containers) {
                    if ($file.name -cnotin $requiredOriginals -or $originalSeen.ContainsKey([string]$file.name) -or $file.sha256 -cnotmatch '^[0-9a-f]{64}$') { Fail '対応版のコンテナ情報が不正です。' }
                    $originalSeen[[string]$file.name] = $true
                    $path = Join-Path $pakDir $file.name
                    Assert-NoLink $path
                    if (!(Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $file.size) { $matched = $false; break }
                    Write-Output ('対応版を確認中: ' + $file.name)
                    if ((Hash $path) -cne $file.sha256) { $matched = $false; break }
                }
                if ($matched) { $supported = $true; break }
            }
            if (!$supported) { Fail '未対応のゲーム版、または変更されたゲームファイルです。適用を中止しました。' }
        }
        Assert-GameStopped
        $backup = @{}
        foreach ($name in @($managedNames) + @($stateName)) {
            $path = Join-Path $pakDir $name
            if (Test-Path -LiteralPath $path -PathType Leaf) { $backup[$name] = [IO.File]::ReadAllBytes($path) }
        }
        $changed = @()
        try {
            foreach ($name in $managedNames) {
                $path = Join-Path $pakDir $name
                $changed += $name
                if ($Action -eq 'Install') { [IO.File]::WriteAllBytes($path,[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $name))) }
                else { [IO.File]::Delete($path) }
            }
            $changed += $stateName
            if ($Action -eq 'Install') {
                $state = @{schema_version=1; product=$product; patch_version=$manifest.patch_version; files=@($manifest.files)}
                [IO.File]::WriteAllText($statePath,($state | ConvertTo-Json -Depth 8),$utf8)
                foreach ($file in $manifest.files) {
                    if ((Hash (Join-Path $pakDir $file.name)) -cne $file.sha256) { Fail 'コピー後の整合性検査に失敗しました。' }
                }
            } else { [IO.File]::Delete($statePath) }
        } catch {
            foreach ($name in $changed) {
                $path = Join-Path $pakDir $name
                if ($backup.ContainsKey($name)) { [IO.File]::WriteAllBytes($path,$backup[$name]) }
                elseif (Test-Path -LiteralPath $path -PathType Leaf) { [IO.File]::Delete($path) }
            }
            Fail '処理に失敗したため、処理前の状態に戻しました。'
        }
        if ($Action -eq 'Install') { Write-Output '導入完了。ゲームの言語設定で簡体字中国語（日本語）を選択してください。' }
        else { Write-Output '削除完了。ゲーム本体とセーブデータは変更していません。' }
    }
} catch {
    if ($_.Exception -is [InvalidOperationException]) { [Console]::Error.WriteLine($_.Exception.Message) }
    else { [Console]::Error.WriteLine('処理を中止しました。ファイル形式、空き容量、書き込み権限を確認してください。') }
    exit 1
} finally {
    if ($null -ne $lock) { $lock.Dispose(); [IO.File]::Delete($lockPath) }
}
