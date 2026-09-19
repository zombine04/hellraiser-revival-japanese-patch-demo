"""同名のキーを持つ自作データで、領域間の取り違えと欠落を検査する。"""
import json
from pathlib import Path
import tempfile
import unittest

from jp_patch.catalog import metadata
from jp_patch.locres import Entry
from jp_patch.regions import GAME, ENGINE, REGIONS, coverage
from jp_patch.translation_set import load_regions


class RegionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for i, region in enumerate(REGIONS):
            entry = Entry('自作の共通名前空間', 1, 'same-key', 2, 10+i, 'Self-authored fixture')
            self.write(region.catalog, dict(schema_version=1, game_version='test-build', entries=[metadata(entry)]))
            self.write(region.translations+'/sample.json', dict(schema_version=1, entries=[entry.metadata() | dict(ja='ゲーム側' if region == GAME else 'エンジン側', status='reviewed')]))
            self.write(region.exclusions, [])
        self.write(GAME.probe, dict(schema_version=1, entries=[]))
        self.write(ENGINE.scope, dict(schema_version=1, rationale='自作の検証対象', namespaces={'自作の共通名前空間':['same-key']}))

    def write(self, relative, data):
        path = self.root/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')

    def read(self, relative):
        return json.loads((self.root/relative).read_text('utf8'))

    def test_identical_identities_remain_in_separate_regions(self):
        data = load_regions(self.root, release=True)
        self.assertEqual(data['game']['rows'][0]['ja'], 'ゲーム側')
        self.assertEqual(data['engine']['rows'][0]['ja'], 'エンジン側')
        report = coverage({name:domain['report'] for name,domain in data.items()})
        self.assertEqual(report['reviewed'], 2)
        self.assertEqual(report['regions']['engine']['total'], 1)

    def test_swapped_region_rows_are_rejected(self):
        self.write(ENGINE.translations+'/sample.json', self.read(GAME.translations+'/sample.json'))
        with self.assertRaises(ValueError):
            load_regions(self.root, release=True)

    def test_engine_missing_or_unreviewed_blocks_release(self):
        original = self.read(ENGINE.translations+'/sample.json')
        for rows in ([], [original['entries'][0] | {'status':'needs_review'}]):
            self.write(ENGINE.translations+'/sample.json', dict(schema_version=1, entries=rows))
            with self.assertRaises(ValueError):
                load_regions(self.root, release=True)

    def test_catalog_cannot_silently_shrink_engine_scope(self):
        catalog = self.read(ENGINE.catalog)
        self.write(ENGINE.catalog, catalog | {'entries':[]})
        self.write(ENGINE.translations+'/sample.json', dict(schema_version=1, entries=[]))
        with self.assertRaises(ValueError):
            load_regions(self.root, release=True)

    def test_different_game_versions_are_rejected(self):
        self.write(ENGINE.catalog, self.read(ENGINE.catalog) | {'game_version':'another-build'})
        with self.assertRaises(ValueError):
            load_regions(self.root, release=True)
