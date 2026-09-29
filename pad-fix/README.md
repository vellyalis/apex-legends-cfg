# パッド側の値がマウスのエイムに関与する余地を最小化する（静的解析ベース）— 対処

## TL;DR

（静的解析の結論）パッドを**挿していなくても**、パッド側の処理は毎フレーム走り、**マウス感度の計算が参照する共有状態**を書き換えます。
下の**36項目**（profile 34＋settings 2）でパッド側の値を最小化しておくのが安全側の対処です（ゲーム改造なし・注入なし）。

**根拠（すべて静的解析）**: ①入力初期化が raw mouse と XInput を**同一オブジェクト**に保持している
②パッド段は**接続チェックなしで毎フレーム**共有状態を書く ③マウスの実効感度は**その共有状態のゲートから選ばれる
テーブル**で決まり、パッド側スカラーと同型の構造を共有している。
※ 統計的な体感差の検証は交絡により保留（断定はせず、構造解析を根拠にした安全側の対処）。

**要点**: パッド側の数値を最小にするには「**倍率ごとのスカラーを使うトグル=1**」＋「**詳細感度(ALC)本体=1**」の両方が必要です
（どちらかが OFF だと、せっかく最小化した値が使われません）。

## 前提（先に読む）

- **ゲームを終了してから**作業する（起動中は上書きされる）
- バックアップは `--apply` が自動で取る（`pad-fix/backup/`）。手動でやる場合は2ファイルを自分でコピーしておく
- 適用は「**既存行は値を書き換え／無い行は末尾に追記**」で行う（＝36項目を必ず揃える）
- 実行には **Python** が必要（Windows なら python.org 版など）。コマンドは `pad-fix` フォルダの中で実行する

```
python pad_fix.py --dry       変更内容の表示だけ（書き込まない）
python pad_fix.py --apply     バックアップ → 適用 → 読み取り専用ロック
python pad_fix.py --unlock    ロックだけ外す（手で編集したい時）
python pad_fix.py --restore   初回適用前の状態に戻す
```

対象ファイル:

```
%USERPROFILE%\Saved Games\Respawn\Apex\local\settings.cfg      (2項目)
%USERPROFILE%\Saved Games\Respawn\Apex\profile\profile.cfg    (34項目)
```

## 書き込む値

### `local\settings.cfg`（2項目）
```
joystick "0"
disable_mouselook "0"
```

### `profile\profile.cfg`（34項目）

**A. 倍率ごとのADS感度スカラー（8項目）— 中立値(1.0)へ**
```
gamepad_ads_advanced_sensitivity_scalar_0 "1.0"
gamepad_ads_advanced_sensitivity_scalar_1 "1.0"
gamepad_ads_advanced_sensitivity_scalar_2 "1.0"
gamepad_ads_advanced_sensitivity_scalar_3 "1.0"
gamepad_ads_advanced_sensitivity_scalar_4 "1.0"
gamepad_ads_advanced_sensitivity_scalar_5 "1.0"
gamepad_ads_advanced_sensitivity_scalar_6 "1.0"
gamepad_ads_advanced_sensitivity_scalar_7 "1.0"
```

**B. アシスト（5項目）— 切る**
```
gamepad_aim_assist_ads_high_power_scopes "0.0"
gamepad_aim_assist_ads_low_power_scopes "0.0"
gamepad_aim_assist_hip_high_power_scopes "0.0"
gamepad_aim_assist_hip_low_power_scopes "0.0"
gamepad_aim_assist_melee "0.0"
```

**C. トグル（4項目）**
```
gamepad_use_per_scope_sensitivity_scalars "1"   # これが1でないと A の 0.2 が効かない
gamepad_custom_enabled "1"                      # 詳細感度(ALC)本体。これが1でないと A が使われない
joystick "0"
disable_mouselook "0"
```

**D. 詳細感度(ALC)の中身を最小化（17項目）**
```
gamepad_custom_curve "0.0"                      # 記述子の min=0（曲線なし側）
gamepad_custom_assist_on "0"                    # ALC側のアシストも切る
gamepad_custom_assist_style "0"
gamepad_custom_ads_pitch "0.0"                  # ADS 旋回上限を最小へ
gamepad_custom_ads_yaw "0.0"
gamepad_custom_ads_turn_delay "0.0"
gamepad_custom_ads_turn_pitch "0.0"
gamepad_custom_ads_turn_time "0.0"
gamepad_custom_ads_turn_yaw "0.0"
gamepad_custom_hip_pitch "0.0"                  # ヒップ 旋回上限を最小へ
gamepad_custom_hip_yaw "0.0"
gamepad_custom_hip_turn_delay "0.0"
gamepad_custom_hip_turn_pitch "0.0"
gamepad_custom_hip_turn_time "0.0"
gamepad_custom_hip_turn_yaw "0.0"
gamepad_custom_deadzone_in "0.15"               # 既定値のまま（意図: 遊びを残す。効果は未検証）
gamepad_custom_deadzone_out "0.02"
```

