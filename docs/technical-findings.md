# 解析と表示試作

## 原本の確認

- 対応デモ: `1.0.0.225957_HellraiserGameDemo_Shipping_26254_Demo_Test`
- Pak形式: v11、索引・対象LocResは暗号化なし、本文はOodle圧縮
- マウントポイント: `../../../`
- 翻訳対象の基本パス: `Hellraiser/Content/Localization/Game/zh-Hans/Game.locres`
- LocRes形式: v3。名前空間・キーのハッシュと原文ハッシュを保持する
- 英語6,840件、中国語6,843件。英語のみ3件、中国語のみ6件。共通キーの原文ハッシュ不一致は0件
- 複数ミッションの文字列が含まれるため、収録件数をデモの表示対象件数と同一視しない
- NotoSansJPのRegular/Boldをゲームが同梱。パッチへのフォント再配布は行わない

## ローカル抽出

```powershell
py -3.12 scripts/extract.py --game-dir '<ゲームのインストール先>'
```

原文と抽出ファイルは `.local/` に保存されます。出力ログには件数と対応版・ハッシュのみを表示します。Windowsでの原本展開には、利用条件を確認して取得した `oo2core_9_win64.dll` をローカルのrepakと同じフォルダに配置します。実行前に `tools.lock.json` のSHA-256と照合します。公開ビルドではこのライブラリを使用しません。

## 表示試作

```powershell
py -3.12 scripts/build_probe.py
```

ゲーム原本を使わず、70件の日本語UI・字幕の試作訳から次の3ファイルを生成します。試作は全翻訳ではありません。正式版へ混入させないでください。

- `.local/Hellraiser_Japanese_Probe_P.pak`
- `.local/probe-iostore/Hellraiser_Japanese_Probe_P.utoc`
- `.local/probe-iostore/Hellraiser_Japanese_Probe_P.ucas`

ゲーム終了中に3ファイルをゲームの `Hellraiser/Content/Paks` へ追加し、簡体字中国語を選択して表示を確認します。確認後はゲームを終了し、この3ファイルだけを削除します。既存のゲームコンテナは上書きしません。

本デモはPak単独では追加ファイルを読み込みません。同名のIoStoreコンテナが必要なため、Retocでゲーム資産を含まない空コンテナを生成します。Retocの出力先にも空Pakが生成されますが、使用するPakはrepakで作成した訳文入りのものです。

メニューと設定の日本語表示、追加Pakの優先読み込みを実機で確認しました。確認したUI文字は既存フォントで表示できています。試作で訳していない項目は英語へフォールバックします。

### 検証状態

- 自作データのUnicode、重複キー、壊れた入力、再現性テスト: 成功
- 英語・中国語の原本全エントリを読取→書込→再読取して意味が保持されること: 成功
- Pakと空IoStoreコンテナの再ビルド時のバイト一致: 成功
- メニュー・設定の日本語表示とセーブの読み込み: 成功
- 会話字幕の日本語表示: 確認中
- ユーザーによる通しプレイ: 未実施

