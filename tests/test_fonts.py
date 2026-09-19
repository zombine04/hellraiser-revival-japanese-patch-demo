"""生成した参照設定のバイナリを独立に読み、字形の参照先を検証する。"""
import io
import struct
import unittest

from jp_patch.fonts import ASSETS, generate


class Reader:
    def __init__(self, data):
        self.stream = io.BytesIO(data)

    def read(self, fmt):
        values = struct.unpack('<' + fmt, self.stream.read(struct.calcsize('<' + fmt)))
        return values[0] if len(values) == 1 else values

    def string(self):
        return self.stream.read(self.read('i')).rstrip(b'\0').decode('ascii')


def inspect(header, payload):
    reader = Reader(header)
    assert reader.read('I5i') == (0x9E2A83C1, -9, 0, 0, 0, 0)
    reader.stream.seek(44)
    assert reader.read('i') == len(header)
    assert reader.read('i') == 0
    package = reader.string()
    assert reader.read('I') == 0x80002200
    name_count, name_offset = reader.read('ii')
    reader.stream.read(16)
    assert reader.read('i') == 1
    export_offset = reader.read('i')
    import_count, import_offset = reader.read('ii')
    reader.stream.seek(name_offset)
    names = []
    for _ in range(name_count):
        names.append(reader.string())
        reader.stream.read(4)
    assert reader.stream.tell() == import_offset
    imports = []
    for _ in range(import_count):
        row = reader.read('8i')
        imports.append((names[row[2]], row[4], names[row[5]]))
    assert reader.stream.tell() == export_offset
    font_class, _, template, _ = reader.read('4i')
    assert imports[-font_class - 1][2] == 'Font'
    assert imports[-template - 1][2] == 'Default__Font'
    reader.stream.read(12)
    size, offset = reader.read('qq')
    assert offset == len(header) and size == len(payload) - 4
    reader = Reader(payload)

    def fragment(value):
        assert reader.read('H') == value

    def typeface():
        fragment(0x300)
        faces = {}
        for _ in range(reader.read('i')):
            fragment(0x500)
            name, number, cooked, index, subface = reader.read('5i')
            assert (number, cooked, subface) == (0, 1, 0)
            kind, outer, object_name = imports[-index - 1]
            assert kind == 'FontFace'
            kind, _, path = imports[-outer - 1]
            assert kind == 'Package' and path.rsplit('/', 1)[1] == object_name
            faces[names[name]] = path
        return faces

    assert reader.read('HHBH') == (0x200, 0x30E, 1, 0x700)
    default = typeface()
    fragment(0x300)
    fallback = typeface()
    subs = {}
    for _ in range(reader.read('i')):
        fragment(0x900)
        ranges = []
        for _ in range(reader.read('i')):
            fragment(0x500)
            bounds = []
            for _ in range(2):
                fragment(0x500)
                assert reader.read('B') == 1
                bounds.append(reader.read('i'))
            ranges.append(tuple(bounds))
        culture = reader.string()
        faces = typeface()
        assert reader.read('f') == 1.0
        subs[culture] = (ranges, faces)
    assert reader.read('iiI') == (0, 0, 0x9E2A83C1)
    assert not reader.stream.read()
    return package, default, fallback, subs


class FontTests(unittest.TestCase):
    def test_generated_packages_use_japanese_faces_for_every_style(self):
        files = generate()
        self.assertEqual(len(files), 4)
        self.assertLess(sum(map(len, files.values())), 10000)
        for asset in ASSETS:
            prefix = 'Hellraiser/Content/UI/Font/' + asset
            package, default, fallback, subs = inspect(files[prefix + '.uasset'], files[prefix + '.uexp'])
            self.assertEqual(package, '/Game/UI/Font/' + asset)
            ranges, faces = subs['zh-Hans']
            self.assertEqual(ranges, [(0, 0x10FFFF)])
            self.assertEqual(set(faces), set(default))
            for style, path in faces.items():
                weight = 'Bold' if style in ('Bold', 'SemiBold') else 'Regular'
                self.assertEqual(path, '/Game/UI/Font/Fallback/NotoSansJP-' + weight)
            self.assertIn('ja', subs)
            self.assertIn('ko', subs)
            self.assertEqual(fallback['Default'], '/Game/UI/Font/Fallback/Arial-Unicode-MS')
            expected = 'ElMessiri-Regular' if asset == ASSETS[0] else 'Sarala-Regular'
            self.assertTrue(default['Default'].endswith('/' + expected))
            if asset == ASSETS[1]:
                self.assertTrue(subs['ru'][1]['Default'].endswith('/Inter_18pt-Regular'))

    def test_no_font_data_and_deterministic(self):
        files = generate()
        self.assertEqual(files, generate())
        for path in files:
            self.assertTrue(path.endswith(('.uasset', '.uexp')))
            self.assertNotIn('/Fallback/', path)
