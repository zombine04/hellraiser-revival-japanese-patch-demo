"""試作と正式版の収録訳文を同じ規則で選ぶ。"""
from .catalog import index, read_json, validate
from .regions import GAME, REGIONS, scope_keys


def select_rows(formal, probe=(), *, preview=False):
    # 正式訳間の重複を、上書きで隠さず検出する。
    selected = index(formal)
    if preview:
        for identity, row in index(probe).items():
            if identity not in selected:
                selected[identity] = row
    return [selected[identity] for identity in sorted(selected)]


def load_rows(root, *, preview=False, region=GAME):
    formal = []
    for path in sorted((root/region.translations).glob('*.json')):
        formal.extend(read_json(path)['entries'])
    probe = read_json(root/region.probe)['entries'] if preview and region.probe else []
    return select_rows(formal, probe, preview=preview)


def load_regions(root, *, preview=False, release=False):
    result = {}
    versions = set()
    for region in REGIONS:
        catalog = read_json(root/region.catalog)
        if region.scope and set(index(catalog['entries'])) != scope_keys(read_json(root/region.scope)):
            raise ValueError('Engineカタログが調査済みの対象範囲と一致しません')
        rows = load_rows(root, preview=preview, region=region)
        report = validate(catalog, rows, read_json(root/region.exclusions), release=release)
        versions.add(catalog['game_version'])
        result[region.name] = dict(catalog=catalog, rows=rows, report=report)
    if len(versions) != 1:
        raise ValueError('領域間で対応ゲーム版が一致しません')
    return result
