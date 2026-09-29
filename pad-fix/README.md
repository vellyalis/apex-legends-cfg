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
gamepad_use_per_scope_sensitivity_scalars "0"
```

**重要 — スカラーの下限は 0.2（実測）**: `gamepad_ads_advanced_sensitivity_scalar_*` に `0.0` を書いても
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

## 根拠（このビルドの静的解析）

| 事実 | 出典 |
|---|---|
| マウス感度の最終計算は `mouse_sensitivity × 共有定数 × テーブルから選ばれるスカラー`。その**スカラー源は共有ゲート状態で切り替わり**、パッド側スカラー（8要素）と**同型の構造を共有** | 逆アセンブル |
| パッド側 look 処理（`0x1408A5350`、呼び出し元は唯一 `0x1409ABC97`）は**接続チェックなしで毎フレーム**共有状態を書く | 逆アセンブル |
| 入力初期化 `0x1404BCA80` が raw mouse と XInput を**同一オブジェクト**に保持（+0x21C0 / +0x21B8） | 逆アセンブル |
| `disable_mouselook` はマウス段のゲート条件 → 明示的に `0` で固定する | 同上 |
| `joystick` の文字列は exe/同梱DLLに**存在しない**（静的に登録されたcvarではない）→ ゲーム自身が書くキーとしてのみ意味がある | 全文走査 |

## English summary

Even with **no controller connected**, gamepad-side values leak into the mouse sensitivity
computation (shared input object, gate-free pad stage running every frame, shared scalar table).
Set the 18 values above (note: `gamepad_ads_advanced_sensitivity_scalar_*` clamps to **0.2**, not 0.0),
apply read-only locks, and re-check the two files after the next launch. `-nojoy` does not help.
No game modification, no injection.
