"""配布ZIPの収録物、ハッシュ、翻訳LocResを独立に検証する。"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jp_patch.build import RELATIVE, STEM
from jp_patch.catalog import read_json, validate
from jp_patch.locres import loads
from jp_patch.tools import ROOT, repak


def check(path, *, release=False):
    binary_names={f'{STEM}.{extension}' for extension in ('pak','utoc','ucas')}
    names=binary_names | {'Patch.ps1','Install.cmd','Uninstall.cmd','README.md','THIRD_PARTY_NOTICES.md','manifest.json','SHA256SUMS.txt'}
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(names) or set(archive.namelist()) != names:
            raise ValueError('ZIPの収録物が許可一覧と一致しません')
        if any(item.file_size > 20_000_000 for item in archive.infolist()):
            raise ValueError('配布物のサイズが上限を超えています')
        files={name:archive.read(name) for name in names}
    expected=''.join(f'{hashlib.sha256(files[name]).hexdigest()}  {name}\n' for name in sorted(names-{'SHA256SUMS.txt'}))
    if files['SHA256SUMS.txt'] != expected.encode():
        raise ValueError('チェックサム一覧が一致しません')
    manifest=json.loads(files['manifest.json'])
    if release and (manifest['preview'] or manifest['patch_version'] != (ROOT/'VERSION').read_text().strip()):
        raise ValueError('試作版またはVERSIONと異なる版は正式公開できません')
    rows=[]
    if manifest['preview']:
        rows=read_json(ROOT/'translations/probe.json')['entries']
    else:
        for file in sorted((ROOT/'translations/release').glob('*.json')):
            rows.extend(read_json(file)['entries'])
    report=validate(read_json(ROOT/'catalog/game.json'),rows,read_json(ROOT/'translations/exclusions.json'),release=release)
    if report != manifest['coverage']:
        raise ValueError('翻訳集計が一致しません')
    if {item['name'] for item in manifest['files']} != binary_names or len(manifest['files']) != 3:
        raise ValueError('管理対象一覧が一致しません')
    for item in manifest['files']:
        if hashlib.sha256(files[item['name']]).hexdigest() != item['sha256']:
            raise ValueError('管理対象のハッシュが一致しません')
    with tempfile.TemporaryDirectory(prefix='jp-verify-') as temp:
        pak=Path(temp)/f'{STEM}.pak'
        pak.write_bytes(files[pak.name])
        listing=subprocess.run([str(repak()),'list',str(pak)],check=True,capture_output=True,text=True).stdout.splitlines()
        if listing != [RELATIVE]:
            raise ValueError('対象外の資産がPakに含まれています')
        unpacked=Path(temp)/'out'
        subprocess.run([str(repak()),'unpack',str(pak),'-o',str(unpacked)],check=True,capture_output=True)
        actual={(e.namespace,e.key):(e.namespace_hash,e.key_hash,e.source_hash,e.text) for e in loads((unpacked/RELATIVE).read_bytes())}
    expected={(r['namespace'],r['key']):(r['namespace_hash'],r['key_hash'],r['source_hash'],r['ja']) for r in rows if r['status'] != 'untranslated'}
    if actual != expected:
        raise ValueError('収録LocResが公開訳文と一致しません')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip',type=Path)
    parser.add_argument('--release',action='store_true')
    args=parser.parse_args()
    print(check(args.zip,release=args.release))
