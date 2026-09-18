"""ローカル原文から公開用の識別情報だけを生成する。"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jp_patch.catalog import compare, metadata, read_json
from jp_patch.locres import Entry
from jp_patch.tools import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'catalog/game.json')
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    entries = [Entry(**row) for row in read_json(ROOT/'.local/source-en.json')]
    inventory = read_json(ROOT/'.local/inventory.json')
    catalog = dict(schema_version=1, game_version=inventory['game_version'], entries=[metadata(e) for e in sorted(entries, key=lambda e:e.identity)])
    if args.compare:
        diff = compare(read_json(args.compare), catalog)
        (ROOT/'.local/catalog-diff.json').write_text(json.dumps(diff, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('更新差分: ' + ', '.join(f'{k}={len(v)}' for k,v in diff.items()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'原文を含まない識別情報を生成: {len(entries)}件')


if __name__ == '__main__':
    main()