値の根拠: cvar 記述子の min が 0 であること（実測）。上限は未記載の項目があるため、**0 かゲーム既定値のみ**を採用している（範囲外を書かない）。
**パッドを使わない人向けの設定**です（パッドを使う人は D が効きすぎるので調整してください）。

## 倍率スカラーの値について

- 採用値は **`"1.0"`（中立＝ゲーム既定。追加の倍率をかけない）**。ユーザー指示（2026-09-29）による
- 参考（実測）: `0.0`〜`0.1`台を書いても**ゲームが 0.2 にクランプして戻す**。この下限帯は使わない
  （ゲーム内スライダーを左端にした状態と同じ値）

## 反映の確認（起動→終了後に）

- `profile.cfg`: スカラー8個 `1.0`（中立） / アシスト5個 `0.0` / **トグル2つが `1`** / ALCの`custom_*`が上記の値 / `joystick 0`・`disable_mouselook 0`
- `settings.cfg`: `joystick 0` / `disable_mouselook 0`
- 戻っていたら再適用（`--apply` は読み取り専用ロックも付ける）

## 触らないもの（わざと）

```
gamepad_use_per_scope_ads_settings     触らない（実装は未操作＝既存値を維持。配布元の環境では0）
gamepad_aim_speed_ads_0..7             -1 がセンチネル値（触ると別方向に変わる）
gamepad_custom_pilot / _titan          内部の割り当てリスト
mouse_sensitivity / mouse_zoomed_sensitivity_scalar_*   各自のエイム設定。無傷で維持
```

## ロックの副作用と解除

読み取り専用ロック中は **その2ファイル全体の保存が止まります**（パッド設定だけでなく、解像度・バインド等の
変更も保存されない）。編集したい時はロックを外す:

```
python pad_fix.py --unlock
（手動なら: attrib -R "…\local\settings.cfg" と attrib -R "…\profile\profile.cfg" の両方）
```

## 検証状況（正直に）

| 項目 | 状態 |
|---|---|
| 入力がマウス/パッドで分離されていない・パッド段がゲートなしで毎フレーム走る | **静的解析で確認**（リバースエンジニアリング） |
| マウス実効感度が共有状態のゲートから選ばれるテーブルで決まる | **静的解析で確認** |
| パッド側の値が実際にその計算へ流れ込むこと（実行時の値の流れ） | **未検証**（デバッガ/ダンプでの実行時計測が未実施） |
| 体感差の統計的検証 | **保留**（条件が違う遊び方で交絡） |

→ したがって本手順は「**安全側の対処**」です（効果の保証ではありません）。実行時検証まで済ませたい場合は、
デバッガ/クラッシュダンプでの実測が必要です（本リポジトリの対象外）。

## 知っておくべきこと

- パッド処理は**毎フレーム無条件**に走り、共有状態を書き換える（接続チェックがない）
- 起動オプション `-nojoy` では防げない
- 効果の実感には個人差がある（関与の度合いはズーム段・武器・設定で変わると**考えられる**＝未検証）。**差を感じなければ戻してよい**
- ゲームを改変しない・アンチチートに触れる操作は含まない（設定ファイルの数値のみ）

## なぜこれが安全側なのか（要点）

- マウスとパッドの入力は**エンジン内部で分離されていない**（同じ入力オブジェクトに載っている）
- パッド側の処理は**接続チェックなしで毎フレーム**走り、共有の状態を書き換える
- マウスの実効感度は**その共有状態から選ばれるテーブル**で決まる（パッド側スカラーと同型の構造）
  → パッド側の値が小さいほど、共有状態に載る量も小さくなる（安全側）
- 関与するスカラーは「倍率ごとのスカラー」で、**per-scope トグルと ALC 本体の両方が ON のときだけ適用される**
  → だから「両トグル ON ＋ 倍率スカラーは中立、ALC の旋回系は下限」が安全側になる

## English summary

Even with **no controller connected**, the gamepad path runs every frame and writes the same shared
state the mouse sensitivity computation reads (same input object, gate-free pad loop, shared scalar table).
The fix below minimizes the gamepad-side values as a safety measure (structural evidence; statistical
feel-testing is inconclusive).
Apply the 36 values above — both the per-scope toggle **and** Advanced Look Controls must be ON
(`gamepad_use_per_scope_sensitivity_scalars "1"`, `gamepad_custom_enabled "1"`), the per-zoom scalars are set to the neutral **1.0**
(values below 0.2 are clamped to 0.2 by the engine) — then lock both files read-only and re-check after the next launch.
`-nojoy` does not help. No game modification, no injection.
