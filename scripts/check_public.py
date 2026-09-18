"""Gitの公開対象を検査する。機密値そのものは出力しない。"""
from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys

FORBIDDEN_SUFFIXES = {
    '.pak', '.utoc', '.ucas', '.locres', '.locmeta', '.uasset', '.uexp',
    '.ubulk', '.ufont', '.usmap', '.dll', '.exe', '.zip', '.7z', '.sav', '.dmp', '.log',
}
FORBIDDEN_DIRS = {'.local', 'private', '.tools', 'dist', '.venv', '__pycache__'}
PATTERNS = {
    '認証トークン': re.compile(rb'(?:github_' + rb'pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})'),
    '秘密鍵': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE' + rb' KEY-----'),
    '認証情報付きURL': re.compile(rb'https?://[^\s/"<>]+:[^\s/"<>]+@'),
    'トークン付きURL': re.compile(rb'https?://[^\s/"<>@]{20,}@'),
    '個人の絶対パス': re.compile(rb'[A-Za-z]:[\\/](?:Users|MyProjects|Steam)[\\/]'),
}


def inspect(path: str, content: bytes) -> list[str]:
    p = PurePosixPath(path)
    errors = []
    if p.suffix.lower() in FORBIDDEN_SUFFIXES or FORBIDDEN_DIRS.intersection(p.parts):
        errors.append('公開禁止の資産・作業ファイル')
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        errors.append('環境変数ファイル')
    if b'\0' in content:
        errors.append('許可されていないバイナリ')
    for name, pattern in PATTERNS.items():
        if pattern.search(content):
            errors.append(name)
    return errors


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--staged', action='store_true')
    scope.add_argument('--history', action='store_true', help='ローカルに存在する全参照の履歴を検査する')
    args = parser.parse_args()
    if args.history:
        objects = set()
        failed = set()
        for commit in git('rev-list', '--all').decode('ascii').splitlines():
            for record in git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
                if not record:
                    continue
                header, raw_path = record.split(b'\t', 1)
                mode, kind, oid = header.decode('ascii').split()
                if kind != 'blob':
                    continue
                path = raw_path.decode('utf-8')
                if (path, oid) in objects:
                    continue
                objects.add((path, oid))
                for error in inspect(path, git('cat-file', 'blob', oid)):
                    failed.add((path, error))
        for path, error in sorted(failed):
            print(f'{path}: {error}')
        print(f'全参照の履歴 {len(objects)} 件を検査: {len(failed)} 件の問題')
        return int(bool(failed))
    paths = git('diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z') if args.staged else git('ls-files', '-z')
    failures = 0
    count = 0
    for raw in paths.split(b'\0'):
        if not raw:
            continue
        path = raw.decode('utf-8')
        content = git('show', ':' + path)
        count += 1
        for error in inspect(path, content):
            print(f'{path}: {error}')
            failures += 1
    print(f'公開対象 {count} ファイルを検査: {failures} 件の問題')
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
