# apex-legends-cfg — Apex Legends 実測ベース設定ファイル

Apex Legends の実行ファイル（`r5apex_dx12.exe`）を静的解析して作った設定集です。
「このビルドの機械語が実際に値を読む」ことを確認できた項目だけを使い、全行に **既定値 / 意味 / 副作用** のコメントを付けています。

- 対象: `v3.0.1.28` / build `R5pc_r5-301_J28_CL11570498`
- EXE: `r5apex_dx12.exe` sha256 `8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825`

## ファイルの役割（何を使うか）

| ファイル | 役割 |
|---|---|
| `configs/full/autoexec.cfg` | cvar 全般（演出カット・性能・fps上限）。ゲームフォルダに置き、起動オプションで読ませる |
| `configs/ranked/autoexec.cfg` | 上から「情報・挙動に触る6行」だけ外した版（足音/ジップ音距離・フォグ・パーティクル倍速・切替クールダウン） |
| `configs/low-risk/autoexec.cfg` | ゲーム内メニューで同じ結果にできる値だけ（＋`fps_max`） |
| `configs/videoconfig.txt` | **映像の個別値**（テクスチャ/異方性/LOD/デカール/影/ラグドール/SSAO）。Saved Games 側に置き読み取り専用で使う |
| `pad-fix/` | パッド設定がマウス感度に混入する問題の対策（手順書＋`pad_fix.py`） |

映像の個別値は **videoconfig.txt が管理元**（autoexec には重複させていない＝優先関係が不明になるため）。

## 使い方

### autoexec.cfg
1. 3つから選ぶ（判断に迷ったら `ranked`）
2. 既存の `autoexec.cfg` があれば退避（リネーム）
3. `C:\Program Files\EA Games\Apex\autoexec.cfg` としてコピー（**管理者権限**）
4. EAアプリの起動オプションに **`+exec autoexec.cfg -novid`** を追加
   - 必須（EXE内に `autoexec` の文字列が無く、自動では読まれない）
   - `+fps_max` は書かない（cfg 側の値が負ける）

### videoconfig.txt
1. ゲーム終了 → `%USERPROFILE%\Saved Games\Respawn\Apex\local\videoconfig.txt` を退避
2. コピーして **読み取り専用**にする（`attrib +R videoconfig.txt`）
3. 編集は `attrib -R` → 編集 → `attrib +R`（ファイル内の「いじり方」参照）

### pad-fix
ゲーム終了中に `python pad_fix.py --apply`（詳細は `pad-fix/README.md`）

## 戻し方

| 対象 | 戻し方 |
|---|---|
| autoexec | ファイルを消す（または起動オプションから `+exec autoexec.cfg` を外す）。値はゲーム側に保存されないので、次回起動から元に戻る |
| autoexec（旧ファイルに戻す） | 退避した `autoexec.cfg.bak-*` を `autoexec.cfg` にリネームして戻す（読み取り専用属性は `attrib -R` で外す） |
| videoconfig | `attrib -R videoconfig.txt` → 退避したファイルを上書きコピーする。または消して起動（ゲームが既定値で作り直す） |
| pad-fix | `python pad_fix.py --restore`（初回 `--apply` 前の状態に戻る。ロックも外れる） |

## 何を根拠にしているか

- cvar 台帳 **3,772件**（うち native readers 2,814 = コードが値を読むと実測確認）
- videoconfig の正規キー **46本**（exe 内の `setting.*` 文字列）
- 「効く」= このビルドの機械語に読み出し箇所があること（`[E]`。推測・他ゲームからのコピペは採用しない）
- UIスクリプト側が読む値（`[S]`）も少数含む（HUD系など。件数は各ファイルのヘッダ参照）
- 読み手が確認できていない値は**使わない**（autoexec 内ではコメントアウトして `[読み手未確認のため無効]` と明記）

## 規約面（重要）

- **大会（ALGS）**: Year 2 のルールブックでは autoexec に書ける内容が5項目に限定されていた
  （`fps_max` / `mat_letterbox_*` / `setting.csm_enabled "0"` / カスタムレティクル）。現行（Year 5 / 6）の
  ルールブックには config ファイルの節自体が無く、包括条項のみ（同梱 `evidence/rules/`）。
- **一般プレイ**: EA規約に「EAが明示的に認めていないファイル変更」を禁止する文言がある。
  演出カットでのBAN確例は確認できていないが、規約文言上は**グレー**。
- **自動化（マクロ・外部ツール・cfgチェーン）は不可**。本書の cfg には含まれない。
- **pad-fix** は自分の入力設定を変えるだけで、他プレイヤーに対する優位は生まれない。

## 限界

- **FPS等の効果数値は未計測**（このリポジトリは静的解析。効果はハード/ドライバ/解像度依存）
- 視覚的なビフォーアフター検証は含まない（1項目ずつ試す前提）
- 将来のアップデートで無効化されうる

## 収録物

| パス | 内容 |
|---|---|
| `configs/{full,ranked,low-risk}/autoexec.cfg` | 3バリアント（98 / 92 / 24 有効行） |
| `configs/videoconfig.txt` | 43キー・コメント付き |
| `configs/cvar-ledger.tsv` | cvar 台帳 3,772件（テキスト） |
| `pad-fix/` | パッド混入対策（手順書＋`pad_fix.py`） |
| `tools/` | データ再生成用スクリプト（※注入・アタッチ・計測ツールは含まない） |
| `evidence/rules/` | ALGS ルールブック（Year 2 / 5 / 6）と config 記述スキャン |

## English summary

Static-analysis-derived Apex Legends configs. Every line is grounded in the actual
`r5apex_dx12.exe` binary (v3.0.1.28): only cvars read by native code are used. Video values live in
`configs/videoconfig.txt`; general cvars in the three autoexec variants; `pad-fix/` stops gamepad
settings from leaking into mouse aim. Tournament (ALGS) use is restricted — see the rules section.

## 免責

自己責任で使用してください。ゲームファイルの改変・DLL配置・メモリ書き込み・外部ツールは一切行いません
（エンジン公式の `+exec` 経路と、公式の設定ファイルのみ）。
