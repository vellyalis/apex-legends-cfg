# パッド設定がマウスのエイムに混入する問題 — 対処

## TL;DR

パッドを**挿していなくても**、パッド側の設定値が**マウス感度の計算に混入します**。
下の18項目を適用すると混入項を最小化できます（ゲーム改造なし・注入なし）。

## 前提（先に読む）

- **ゲームを終了してから**作業する（起動中は上書きされる）
- バックアップは `--apply` が自動で取る（`pad-fix/backup/`）。手動でやる場合は2ファイルを自分でコピーしておく
- 適用は「**既存行は値を書き換え／無い行は末尾に追記**」で行う（＝18項目を必ず揃える）
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
%USERPROFILE%\Saved Games\Respawn\Apex\profile\profile.cfg    (16項目)
```

## 書き込む値（計18項目）

### `local\settings.cfg`（2項目）
```
joystick "0"
disable_mouselook "0"
```

### `profile\profile.cfg`（16項目）
```
gamepad_ads_advanced_sensitivity_scalar_0 "0.2"
gamepad_ads_advanced_sensitivity_scalar_1 "0.2"
gamepad_ads_advanced_sensitivity_scalar_2 "0.2"
gamepad_ads_advanced_sensitivity_scalar_3 "0.2"
gamepad_ads_advanced_sensitivity_scalar_4 "0.2"
gamepad_ads_advanced_sensitivity_scalar_5 "0.2"
gamepad_ads_advanced_sensitivity_scalar_6 "0.2"
gamepad_ads_advanced_sensitivity_scalar_7 "0.2"
gamepad_aim_assist_ads_high_power_scopes "0.0"
gamepad_aim_assist_ads_low_power_scopes "0.0"
gamepad_aim_assist_hip_high_power_scopes "0.0"
gamepad_aim_assist_hip_low_power_scopes "0.0"
gamepad_aim_assist_melee "0.0"
joystick "0"
disable_mouselook "0"
gamepad_use_per_scope_sensitivity_scalars "1"
```

## 重要1: `gamepad_use_per_scope_sensitivity_scalars` は `"1"`（ON）

OFF（0）にすると**ズーム段ごとのスカラーが使われなくなり、上の 0.2 が効きません**（混入が残る）。
「1 + 8段すべて 0.2」がセットで意味を持ちます。

## 重要2: スカラーの下限は 0.2（実測）

`gamepad_ads_advanced_sensitivity_scalar_*` に `0.0` を書いても、**ゲームが 0.2 にクランプして戻します**
（実測: 全8段が 0.2 になった）。正しくは `"0.2"` ＝ **ゲーム内スライダーを全部左端にしたのと同じ値**。
つまり「ゲーム内でスライダーを左端に揃える」だけでも最小化できますが、その場合も**重要1のトグルが `1` であること**が必要です。

## 反映の確認（起動→終了後に）

- `profile.cfg`: スカラー8個が `0.2` / エイムアシスト5個が `0.0` / **トグルが `1`** / `joystick 0` / `disable_mouselook 0`
- `settings.cfg`: `joystick 0` / `disable_mouselook 0`
- 戻っていたら再適用（`--apply` は読み取り専用ロックも付ける）

## 触らないもの（わざと）

```
gamepad_custom_enabled                0のまま（ALC本体。ONにするとカーブ/デッドゾーンが有効化され悪化）
gamepad_use_per_scope_ads_settings    0のまま
gamepad_aim_speed_ads_0..7            -1 がセンチネル値（触ると別方向に変わる）
mouse_sensitivity / mouse_zoomed_sensitivity_scalar_*   各自のエイム設定。無傷で維持
```

## ロックの副作用と解除

読み取り専用ロック中は **その2ファイル全体の保存が止まります**（パッド設定だけでなく、解像度・バインド等の
変更も保存されない）。編集したい時はロックを外す:

```
python pad_fix.py --unlock
（手動なら: attrib -R "…\local\settings.cfg" と attrib -R "…\profile\profile.cfg" の両方）
```

## 知っておくべきこと

- パッド処理は**毎フレーム無条件**に走り、共有状態を書き換える（接続チェックがない）
- 起動オプション `-nojoy` では防げない
- 効果の実感には個人差がある（混入量はズーム段・武器・設定で変わる）。**差を感じなければ戻してよい**
- ゲームを改変しない・アンチチートに触れる操作は含まない（設定ファイルの数値のみ）

## なぜこれで止まるのか（要点）

- マウスとパッドの入力は**エンジン内部で分離されていない**（同じ入力オブジェクトに載っている）
- パッド側の処理は**接続チェックなしで毎フレーム**走り、共有の状態を書き換える
- マウスの実効感度は**その共有状態から選ばれるテーブル**で決まる → パッド側スカラーが混入する
- だから「パッド側スカラーを下限に固定」＋「`joystick 0` / `disable_mouselook 0` を明示」が最小化になる

## English summary

Even with **no controller connected**, gamepad-side values leak into the mouse sensitivity
computation (shared input object, gate-free pad loop every frame, shared scalar table).
Apply the 18 values above — note the toggle `gamepad_use_per_scope_sensitivity_scalars "1"` and the
engine clamp at **0.2** (not 0.0) — lock both files read-only, and re-check after the next launch.
`-nojoy` does not help. No game modification, no injection.
