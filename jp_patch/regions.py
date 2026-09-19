"""領域ごとの識別情報と出力先を固定し、GameとEngineのキーを分離する。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    name: str
    catalog: str
    translations: str
    exclusions: str
    locres: str
    probe: str | None = None
    scope: str | None = None


GAME = Region('game', 'catalog/game.json', 'translations/release',
              'translations/exclusions.json',
              'Hellraiser/Content/Localization/Game/zh-Hans/Game.locres',
              probe='translations/probe.json')
ENGINE = Region('engine', 'catalog/engine.json', 'translations/engine',
                'translations/engine-exclusions.json',
                'Engine/Content/Localization/Engine/zh-Hans/Engine.locres',
                scope='catalog/engine-scope.json')
REGIONS = (GAME, ENGINE)


def scope_keys(scope):
    if scope['schema_version'] != 1 or not scope['rationale'].strip():
        raise ValueError('Engine対象範囲の形式・根拠が不正です')
    pairs = [(namespace, key) for namespace, keys in scope['namespaces'].items() for key in keys]
    if len(set(pairs)) != len(pairs) or not pairs:
        raise ValueError('Engine対象範囲が空または重複しています')
    return set(pairs)


def coverage(reports):
    totals = {key: sum(report[key] for report in reports.values()) for key in next(iter(reports.values()))}
    return totals | {'regions': reports}
