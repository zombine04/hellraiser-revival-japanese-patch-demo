from pathlib import Path
import hashlib
import json
import os
import platform
import tarfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tool(name: str) -> Path:
    if name not in {'repak', 'retoc'}:
        raise ValueError('未定義のツールです')
    lock = json.loads((ROOT / 'tools.lock.json').read_text('utf-8'))[name]
    target = {'Windows': 'windows', 'Linux': 'linux'}.get(platform.system())
    if target is None or platform.machine().lower() not in {'amd64', 'x86_64'}:
        raise ValueError('開発ツールはWindows/Linux x64に対応しています')
    asset = lock[target]
    folder = ROOT / '.tools' / f'{name}-{lock["version"]}-{target}'
    folder.mkdir(parents=True, exist_ok=True)
    archive_path = folder / ('download.zip' if target == 'windows' else 'download.tar.xz')
    if not archive_path.exists():
        with urlopen(asset['url'], timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != asset['sha256']:
            raise ValueError(name + 'のダウンロード検証に失敗しました')
        archive_path.write_bytes(data)
    if sha256(archive_path) != asset['sha256']:
        raise ValueError(name + 'の保存済みアーカイブの検証に失敗しました')
    binary = name + ('.exe' if target == 'windows' else '')
    if target == 'windows':
        with zipfile.ZipFile(archive_path) as archive:
            matches = [n for n in archive.namelist() if Path(n).name == binary]
            if len(matches) != 1:
                raise ValueError(name + 'の配布構成が不正です')
            data = archive.read(matches[0])
    else:
        with tarfile.open(archive_path) as archive:
            matches = [m for m in archive.getmembers() if m.isfile() and Path(m.name).name == binary]
            if len(matches) != 1:
                raise ValueError(name + 'の配布構成が不正です')
            data = archive.extractfile(matches[0]).read()
    path = folder / binary
    if not path.exists() or hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(data).digest():
        path.write_bytes(data)
    if target == 'linux':
        os.chmod(path, 0o755)
    return path


def repak() -> Path:
    return tool('repak')


def retoc() -> Path:
    return tool('retoc')
