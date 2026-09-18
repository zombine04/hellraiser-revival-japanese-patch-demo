"""本デモのLocRes v3を読み書きする。元の識別用ハッシュは再計算しない。"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from io import BytesIO
import struct

MAGIC = bytes.fromhex('0e147475674a03fc4a15909dc3377f1b')
MAX_ITEMS = 1_000_000


@dataclass(frozen=True)
class Entry:
    namespace: str
    namespace_hash: int
    key: str
    key_hash: int
    source_hash: int
    text: str

    @property
    def identity(self):
        return self.namespace, self.key

    def metadata(self):
        return {k: v for k, v in asdict(self).items() if k != 'text'}


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def read(self, size):
        if size < 0 or self.pos + size > len(self.data):
            raise ValueError('LocResの範囲外参照')
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def number(self, fmt):
        return struct.unpack('<' + fmt, self.read(struct.calcsize('<' + fmt)))[0]

    def count(self):
        n = self.number('I')
        if n > MAX_ITEMS:
            raise ValueError('LocResの件数が上限を超えています')
        return n

    def string(self):
        size = self.number('i')
        if not size:
            return ''
        data = self.read(abs(size) * (2 if size < 0 else 1))
        end = b'\0\0' if size < 0 else b'\0'
        if not data.endswith(end):
            raise ValueError('LocRes文字列の終端が不正です')
        return data[:-len(end)].decode('utf-16-le' if size < 0 else 'utf-8')


def loads(data: bytes) -> list[Entry]:
    r = Reader(data)
    if r.read(16) != MAGIC or r.number('B') != 3:
        raise ValueError('対応する形式はLocRes v3のみです')
    offset = r.number('q')
    if not 33 <= offset <= len(data) - 4:
        raise ValueError('LocRes文字列テーブルの位置が不正です')
    r.pos = offset
    strings = []
    references = []
    for _ in range(r.count()):
        strings.append(r.string())
        references.append(r.number('i'))
    if r.pos != len(data):
        raise ValueError('LocRes末尾に不明なデータがあります')
    r.pos = 25
    total = r.count()
    entries = []
    identities = set()
    actual_refs = Counter()
    for _ in range(r.count()):
        ns_hash, ns = r.number('I'), r.string()
        for _ in range(r.count()):
            key_hash, key = r.number('I'), r.string()
            source_hash, index = r.number('I'), r.number('i')
            if not 0 <= index < len(strings):
                raise ValueError('LocRes文字列インデックスが不正です')
            entry = Entry(ns, ns_hash, key, key_hash, source_hash, strings[index])
            if entry.identity in identities:
                raise ValueError('LocResのキーが重複しています')
            identities.add(entry.identity)
            entries.append(entry)
            actual_refs[index] += 1
    if r.pos != offset or len(entries) != total:
        raise ValueError('LocResの件数または境界が一致しません')
    if any(n != actual_refs[i] for i, n in enumerate(references)):
        raise ValueError('LocRes文字列の参照数が一致しません')
    return entries


def dumps(entries: list[Entry]) -> bytes:
    ordered = sorted(entries, key=lambda e: e.identity)
    if len({e.identity for e in ordered}) != len(ordered):
        raise ValueError('LocResのキーが重複しています')
    stream = BytesIO()

    def number(fmt, n):
        stream.write(struct.pack('<' + fmt, n))

    def string(value):
        if '\0' in value:
            raise ValueError('文字列にNULを含めることはできません')
        if value.isascii():
            payload = value.encode('ascii') + b'\0'
            number('i', len(payload))
        else:
            payload = value.encode('utf-16-le') + b'\0\0'
            number('i', -(len(payload) // 2))
        stream.write(payload)

    groups = defaultdict(list)
    strings = list(dict.fromkeys(e.text for e in ordered))
    indexes = {s: i for i, s in enumerate(strings)}
    refs = Counter(e.text for e in ordered)
    for e in ordered:
        groups[e.namespace].append(e)
    stream.write(MAGIC)
    number('B', 3)
    number('q', 0)
    number('I', len(ordered))
    number('I', len(groups))
    for ns, group in groups.items():
        if len({e.namespace_hash for e in group}) != 1:
            raise ValueError('同一名前空間のハッシュが不一致です')
        number('I', group[0].namespace_hash)
        string(ns)
        number('I', len(group))
        for e in group:
            number('I', e.key_hash)
            string(e.key)
            number('I', e.source_hash)
            number('i', indexes[e.text])
    table_offset = stream.tell()
    number('I', len(strings))
    for s in strings:
        string(s)
        number('i', refs[s])
    stream.seek(17)
    number('q', table_offset)
    return stream.getvalue()
