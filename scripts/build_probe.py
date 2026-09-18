"""公開された試作訳文だけで日本語表示テスト用Pakを生成する。"""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp_patch.locres import Entry, dumps, loads
from jp_patch.tools import ROOT, repak, retoc, sha256


def main():
    rows = json.loads((ROOT / 'translations/probe.json').read_text('utf-8'))['entries']
    entries = [Entry(**{k: r[k] for k in ['namespace', 'namespace_hash', 'key', 'key_hash', 'source_hash']}, text=r['ja']) for r in rows]
    staging = ROOT / '.local/probe'
    relative = 'Hellraiser/Content/Localization/Game/zh-Hans/Game.locres'
    path = staging / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dumps(entries)
    assert loads(payload) == sorted(entries, key=lambda e: e.identity)
    path.write_bytes(payload)
    if {p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_file()} != {relative}:
        raise ValueError('試作フォルダに想定外のファイルがあります')
    output = ROOT / '.local/Hellraiser_Japanese_Probe_P.pak'
    subprocess.run([str(repak()), 'pack', str(staging), str(output), '--version', 'V11', '--quiet'], check=True)
    empty = ROOT / '.local/empty-iostore-input'
    empty.mkdir(parents=True, exist_ok=True)
    if any(empty.iterdir()):
        raise ValueError('空コンテナ生成用ディレクトリが空ではありません')
    companion = ROOT / '.local/probe-iostore' / output.with_suffix('.utoc').name
    companion.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(retoc()), 'to-zen', str(empty), str(companion), '--version', 'UE5_6'], check=True)
    print('日本語表示用の試作Pakを生成しました。正式配布には使用しないでください。')
    print('SHA-256: ' + sha256(output))
    for extension in ['.utoc', '.ucas']:
        item = companion.with_suffix(extension)
        print(item.name + ': ' + sha256(item))


if __name__ == '__main__':
    main()
