"""UE5.6用の小さなUFont参照設定を生成する。フォント本体・原本は読まない。

対応版のUnversioned UFont / FCompositeFont構造に限定したライター。
ゲーム更新でプロパティ配置が変わる場合は、対応版検証と再実装が必要。
"""
from pathlib import Path
import struct


MAGIC = 0x9E2A83C1
BASE = '/Game/UI/Font/'
ASSETS = ('EBGaramond/EBGaramond_Font', 'FiraSansCondensed/FiraSansCondensed_Font')
JAPANESE_RANGES = ((0x3040, 0x309F), (0x30A0, 0x30FF), (0x4E00, 0x9FFF), (0x3300, 0x33FF))
KOREAN_RANGES = ((0x1100, 0x11FF), (0xAC00, 0xD7AF))


def packed(fmt, *values):
    return struct.pack('<' + fmt, *values)


def fstring(value):
    raw = value.encode('ascii') + b'\0'
    return packed('i', len(raw)) + raw


def recipe(asset):
    """既存の参照先と、日本語パッチ用に指定する表示設定。"""
    if asset not in ASSETS:
        raise ValueError('未定義のフォント設定です')
    primary = asset == ASSETS[0]
    styles = ('Default', 'Bold', 'Medium', 'SemiBold') if primary else ('Default', 'Bold')
    weights = ('Regular', 'Bold', 'Medium', 'SemiBold') if primary else ('Regular', 'Bold')
    default = [(style, BASE + ('Primary/ElMessiri-' if primary else 'Secondary/Sarala-') + weight)
               for style, weight in zip(styles, weights)]

    def noto(language):
        return [(style, BASE + 'Fallback/NotoSans' + language + '-' +
                 ('Bold' if style in ('Bold', 'SemiBold') else 'Regular')) for style in styles]

    subs = []
    if not primary:
        subs.append(('ru', ((0x400, 0x4FF),), [(s, BASE + 'Fallback/Inter_18pt-' + w) for s, w in zip(styles, weights)]))
    subs.extend([('ja', JAPANESE_RANGES, noto('JP')), ('ko', KOREAN_RANGES, noto('KR')),
                 # 句読点・全角英数・拡張漢字も同じ書体にし、代替フォントとの混在を避ける。
                 ('zh-Hans', ((0, 0x10FFFF),), noto('JP'))])
    return default, [('Default', BASE + 'Fallback/Arial-Unicode-MS')], subs


class FontPackage:
    def __init__(self, asset):
        self.asset = asset
        self.names = []
        self.imports = []
        self.faces = {}

    def name(self, value):
        if value not in self.names:
            self.names.append(value)
        return packed('ii', self.names.index(value), 0)

    def add_import(self, package, kind, outer, name):
        self.imports.append(self.name(package) + self.name(kind) + packed('i', outer) + self.name(name) + packed('i', 0))
        return -len(self.imports)

    def face(self, path):
        if path not in self.faces:
            package = self.add_import('/Script/CoreUObject', 'Package', 0, path)
            self.faces[path] = self.add_import('/Script/Engine', 'FontFace', package, path.rsplit('/', 1)[1])
        return self.faces[path]

    def typeface(self, entries):
        result = packed('Hi', 0x300, len(entries))
        for style, path in entries:
            result += packed('H', 0x500) + self.name(style) + packed('iii', 1, self.face(path), 0)
        return result

    def build(self):
        package = BASE + self.asset
        object_name = self.name(self.asset.rsplit('/', 1)[1])
        self.name(package)
        engine = self.add_import('/Script/CoreUObject', 'Package', 0, '/Script/Engine')
        font_class = self.add_import('/Script/CoreUObject', 'Class', engine, 'Font')
        font_template = self.add_import('/Script/Engine', 'Font', engine, 'Default__Font')
        default, fallback, subs = recipe(self.asset)
        # UFont: FontCacheType=Runtime (field 0), CompositeFont (field 15).
        body = packed('HHBH', 0x200, 0x30E, 1, 0x700)
        body += self.typeface(default) + packed('H', 0x300) + self.typeface(fallback)
        body += packed('i', len(subs))
        for culture, ranges, faces in subs:
            body += packed('Hi', 0x900, len(ranges))
            for lower, upper in ranges:
                # TRange<int32>の両端をInclusiveで指定。
                body += packed('HHBiHBi', 0x500, 0x500, 1, lower, 0x500, 1, upper)
            body += fstring(culture) + self.typeface(faces) + packed('f', 1.0)
        body += packed('ii', 0, 0)  # UObject GUIDなし、UFont CharRemapなし。

        names = b''.join(fstring(n) + packed('HH', 0, 0) for n in self.names)
        imports = b''.join(self.imports)
        deps = list(self.faces.values()) + [font_class, font_template]
        dependency_data = packed('i' * len(deps), *deps)

        def summary(header_size, name_offset, import_offset, export_offset, depends_offset, registry_offset, preload_offset):
            out = packed('I5i', MAGIC, -9, 0, 0, 0, 0) + bytes(20) + packed('ii', header_size, 0)
            out += fstring(package) + packed('I', 0x80002200)  # Cooked, unversioned, editor filtered.
            out += packed('14i', len(self.names), name_offset, 0, 0, 0, 0, 1, export_offset, len(self.imports), import_offset, 0, 0, 0, 0)
            out += packed('6i', 0, depends_offset, 0, 0, 0, 0)
            out += packed('3i', 1, 1, len(self.names))  # generation
            out += (packed('HHHI', 0, 0, 0, 0) + fstring('')) * 2
            out += packed('5i', 0, 0, 0, 0, registry_offset)
            out += packed('q', header_size + len(body))
            out += packed('5i', 0, 0, len(deps), preload_offset, len(self.names)) + packed('qi', -1, -1)
            return out

        summary_size = len(summary(0, 0, 0, 0, 0, 0, 0))
        import_offset = summary_size + len(names)
        export_offset = import_offset + len(imports)
        depends_offset = export_offset + 96
        registry_offset = depends_offset + 4
        preload_offset = registry_offset + 4
        header_size = preload_offset + len(dependency_data)
        export = packed('4i', font_class, 0, font_template, 0) + object_name
        export += packed('Iqq', 0xB, len(body), header_size)
        # public asset; faces must exist before serialization, class/template before creation.
        export += packed('13i', 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, len(self.faces), 2, 0)
        header = summary(header_size, summary_size, import_offset, export_offset, depends_offset, registry_offset, preload_offset)
        header += names + imports + export + packed('ii', 0, 0) + dependency_data
        assert len(header) == header_size
        return header, body + packed('I', MAGIC)


def generate():
    """公開ソースだけから作る4ファイル。FontFace/ufont等は収録しない。"""
    result = {}
    for asset in ASSETS:
        header, body = FontPackage(asset).build()
        path = 'Hellraiser/Content/UI/Font/' + asset
        result[path + '.uasset'] = header
        result[path + '.uexp'] = body
    return result


def write_assets(directory):
    for relative, data in generate().items():
        path = Path(directory) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
