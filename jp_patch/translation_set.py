"""試作と正式版の収録訳文を同じ規則で選ぶ。"""
from .catalog import index, read_json


def select_rows(formal, probe=(), *, preview=False):
    # 正式訳間の重複を、上書きで隠さず検出する。
    selected = index(formal)
    if preview:
        for identity, row in index(probe).items():
            if identity not in selected:
                selected[identity] = row
    return [selected[identity] for identity in sorted(selected)]


def load_rows(root, *, preview=False):
    formal = []
    for path in sorted((root/'translations/release').glob('*.json')):
        formal.extend(read_json(path)['entries'])
    probe = read_json(root/'translations/probe.json')['entries'] if preview else []
    return select_rows(formal, probe, preview=preview)
