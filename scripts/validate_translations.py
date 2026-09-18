from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp_patch.catalog import read_json, validate
from jp_patch.tools import ROOT


def main():
    catalog=read_json(ROOT/'catalog/game.json')
    try:
        probe=validate(catalog,read_json(ROOT/'translations/probe.json')['entries'])
        rows=[]
        for path in sorted((ROOT/'translations/release').glob('*.json')):
            rows.extend(read_json(path)['entries'])
        formal=validate(catalog,rows,read_json(ROOT/'translations/exclusions.json'))
    except (ValueError, KeyError, TypeError):
        print('翻訳データの構造・書式検査に失敗しました。原文は表示しません。',file=sys.stderr)
        return 1
    print('試作: '+str(probe))
    print('正式版: '+str(formal))
    return 0


if __name__=='__main__':
    sys.exit(main())
