# apex-legends-cfg — Apex Legends 実測ベース設定ファイル

Apex Legends（EA app版）の実行ファイル `r5apex_dx12.exe` を**静的解析**して、
「このビルドの機械語が実際に値を読む設定」だけを集めた **autoexec.cfg** と **videoconfig.txt** です。
全行・全キーに **既定値 / 意味 / 副作用** のコメント付き、**1行消せばそのまま無効**になります。

- 対象: `v3.0.1.28` / build `R5pc_r5-301_J28_CL11570498`
- EXE: `r5apex_dx12.exe` sha256 `8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825`
- 作り方の証拠は `tools/` に同梱（RVAs/ハッシュ/抽出結果）

## 収録物

| パス | 内容 |
|---|---|
| `configs/full/autoexec.cfg` | **111行** — 視覚カット全部入り（ブルーム/グレア/ブラー/露出/フォグ/マズルフラッシュ/揺れ）＋性能＋情報系 |
| `configs/ranked/autoexec.cfg` | **105行** — full から「情報・挙動に触る6行」だけ除外（足音/ジップ音距離・フォグ・パーティクル倍速・切替クールダウン） |
| `configs/low-risk/autoexec.cfg` | **35行** — ゲーム自身がメニューから書く値のみ（＋`fps_max`） |
| `configs/videoconfig.txt` | **43キー** — コメント付き（読み取り専用で使う前提） |
| `pad-fix/` | **パッド設定がマウス感度に混入する問題の対処**（手順書＋自動適用 `pad_fix.py`。混入機構は逆アセンブルで確認済み） |
| `configs/CVAR-GUIDE.md` / `configs/cvar-ledger.tsv` | cvar 台帳 **3,772件**（機械可読＋日本語ガイド） |
| `tools/` | 解析スクリプト（PE走査・キー抽出・cfg生成。再現用。※ゲームへの注入・アタッチ・計測ツールは含まない） |
| `evidence/rules/` | ALGS ルールブックの config 記述スキャン（Year 2 / 5 / 6） |

## 設置

### autoexec.cfg
1. 使いたいフォルダの `autoexec.cfg` を `C:\Program Files\EA Games\Apex\` にコピー（管理者権限）
2. EAアプリの起動オプションに `+exec autoexec.cfg -novid` を追加（**必須**。EXE内に `autoexec` の文字列が無い＝自動実行されない）
3. `+fps_max` は書かない（cfg の値が負ける）

### videoconfig.txt
1. `configs/videoconfig.txt` を `%USERPROFILE%\Saved Games\Respawn\Apex\local\` にコピー（ゲーム終了中に）
2. **読み取り専用**にする（`attrib +R videoconfig.txt`）— でないとゲームがメニュー値で書き戻してコメントも消える
3. メニューからの解像度等の変更が保存されなくなる点に注意（変えるときは属性を外す）

## 何を根拠にしているか

- cvar 台帳 **3,772件**: native readers 2,814（コードが値を読むと実測確認）/ 読み手なし 929 / 動的登録 29 / `FCVAR_CHEAT` 288
- videoconfig 正規キー **46本**: exe 内の `setting.*` 文字列を機械抽出
- 「効く」= このビルドの機械語に読み出し箇所があること（推測・他ゲームからのコピペは不採用）

## ルール面（重要）

- **大会（ALGS）**: Year 2 のルールブックは `autoexec.cfg` をファイルとしては許可しつつ、**中身を5項目に限定**（`fps_max` / `mat_letterbox_aspect_goal` / `mat_letterbox_aspect_threshold` / `setting.csm_enabled 0` / カスタムレティクル）。現行の Year 5 / Year 6 には **config ファイルの節が無く**、包括条項（unfair advantage / exploits）のみ。→ 大会利用は自己判断で。
- **一般プレイ**: EA利用規約に「EAが明示的に認めていないファイル変更」を禁止する文言がある。演出カット系でのBAN確例は確認できていないが、**グレー**であることは明示しておく。厳密に行きたい人向けに `low-risk` 版を用意している。
- **自動化（マクロ・外部ツール・cfgチェーン）は不可**。本リポジトリの cfg には含まれない（Respawn は 2024/2 に `+exec` チェーンを無効化し自動化を不正と明言）。

## 限界（正直に）

- **FPS等の効果数値は未計測**（このリポジトリは静的解析。効果はハード/ドライバ/解像度依存）
- 読み手未確認の 929件・動的登録 29件は**採用していない**
- 視覚的なビフォーアフター検証は含まない（各自1行ずつ試す前提）
- 将来のアップデートで無効化されうる（その場合は各自の環境で無効行を判別できるよう [E]/[S]/[未] の印がある）

## English summary

Static-analysis-derived Apex Legends configs. Every line is grounded in the actual
`r5apex_dx12.exe` binary (v3.0.1.28): only cvars whose values are read by native code
were kept. Three autoexec variants (full / ranked / low-risk) plus a commented
`videoconfig.txt`. All defaults, meanings and side effects are documented inline
in Japanese. Tournament (ALGS) use is restricted — see the rules section above.

## 免責

自己責任で使用してください。ゲームファイルの改変・DLL配置・メモリ書き込み・外部ツールは一切行いません
（エンジン公式の `+exec` 経路のみ）。
