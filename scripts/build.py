import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jp_patch.build import build
from jp_patch.tools import sha256


def main():
    parser=argparse.ArgumentParser(description='ゲーム原本不要の日本語パッチビルド')
    parser.add_argument('--preview',action='store_true',help='70件の試作訳だけを収録。正式配布しない')
    args=parser.parse_args()
    try:
        output,report=build(preview=args.preview)
    except Exception as error:
        print('ビルドに失敗しました: ' + (str(error) if isinstance(error,ValueError) else type(error).__name__),file=sys.stderr)
        return 1
    print(output.name)
    print('SHA-256: '+sha256(output))
    print('検査結果: '+str(report))
    return 0


if __name__=='__main__':
    sys.exit(main())
