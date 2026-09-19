"""原文を公開せず、識別情報と書式制約を照合する。"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

IDENTITY = ('namespace', 'key')
HASHES = ('namespace_hash', 'key_hash', 'source_hash')
PLACEHOLDERS = re.compile(r'\{[^{}\r\n]*\}|%(?:\d+\$)?[-+#0 ]*\d*(?:\.\d+)?[diouxXeEfFgGcs]')
TAGS = re.compile(r'<[^>\r\n]*>')


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('JSONのフィールドが重複しています')
            result[key] = value
        return result
    return json.loads(Path(path).read_text('utf-8-sig'), object_pairs_hook=unique)


def signature(text):
    return dict(placeholders=sorted(PLACEHOLDERS.findall(text)), tags=TAGS.findall(text), newlines=text.count('\n'))


def source_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def metadata(entry):
    return entry.metadata() | dict(source_text_sha256=source_digest(entry.text), **signature(entry.text))


def index(rows):
    result = {}
    for row in rows:
        identity = tuple(row[k] for k in IDENTITY)
        if identity in result:
            raise ValueError('名前空間とキーが重複しています')
        if not all(isinstance(row[k], str) for k in IDENTITY):
            raise ValueError('識別情報は文字列で指定してください')
        for name in HASHES:
            if type(row[name]) is not int or not 0 <= row[name] <= 0xffffffff:
                raise ValueError('ハッシュは符号なし32ビット整数で指定してください')
        result[identity] = row
    return result


def validate(catalog, rows, exclusions=(), *, release=False):
    if set(catalog) != {'schema_version', 'game_version', 'entries'} or catalog['schema_version'] != 1:
        raise ValueError('原本メタデータの形式が不正です')
    fields = set(IDENTITY + HASHES) | {'source_text_sha256', 'placeholders', 'tags', 'newlines'}
    for original in catalog['entries']:
        if set(original) != fields or not re.fullmatch(r'[0-9a-f]{64}', original['source_text_sha256']):
            raise ValueError('原本メタデータに未定義のフィールドまたは不正なハッシュがあります')
        if type(original['newlines']) is not int or original['newlines'] < 0:
            raise ValueError('改行の制約が不正です')
        for name, pattern in (('placeholders', PLACEHOLDERS), ('tags', TAGS)):
            if not isinstance(original[name], list) or any(not isinstance(s, str) or not pattern.fullmatch(s) for s in original[name]):
                raise ValueError('書式制約の形式が不正です')
    source = index(catalog['entries'])
    translated = index(rows)
    if set(translated) - set(source):
        raise ValueError('未知のキーが翻訳に含まれています')
    excluded = {}
    for row in exclusions:
        if set(row) != {'namespace', 'key', 'reason', 'evidence'} or not row['reason'].strip() or not row['evidence'].strip():
            raise ValueError('対象外の項目には理由と確認根拠が必要です')
        identity = tuple(row[k] for k in IDENTITY)
        if identity not in source or identity in excluded or identity in translated:
            raise ValueError('対象外のキーが不正または重複しています')
        excluded[identity] = row
    allowed = set(IDENTITY + HASHES) | {'ja', 'status', 'review_note', 'retained_reason', 'display_checked', 'placeholders', 'tags'}
    counts = Counter()
    for identity, row in translated.items():
        if set(row) - allowed:
            raise ValueError('翻訳データに未定義のフィールドがあります')
        original = source[identity]
        if 'display_checked' in row and type(row['display_checked']) is not bool:
            raise ValueError('表示確認状態は真偽値で指定してください')
        if any(row[k] != original[k] for k in HASHES):
            raise ValueError('翻訳データの識別ハッシュが原本メタデータと一致しません')
        status = row['status']
        if status not in {'untranslated', 'needs_review', 'reviewed'}:
            raise ValueError('翻訳のレビュー状態が不正です')
        text = row['ja']
        if not isinstance(text, str) or '\0' in text or '\r' in text:
            raise ValueError('訳文に不正な文字が含まれています')
        counts[status] += 1
        if not text.strip():
            if status != 'untranslated':
                raise ValueError('空の訳文は未訳として記録してください')
        else:
            if status == 'untranslated':
                raise ValueError('訳文のある項目を未訳にできません')
            current = signature(text)
            if any(current[k] != original[k] for k in current):
                raise ValueError('変数、タグ、改行が原文の制約と一致しません')
            if source_digest(text) == original['source_text_sha256'] or not re.search(r'[ぁ-んァ-ヶ一-龯]', TAGS.sub('', PLACEHOLDERS.sub('', text))):
                if not row.get('retained_reason', '').strip():
                    raise ValueError('原語・記号だけを残す項目には理由が必要です')
            if status == 'reviewed' and row.get('review_note', '').strip():
                raise ValueError('未解決の確認事項がある項目を確認済みにできません')
        if release and status != 'reviewed':
            raise ValueError('正式ビルドには未訳・要確認の項目を含められません')
    missing = set(source) - set(translated) - set(excluded)
    if release and missing:
        raise ValueError(f'翻訳対象または対象外の判定が未完了です: {len(missing)}件')
    return dict(total=len(source), translated=len(translated), excluded=len(excluded), missing=len(missing), reviewed=counts['reviewed'], needs_review=counts['needs_review'], untranslated=counts['untranslated'])


def compare(old, new):
    before, after = index(old['entries']), index(new['entries'])
    encode = lambda keys: [dict(namespace=a, key=b) for a, b in sorted(keys)]
    changed = {key for key in before.keys() & after.keys() if before[key] != after[key]}
    return dict(added=encode(after.keys()-before.keys()), removed=encode(before.keys()-after.keys()), changed=encode(changed))
