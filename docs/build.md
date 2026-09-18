# 抽出とビルド

開発にはPython 3.12を使用します。ゲーム原本の参照は抽出工程だけで行い、翻訳データの検査・配布ビルド・CIは原本不要です。依存ツールは `tools.lock.json` のバージョンとSHA-256で固定しています。

```powershell
py -3.12 scripts/extract.py --game-dir '<ゲームのインストール先>'
py -3.12 scripts/catalog.py
py -3.12 scripts/validate_translations.py
py -3.12 -m unittest discover -s tests -v
py -3.12 scripts/build.py --preview
```

抽出物は `.local/` のみへ保存します。`catalog/game.json` は識別情報、原文ハッシュ、原文のSHA-256、変数・タグ・改行の制約だけを含みます。原文は収録しません。`catalog/supported-builds.json` は対応を確認するためのゲームコンテナの名前・サイズ・SHA-256です。

正式訳は `translations/release/*.json` の `entries` 配列に記録します。各項目は `namespace`、`namespace_hash`、`key`、`key_hash`、`source_hash`、`ja`、`status` を持ちます。要確認事項は `review_note`、意図的な原語維持は `retained_reason`、実機表示確認は `display_checked` に記録します。レビュー方針は[翻訳方針](translation-guide.md)を参照してください。

正式ビルドは `py -3.12 scripts/build.py` です。未訳・要確認・キー欠落があると停止します。デモ範囲外と確認したキーのみ `translations/exclusions.json` に名前空間・キー・理由・確認根拠を記録できます。判断できないキーを件数合わせのために除外してはいけません。

ビルドはLocResの読取・書込の一致、Pakの収録パスと再展開したLocResの一致を検査します。Pakには訳文のLocResだけを収録し、同名の空IoStoreコンテナを組み合わせます。ZIPにはツール本体、元ゲーム資産、ログを含めません。

ZIPのファイル順序、時刻、改行、文字コードを固定します。配布ファイルのSHA-256一覧とZIP自体のSHA-256を `dist/` に出力します。試作ZIPは `-preview` を付け、正式訳と分離します。

ゲーム更新時は旧カタログをローカルへ保存してから抽出し、`scripts/catalog.py --compare <旧カタログ>` を実行します。追加・削除・変更の識別情報だけを `.local/catalog-diff.json` に出力します。変更項目の訳文と原文ハッシュを照合し、要確認へ戻して再レビューしてください。対応版の追加には実機確認が必要です。

導入テストはゲームと無関係な自作の小さなコンテナを使います。WindowsではPowerShell 5.1の実処理を起動し、正常導入、再導入、更新、削除、未知・改変・欠落ファイル、未対応版、書き込み失敗などを確認します。実機の通しプレイは別途必要です。
