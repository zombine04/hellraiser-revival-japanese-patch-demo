"""公開データから配布物を生成する。ゲーム本体へのアクセスは禁止する。"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from .catalog import read_json, validate
from .locres import Entry, dumps, loads
from .tools import ROOT, repak, retoc, sha256

RELATIVE = 'Hellraiser/Content/Localization/Game/zh-Hans/Game.locres'
STEM = 'Hellraiser_Japanese_P'


def deterministic_zip(files, output):
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(files.items()):
            if Path(name).name != name or '/' in name or '\\' in name:
                raise ValueError('ZIPの収録パスが不正です')
            info = zipfile.ZipInfo(name, date_time=(2026,1,1,0,0,0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def build(*, preview=False):
    version = (ROOT/'VERSION').read_text('ascii').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('VERSIONの形式が不正です')
    rows = []
    if preview:
        rows = read_json(ROOT/'translations/probe.json')['entries']
        version += '-preview'
    else:
        for file in sorted((ROOT/'translations/release').glob('*.json')):
            rows.extend(read_json(file)['entries'])
    catalog = read_json(ROOT/'catalog/game.json')
    report = validate(catalog, rows, read_json(ROOT/'translations/exclusions.json'), release=not preview)
    entries = [Entry(**{k:row[k] for k in ('namespace','namespace_hash','key','key_hash','source_hash')}, text=row['ja']) for row in rows if row['status'] != 'untranslated']
    if not entries:
        raise ValueError('ビルドする訳文がありません')
    payload = dumps(entries)
    if loads(payload) != sorted(entries, key=lambda e:e.identity):
        raise ValueError('LocRes読み戻し検査に失敗しました')
    destination = ROOT/'dist'
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jp-build-') as temp:
        work = Path(temp)
        staging = work/'staging'
        locres = staging/RELATIVE
        locres.parent.mkdir(parents=True)
        locres.write_bytes(payload)
        pak = work/f'{STEM}.pak'
        subprocess.run([str(repak()),'pack',str(staging),str(pak),'--version','V11','--quiet'],check=True,capture_output=True)
        listing = subprocess.run([str(repak()),'list',str(pak)],check=True,capture_output=True,text=True).stdout.splitlines()
        if listing != [RELATIVE]:
            raise ValueError('Pakに対象外の資産が含まれています')
        unpacked = work/'unpacked'
        subprocess.run([str(repak()),'unpack',str(pak),'-o',str(unpacked)],check=True,capture_output=True)
        if (unpacked/RELATIVE).read_bytes() != payload:
            raise ValueError('Pak読み戻し検査に失敗しました')
        empty = work/'empty'
        empty.mkdir()
        iostore = work/'iostore'/f'{STEM}.utoc'
        iostore.parent.mkdir()
        subprocess.run([str(retoc()),'to-zen',str(empty),str(iostore),'--version','UE5_6'],check=True,capture_output=True)
        files = {pak.name:pak.read_bytes(),iostore.name:iostore.read_bytes(),iostore.with_suffix('.ucas').name:iostore.with_suffix('.ucas').read_bytes()}
    manifest = dict(schema_version=1, product='hellraiser-revival-demo-japanese', patch_version=version, preview=preview, game_version=catalog['game_version'], coverage=report,
                    files=[dict(name=name,sha256=hashlib.sha256(content).hexdigest()) for name,content in sorted(files.items())], supported_builds=read_json(ROOT/'catalog/supported-builds.json'))
    files['manifest.json'] = (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    for name in ('Patch.ps1','Install.cmd','Uninstall.cmd'):
        raw = (ROOT/'distribution'/name).read_text('utf-8-sig').replace('\r\n','\n')
        files[name] = raw.replace('\n','\r\n').encode('utf-8-sig' if name.endswith('.ps1') else 'ascii')
    for name in ('README.md','THIRD_PARTY_NOTICES.md'):
        files[name] = (ROOT/name).read_text('utf-8-sig').replace('\r\n','\n').encode()
    if preview:
        files['README.md'] = ('# 表示確認用の試作版\n\n70件の試作訳だけを含みます。正式版ではありません。\n\n'.encode() + files['README.md'])
    files['SHA256SUMS.txt'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name,data in sorted(files.items())).encode('ascii')
    output = destination/f'Hellraiser_Revival_Demo_Japanese_v{version}.zip'
    deterministic_zip(files, output)
    output.with_suffix('.sha256').write_text(f'{sha256(output)}  {output.name}\n',encoding='ascii')
    return output, report
