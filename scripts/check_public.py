"""Gitの公開対象を検査する。機密値そのものは出力しない。"""
from __future__ import annotations

import argparse
from pathlib import PurePosixPath
import re
import subprocess
import sys

FORBIDDEN_SUFFIXES = {
    '.pak', '.utoc', '.ucas', '.locres', '.locmeta', '.uasset', '.uexp',
    '.ubulk', '.ufont', '.usmap', '.dll', '.exe', '.zip', '.7z', '.sav', '.dmp',
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
    parser.add_argument('--staged', action='store_true')
    args = parser.parse_args()
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
