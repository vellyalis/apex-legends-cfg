# パッド設定がマウスのエイムに混入する問題 — 対処

## TL;DR

パッドを**挿していなくても**、パッド側の設定値が**マウス感度の計算に混入します**。
下の設定を適用すると混入項を最小化できます（ゲーム改造なし・注入なし）。

```
%USERPROFILE%\Saved Games\Respawn\Apex\local\settings.cfg
%USERPROFILE%\Saved Games\Respawn\Apex\profile\profile.cfg
```

適用は手動でも、同梱の `pad_fix.py` でも可:

```
python pad_fix.py --dry      # 変更内容の表示だけ
python pad_fix.py --apply    # バックアップして適用（読み取り専用ロックまで）
python pad_fix.py --restore  # 初回適用前の状態に戻す
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

**重要1 — `gamepad_use_per_scope_sensitivity_scalars` は `"1"`（ON）にする**
OFF（0）だとズーム段ごとのスカラーが使われず、下の 0.2 が効きません（＝混入が残る）。

**重要2 — スカラーの下限は 0.2（実測）**: `gamepad_ads_advanced_sensitivity_scalar_*` に `0.0` を書いても
**ゲームが 0.2 にクランプして書き戻します**（実測: 全8段が 0.2 になった）。正しくは `"0.2"`
（＝ゲーム内スライダーを全部左端にしたのと同じ値）。つまり**ゲーム内でスライダーを左端に揃えるだけ**でも最小化できます。

**触ってはいけない行**:
```
gamepad_custom_*          # カーブ/デッドゾーン/旋回系（マウス計算に非関与）
gamepad_aim_speed_ads_*   # -1 がセンチネル値。0 にすると別方向に挙動が変わる
```

## 反映後にやること

1. ゲームを起動 → 終了（＝設定が読み込まれる）
2. 2つのファイルを開いて**値が 0.2 / 0 のままか確認**
   - 書き戻されていたら再度適用（同梱スクリプトは適用時に**読み取り専用**にロックする。実測ではロックで書き戻しを止められている。ロック中はゲーム内メニューからのパッド設定変更も保存されない）
   - 解除したい時: `attrib -R "…\profile.cfg"` / `pad_fix.py --restore`

## 知っておくべきこと

- パッド処理は**毎フレーム無条件**に共有入力状態を書く（接続チェックがない）
- 起動オプション `-nojoy` では防げない（`joystick` はパッド有効化ロジックでしか読まれない）
- 効果の実感には個人差がある（混入量はズーム段・武器・設定で変わる）。**差を感じなければ戻してよい**
- ゲームを改変しない・アンチチートに触れる操作は含まない（設定ファイル＝データのみ）

## なぜこれで止まるのか（要点）

- マウスとパッドの入力は**エンジン内部で分離されていない**（同じ入力オブジェクトに載っている）
- パッド側の処理は**接続チェックなしで毎フレーム**走り、共有の状態を書き換える
- マウスの実効感度は**その共有状態から選ばれるテーブル**で決まる → パッド側スカラーが混入する
- だから「パッド側スカラーを下限に固定」＋「`joystick 0` / `disable_mouselook 0` を明示」が最小化になる
- 起動オプション `-nojoy` では防げない（`joystick` はパッド有効化ロジックでしか読まれない）

## 触らないもの（わざと）

```
gamepad_custom_enabled            # 0のまま（ALC本体。ONにするとカーブ/デッドゾーンが有効化され悪化）
gamepad_use_per_scope_ads_settings    # 0のまま
gamepad_aim_speed_ads_0..7        # -1 がセンチネル値（触ると別方向に変わる）
mouse_sensitivity / mouse_zoomed_sensitivity_scalar_*  # 各自のエイム設定。無傷で維持
```

## English summary

Even with **no controller connected**, gamepad-side values leak into the mouse sensitivity
computation (shared input object, gate-free pad stage running every frame, shared scalar table).
Set the 18 values above (note: `gamepad_ads_advanced_sensitivity_scalar_*` clamps to **0.2**, not 0.0),
apply read-only locks, and re-check the two files after the next launch. `-nojoy` does not help.
No game modification, no injection.
