import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jp_patch.build import build
from jp_patch.tools import sha256
from check_package import check


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='同一入力の再ビルドを照合する')
    parser.add_argument('--release',action='store_true')
    args=parser.parse_args()
    first,_=build(preview=not args.release)
    expected=sha256(first)
    second,_=build(preview=not args.release)
    if sha256(second) != expected:
        raise ValueError('再ビルドのSHA-256が一致しません')
    check(second,release=args.release)
    print('再現性・配布物検査: 成功')
