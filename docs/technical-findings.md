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

### 追加のローカライズ領域

`Engine/Content/Localization/Engine` にもLocResがあり、英語・簡体字中国語とも54,314件を収録しています。6,221名前空間を含み、エディター用の文字列が多くあります。`InputKeys` の350件など、プレイヤーが目にする可能性のある表示を実機で確認し、必要なキーを追加対象にします。この切り分けは追加Issueで追跡します。

現時点のビルドが扱うのはGame領域です。Gameの翻訳率だけをデモ全体の完了率として報告してはいけません。

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

メニューと設定の日本語表示、追加Pakの優先読み込みを実機で確認しました。ユーザーにより冒頭ムービーとゲームプレイ開始直後の字幕の日本語表示も確認済みです。試作で訳していない項目は英語へフォールバックします。

### NotoSansJPへの切り替え

中国語設定の元の複合フォントは、漢字にNotoSansSCを使い、かなが別の代替フォントへ回るため、日本語の書体が混在していました。同梱NotoSansJPは `ja` 用の設定にしか登録されていません。

`EBGaramond_Font` と `FiraSansCondensed_Font` の参照設定を自作し、`zh-Hans` では全Unicode範囲にNotoSansJPを指定します。通常・MediumはRegular、Bold・SemiBoldはBoldを使用します。英語設定の既定書体と、ロシア語・韓国語・日本語用の参照は維持します。フォント本体と抽出資産は収録しません。

会話表示の `W_DialogueBox` は `DT_SubtitleRichText` を参照し、このスタイル表は `FiraSansCondensed_Font` を参照しています。字幕にも今回の設定が適用される構成です。

`scripts/build.py --preview` で生成する配布試作ZIPには、この参照設定を含みます。上記の旧 `build_probe.py` は文字列の読み込み確認用で、フォント設定を含みません。初期の手動試作 `Hellraiser_Japanese_Probe_P.*` とフォント単独試作 `Hellraiser_Japanese_Font_P.*` が残る環境では、導入スクリプトは競合を避けるため停止します。

自作した設定の実機読み込みとメニュー・設定画面の表示を確認しました。ローカルでIoStoreから読み戻したプロパティも生成時と一致しています。字幕の読みやすさと全画面でのはみ出しは、フォント変更後の追加確認が必要です。

### 検証状態

- 自作データのUnicode、重複キー、壊れた入力、再現性テスト: 成功
- 英語・中国語の原本全エントリを読取→書込→再読取して意味が保持されること: 成功
- Pakと空IoStoreコンテナの再ビルド時のバイト一致: 成功
- メニュー・設定の日本語表示とセーブの読み込み: 成功
- 会話字幕の日本語表示: 冒頭ムービーとゲームプレイ開始直後をユーザー確認済み
- NotoSansJPへの切り替え: 自作参照設定の読み込みとメニュー・設定画面を確認済み。字幕での読みやすさは確認待ち
- ユーザーによる通しプレイ: 未実施
