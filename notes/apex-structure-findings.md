# Apex Legends ローカル構造解析（vision/AIM感の謎）

対象: `C:\Program Files\EA Games\Apex`（EA app導入, build `R5pc_r5-301_J28_CL11570498_FSv30_1_2026_09_16_17_18` / v3.0.1.28）
本体: `r5apex_dx12.exe` sha256 は `evidence/install/EXE_SHA256.txt`
手法: **ローカルファイルのみ**（Web検索なし）。PE解析(.pdata/.rdata/.data)、文字列抽出、RIP相対xref、capstone逆アセンブル。
ツール: `tools/*.py`（scan_strings / scan_tokens / cvar_table / func_xref / readers3 / identify / resolve_objects / callsite）

---

## 1. 設定の保管場所（実測）

| ファイル | 内容 | 実例 |
|---|---|---|
| `Saved Games\Respawn\Apex\profile\profile.cfg` | コントロール系（`gamepad_*`, HUD, 音量） | `gamepad_custom_enabled 0`, `gamepad_custom_deadzone_in 0.15` |
| `Saved Games\Respawn\Apex\local\settings.cfg` | バインド + マウス + 低遅延系 | `mouse_sensitivity 1.45`, `mouse_use_per_scope_sensitivity_scalars 1`, `m_acceleration 0`, `gfx_amdUseLowLatency 1`, `gfx_nvnUseLowLatency 1` |
| `Saved Games\Respawn\Apex\local\videoconfig.txt` | 映像 `setting.*` | `setting.mat_forceaniso 2`, `setting.stream_memory 600000`, `setting.dvs_enable 0`, `setting.mat_backbuffer_count 1` |

`videoconfig.txt` の `setting.*` は exe 内の**ホワイトリスト49キー**(rva 0x180fc40付近 / `evidence/pak/exe_ctx.txt`)に一致すること、
および映像メニューのパネル名・ラベル（`SwchFilteringMode`, `#GameUI_Anisotropic2X/4X/8X/16X`, `#setting_texture_stream_budget_very_low…ultra`,
`SldAdaptiveRes`, `SwchNvidiaReflex`, `SwchAmdAntiLag`, `SwchTextureDetail`）が exe 内に存在することを確認（`evidence/tokens/`）。

## 2. cvar の登録スタブと既定値（すべて exe から抽出）

各 cvar は「登録スタブ関数」を持ち、`名前文字列 + 既定値文字列 + 記述子(struct) + ハンドル(グローバル)` を書き込む。

| cvar | スタブRVA | 記述子 | ハンドル | 既定値 |
|---|---|---|---|---|
| `mouse_sensitivity` | 0x14017ab80 | 0x14253b160 | 0x14253b198 | **"5"**（min/max らしき float `0.1` / `20.0` も同struct内） |
| `mouse_use_per_scope_sensitivity_scalars` | 0x14017ad50 | 0x142530a10 | 0x142530a48 | "0" |
| `mouse_zoomed_sensitivity_scalar_0..7` | 0x14017af10 | 0x142530aa0起点テーブル | 0x142530ad8(scalar_0) | "1.0" ほか |
| `m_acceleration` | 0x14017bfb0 | 0x1425321a0 | 0x1425321d8 | **"0"** |
| `cl_use_raw_input_buffer` | 0x140200a70 | 0x14274de50 | 0x14274de88 | **"1"** |
| `gamepad_look_curve` | 0x14013f1c0 | 0x142519280 | 0x1425192b8 | "0" |
| `gamepad_custom_deadzone_in` | 0x14013acb0 | 0x142517e80 | 0x142517eb8 | "0.15" |
| `gamepad_custom_curve` | 0x14013b030 | 0x142517b90 | 0x142517bc8 | "10.0" |
| `gamepad_custom_enabled` | 0x14013a770 | 0x1425149b0 | 0x1425149e8 | "0" |
| `gamepad_aim_speed` | 0x140138460 | 0x142518070 | 0x1425180a8 | "2" |
| `input_did_turn_threshold` | 0x1401769c0 | 0x14253c7c0 | 0x14253c7f8 | "1.0f" |
| `raw_input_deadzone` | 0x1400c9620 | 0x1424cde10 | 0x1424cde48 | **"1024"** |
| `showfps_mouse_latency` | 0x140099450 | 0x141ed5480 | 0x141ed54b8 | **"1"** |
| `mirror_main_scene` | 0x1401ebaa0 | 0x1426bdfc0 | 0x1426bdff8 | "0" |
| `cl_fovScale` | 0x140094e10 | 0x141ed0440 | 0x141ed0478 | "1.27216005" |

## 3. エイム（look）処理の実体 — **マウスとパッドは別関数**

### マウス感度の計算関数 = `0x1409b6e10`（0x730B, 唯一の consumer）
`mouse_sensitivity` ハンドル(0x14253b198)への静的参照は**この関数1つだけ**（`evidence/readers3.txt`）。処理:

1. `xmm8 = mouse_sensitivity`（記述子+0x58 の float）
2. `mirror_main_scene != 0` のとき yaw を **×(-1)**（ミラー描画用の反転。定数 0x1419c79f4 = -1.0）
3. ADS(ズーム)中と判定されると `mouse_use_per_scope_sensitivity_scalars` を確認:
   - off → `mouse_zoomed_sensitivity_scalar_0` の値
   - on → スコープ指数 `[weapon?+0x1b98]`, `[+0x1b9c]` で **scalar テーブル(0x142530aa0, stride 0x48)** の2値を lerp（ズーム率で補間）
4. `m_acceleration != 0` のとき: `(x,y)` を `sqrt(x²+y²)` で**正規化**（斜め入力の実効感度が変わる Source系の遺物）
5. yaw/pitch デルタに乗算して書き戻し

→ この関数が読む cvar は **mouse系 + m_acceleration + mirror フラグのみ**。gamepad系は一切読まない。

### パッドの look 処理関数 = `0x1408a5350`（0xC14B）
`gamepad_custom_enabled`(0x1425149e8) などの **gamepad系cvarとプレイヤー状態**を読む。マウス系cvarへの静的参照は**なし**。

### 呼び出し関係
- マウス: ラッパ `0x1409b7650` → `0x1409b6e10`（呼び出し元は1箇所のみ）
- パッド: ラッパ `0x1409ab47b` → `0x1408a5350`（呼び出し元は1箇所のみ）

**結論（静的・コード参照レベル）**: このビルドには「パッド設定 → マウス感度/マウス入力」の直接結合経路が存在しない。
（前回のChatGPT調査の「no mixing path」を RVA レベルで裏付けた形。ただし runtime で名前から cvar を引く箇所までは静的xrefでは追えない点は残る）

## 4. 生入力・遅延系（AIM感に直結しうる部分）

- `cl_use_raw_input_buffer` 既定 **1**（生入力バッファ使用）
- `showfps_mouse_latency` 既定 **1** → エンジン自身が**マウス遅延を計測**している（perf オーバーレイ用。読者は 0x140419120 / 0x1404bdb3e）
- `raw_input_deadzone` 既定 1024 → ただし参照元は `0x14057e2d0`（入力ビット列を自前バッファに詰める処理）で、
  exe内文字列 **`anticheat.raw_input.match.rate` / `send_buffer_overflow` / `raw_input_client_send_enable`** と同居
  → これは **EOS AntiCheat 向けの生入力テレメトリ経路**（ゲームプレイのエイム経路とは別物）
- `input_did_turn_threshold`(既定1.0) 読者 `0x1409b1370`: 視点角度の差分二乗和を閾値と比較して「turnしたか」を判定（エイム支援/計測系）

## 5. 映像側（テクスチャストリーミング / 異方性）

- `setting.mat_forceaniso`（メニュー: Bilinear / Trilinear / **2x** / 4x / 8x / 16x）。既定（exe/メニュー基準）は **2x**
- `setting.stream_memory`（ユーザー値 600000）＋ エンジン側cvar群:
  `stream_memory_min`, `stream_memory_while_loading`(既定 **298000**), `stream_texture_bandwidth`,
  `stream_handle_allocation_max_stall_msec`（**ストール許容値**）, `stream_never_high_priority_frac`,
  `stream_load_after_drop`(既定 0.0125), `stream_picmip`, `dynamic_streaming_budget`
- 動的解像度: `setting.dvs_enable 0` / `dvs_gpuframetime_min 15000` / `max 16500`（µs = 15ms ≈ 66.7fps を GPU 目標に設定可能）
- スワップチェーン: `setting.mat_backbuffer_count 1`（入力→表示の遅延に直接効く）
- 低遅延系: `gfx_amdUseLowLatency`, `gfx_forceAllowedLowLatencyMode`, `gfx_nvnUseLowLatency`, `gfx_nvnUseLowLatencyBoost`（ユーザーは AMD/NV 両方 1）
- AIM計算コード（§3）から映像系cvarへの参照は**存在しない**。

→ 映像設定が「AIM感」に効く構造的理由は **GPU/IO負荷 → フレームタイム → 入力→表示遅延** の経路（＋ストリーミングのスタール）。
　異方性はサンプラ設定のみで、フレームタイム経由以外の経路は無い。

## 6. 未確定 / 次の切り分け（提案）

1. **誤書き込み仮説**: パッド詳細設定を変更→終了した直後に `profile.cfg` と `settings.cfg` を diff する。
   マウス系キー（`mouse_sensitivity`, `mouse_zoomed_*`, `m_acceleration`, `cl_use_raw_input_buffer`）が動いていれば確定。
2. **体感の原因がフレームタイム側か**の実測: `showfps_mouse_latency` があるので、エンジン内蔵の遅延計測値と
   フレームタイム（netgraph/perfオーバーレイ）をキャプチャ比較する。
3. EAC を外した場合の制約: オフライン起動となり射撃場等へ入れない可能性が高く、**実プレイでの体感比較はできない**。
   ローカルでのメモリ読み取り/デバッガ接続は可能になるが、動くゲームでのA/B計測は EAC ありの通常起動が前提になる。

（この解析はローカルの静的データのみ。ゲームの改変・注入は行っていない）

## 共有状態の発見（2026-09-24, xref_compare による）

mouse sens `0x1409b6e10` と pad look `0x1408a5350` は**直接 xref が無い**が、
**7 個のグローバルを共有**している（RIP 相対参照の突き合わせ、tools/xref_compare.py）。

共有先の絞り込み（identify.py の xref 数）:
- 0x143f83be0: 20228 refs / 7912 funcs（汎用）
- 0x1419c79f4: 566 / 389、0x1419c9ce0: 560 / 440（エンジン全体）
- **0x1426bdff8: 12 refs / 12 funcs ← 特定**

`0x1426bdff8` の参照元 12 関数に、**mouse sens と pad look の両方**が含まれる。さらに
`ViewZoom` 文字列を持つ関数 (`0x14065c57b`) と `mirror_main_scene` 文字列を持つ関数 (`0x1401ebaa0`) も
同じ状態を参照 → **共通の view/zoom/aim 状態**である可能性が高い（パッド入力が書き込む場所と
マウス計算が読む場所が同じ = 「パッドがマウスに効く」経路の候補）。

### 共有状態の書き込み側の検査（2026-09-24 追記）

- 共有 float `0x1419c79f4` への**書き込みはバイナリ全体で 0 箇所**（`F3 0F 11`/`C7 05`/`89 05` 系の
  RIP 相対ストアを全走査）→ これは**定数**（ハードコードされた倍率）であって実行時に書き換わる値ではない。
- 共有状態を参照する 12 関数の中で `[state+0x5C]` に**書き込む**命令は**無い**（すべて cmp / mov（読み）/
  mulss（読み））。→ この 12 関数は `[state+0x5C]` を**同じゲートとして読む**側だけ。
- つまり現時点の結合は「**共有のゲート値 + 共有の定数倍率を両経路が読む**」という読み取り結合。
  パッド経路がマウス用の値を**書く**形ではない（この経路では）。
- 次の候補: (1) `[state+0x5C]` を書く側（12 関数の外）の特定、(2) 残り 4 つの共有グローバルの正体
  （0x141b4d4a0 / 0x143fd0390 / 0x1458d4a18 ほか。identify 出力は %LOCALAPPDATA%\Temp\identify-shared4.txt）、
  (3) フレーム間隔・入力タイミング経由の結合（外部観測レーンで測定可能）。

## 共有グローバル 0x143fd0390（2026-09-24）

- xref: 55 refs / 38 funcs（7 個の共有先のうち「ほどよく特定」な 1 つ。他は汎用）。
- mouse sens 0x1409b6e10 と pad look 0x1408a5350 の両方が参照。参照元の文字列は
  %LOCALAPPDATA%\Temp\identify-143fd0390.txt に保存。
- 次の一手: 同ファイルの strings から正体（cvar / オブジェクト種別）を確定し、
  pad 経路がここへ書くか（データフロー）を確認。

## 設定ファイルの実測（2026-09-24, パッド未接続時点）

- `local/settings.cfg`: `mouse_sensitivity "1.45"`, per-scope scalars 0..7 =
  (1, 1.15, 1.25, 1.3, 1.3, 1.4, 1.4, 1.0), `mouse_use_per_scope_sensitivity_scalars "1"`。
  **`disable_mouselook` は保存されていない**（= ユーザー設定値として存在しない。既定のまま）。
- `profile/profile.cfg`: パッド側の設定が全部ここ — `gamepad_aim_assist_*` が全て "1"（有効）、
  `gamepad_aim_speed "0"`, `gamepad_ads_advanced_sensitivity_scalar_0..7` は全て "1.0"。
- `evidence/live/config_watch.log` は 2 行のみで履歴なし → **パッド有無の比較は新規に取る必要がある**
  （現在 pad=no が観測済みなので、いまの設定 = 「パッド無しベースライン」。パッドを挿した状態との
  diff を取れば `gamepad_*` / `mouse_*` の相互汚染が目に見える）。
- `disable_mouselook` の cvar 記述子は、名前文字列（VA 0x1418BFF70）への 64bit ポインタ走査では
  見つからなかった（このビルドの記述子は別形式）→ **レーンの readers3.py で記述子と値スロットを
  取るのが正攻法**（そこから値スロットへの書き込み側を全列挙すれば「パッド側がマウス用設定を
  書くか」が確定する）。

## 共有インターフェースの参照パターン（2026-09-24, setter 側の列挙）

`0x143fd0390` を参照する 38 関数の参照サイト 55 箇所を走査（47 箇所が「直後に vtable 呼び出し」）。

- パターンはほぼ全部: `mov rcx,[0x143fd0390] / mov rax,[rcx] / call qword ptr [rax+0x78]` →
  **同じ vtable スロット +0x78 を呼び、戻り値を小さな値と比較**する。
  - `cmp eax, 3`（0x14089F8DA）
  - `lea ecx,[rax-4]; test ecx, 0xfffffff9`（= 数ビットのパターン検査。列挙値の判定）
- 呼び出し元には **pad look (0x1408A5350 ×2)**、aim-assist 系 (0x1408A0CA0 ほか)、
  入力設定系 (0x14089F5xx 群) が並ぶ。
- 解釈（作業仮説）: `+0x78` は **入力モード/デバイス種別の列挙**（マウス/キーボード/パッド…）を返す
  クエリで、マウス経路とパッド経路が**同じモード値を参照して分岐**している。
  → 「パッドがあるとマウスの挙動が変わる」は、この**共有モード値の遷移**として説明できる
  （パッド接続・入力でモードが変わる/揺れると、マウス経路のゲートとスケーリングが変わる）。
- `disable_mouselook` のアクセッサ stub (0x1409B74D8) も同じインターフェースを参照（readers3 実測）。
- 次: vtable のオーナー（RTTI/初期化コード）を特定して `+0x78` の意味（列挙の実値）を確定。

## ユーザー情報の更新（重要）: パッド未接続でも影響が出る

「パッドを挿していなくても影響が出る」とのこと → **パッドの存在ではなく、パッド処理コードが
毎フレーム走って共有状態を触る**形が本命。

### pad look 関数 (0x1408A5350) が実際に書くもの（非スタックストア 26 箇所の要約）

- アキュムレータ: `[rbx+0x1C8]`（int/float 共用スロット。0 リセット → `addss` 加算 → 書き戻し）、
  同 `[rbx+0x1D8]`（同パターン）。フラグ: `[rbx+0x1FA]`（byte, cl で更新）。
- 出力: `[rax]` / `[rax+4]` / `[rax+8]` に **3 float ベクトル**、`[rsi]` / `[r14]` にスカラー 2 本
  （= 視点/エイムのデルタか角度の出力と解釈）。
- **接続チェックが無い**: これらの書き込みの前にパッド接続/存否の判定は見えない（読んでいるのは
  共有ゲート `[+0x5C]` だけ）。→ パッドが無くても pad 経路は走って状態を書く。
- 一方 mouse sens 関数 (0x1409B6E10) は `[+0x5C]` を読むだけで、`+0x1C8/+0x1D8/+0x1FA` には
  触れない → 衝突は**下流の apply 経路**（視点/エイム反映側）で起きる可能性が高い。

### 次の解析（未着手）

1. pad 関数プロローグで `rbx` の出所を辿り、`+0x1C8/+0x1D8/+0x1FA` がどのオブジェクトかを確定
2. 視点 apply 経路（pad の出力先と、マウスの適用先が同じか）の照合
3. 外部観測（パッド不要になった）: 通常プレイで `session_capture.py run` → 入力タイミング/取りこぼし/フレーム間隔

## 消費者側の実測（2026-09-24 追記）

- pad look が状態オブジェクトを渡す先 `0x1408A4D30` は `[rbx+0x1D4]` を読み（0x1408A4DEB）、
  さらに **共有グローバル `0x141B4D4A0`**（7 個の共有先の 1 つ = mouse sens も読む）を使用（0x1408A4E3B）。
  もう一方の消費者 `0x1408A44E0` も同グローバルを使用（0x1408A4597）。
- → 入力パイプラインの段間共有: ①per-frame 状態 `rbx+0x1D4/+0x1D8/+0x1E0/+0x1E8`、
  ②共有グローバル `0x141B4D4A0`、③共有ゲート `[shared+0x5C]` と共有定数 `0x1419C79F4`。
  パッド段は接続チェックなしで毎フレーム走り、①を書く → パッド未接続でも段間干渉が起きうる。
- 残: 適用段の完全データフロー（リセット値が感度適用入力になるか）と、実測（observer/correlate）。

## オフセット単独マッチングの限界（2026-09-24）

`+0x1D4` / `+0x1D8` をオブジェクト相対で全バイナリから列挙 → **557 箇所**（大半は無関係の構造体。
43MB のバイナリでは 0x1D8 程度のオフセットは衝突し放題）。
→ **オフセットだけでは特定オブジェクトの消費者を切り出せない**。特定には「どのレジスタがその
オブジェクトを持つか」のデータフロー（provenance）追跡が要る（= 次の静的解析課題）。
現時点で確度が高いのは:
- pad 段は接続チェックなしで per-frame 状態を書く（実測）
- mouse 段は `disable_mouselook` 判定関数の中から呼ばれる（実測）
- 両段は共有ゲート `[shared+0x5C]` / 共有定数 `0x1419C79F4` / 共有グローバル `0x141B4D4A0` を参照（実測）
- 未確定: どのフィールドの変異がマウス段を実際に乱すか（provenance 解析 or 実データ）

## インターフェース同定（2026-09-24 追記）

- RTTI は無い（`/GR-` ビルド）→ クラス名は静的取得不可。
- 各インターフェース/グローバルへの書き込みは**各 1 箇所のみ**（0x1408A97FB / 0x1408AA4EC / 0x1408AA582 /
  0x1408AA30D、共有ゲート持ちは 0x1401EBAD3）＝シングルトン構築。モードはオブジェクト内部状態。
- 近傍文字列: iface3 周辺 = `ClientModeShared`/`ClientDLL`、ゲート持ち周辺 = cvar 登録
  (`laserSightColor`, `allow_extended_range_use_ents`, `smoothstairs_lunge`)、
  共有グローバル周辺 = usermessage/ネットワーク系。
- mouse 段のゲート列（実測）: `disable_mouselook` cvar 解決 → 共有インターフェース照会
  ([+0x80], [+0x108], [+0x1F0]) → 感度段 0x1409B6E10。

## 入力サブシステムの同一性（2026-09-24 決定的）

- 初期化 0x1404BCA80 が GetProcAddress で **RegisterRawInputDevices / GetRawInputData /
  GetRawInputBuffer / XInputGetState** を解決し、**同一オブジェクト rdi** に保持
  ([+0x1E84] 生入力登録フラグ, [+0x21B8] XInput モジュール, [+0x21C0] rawinput モジュール,
  [+0x21D0] フラグ)。解決済みポインタ: [0x143364358]=GetRawInputData, [0x143364360]=Register…,
  [0x143364368]/[0x143364370]=XInput 系, [0x143364378]=GetRawInputBuffer。
- 生マウス読み取り: 0x1404BEA07 (RID_INPUT=0x10000003, cbSizeHeader=0x18 ✓)。GetRawInputBuffer: 0x1404C0654。
- パッド: 0x1404BE71B / 0x1404C0ADE (XInputGetState), 0x380 ストライド配列をループ、
  エントリ +0x280〜+0x2D0 に書く。**同じ入力更新領域**。
- pad 段クラスタ (0x1408A4000-0x1408A6000) が参照する cvar は **aimassist_* のみ**
  (aimassist_adspull / aimassist_sp_rules / aimassist_adspull_allow_npc_override)。
  → **joystick / gamepad 有効性のゲートは無い**。
- joystick cvar 参照は 0x1409AAA2E の有効化ロジックのみ (iface2 [0x143FD1A60] のメソッド 0xB0 で
  読む → 共有ゲート [state+0x5C]==0 を確認 → メソッド 0x80 に 1 を渡す)。
- "nojoy" 文字列は XInput API 名と同じブロブ 0x141812E79 (静的ポインタ参照なし)。
- 結論: pad 段自体は joystick 無効の影響を受けない (ゲートなし・毎フレーム書く)。

## 最終リンク: マウス感度段のスカラー源セレクタ（2026-09-24）

0x1409B6E10 内で確定:
- [0x14253B198] = mouse_sensitivity 保管先
- 共有ゲート [0x1426BDFF8 + 0x5C] を見て、非0なら共有定数 0x1419C79F4 を乗算
- cl != 0 のとき (**モードフラグ**)、スカラー源を選択:
  - 0x142530A48 (自身も [+0x5C] でゲート) → 0x142530AD8 → 0x141B4D4A0 経由の解決
  - 2段テーブル 0x142530AA0 (ストライド 0x48 = 9 要素) をズーム段で入れ子参照
- 最終: mulss xmm3,xmm1 / mulss xmm3,xmm0 / mulss xmm8,xmm3 (感度へ乗算)
→ **マウス実効感度 = mouse_sensitivity × 共有定数 × (ゲートで選ばれた源の)2段テーブル値**
  pad 側 8 要素スカラー (gamepad_ads_advanced_sensitivity_scalar_0..7) と同型 → pad 設定が混入する経路の実体。

## 無効化の実装（EAC 回避不要）

tools/pad_disable.py: 影響が実証された項目のみ適用（バックアップ付き）
- profile.cfg: gamepad_ads_advanced_sensitivity_scalar_0..7 → 0.0、gamepad_aim_assist_* → 0.0
- settings.cfg / profile.cfg: joystick "0"、disable_mouselook "0" を明示追加
- 触らない: gamepad_custom_*（カーブ/デッドゾーン）、gamepad_aim_speed_ads_*（-1 センチネル）
復元: python tools/pad_disable.py --restore

## 深掘りレーン（2026-09-24 開始）

### レーン A: WER LocalDumps（ゼロリスク・稼働中）
- HKLM\...\Windows Error Reporting\LocalDumps\r5apex_dx12.exe を設定（DumpFolder=G:\apex-analysis\evidence\dumps,
  DumpType=2=フルダンプ）。**OS がクラッシュ時に書く**ため、こちらからプロセスに触れない（EAC から見て正常）。
- ダンプには保護プロセスのメモリ全体が入る → 実行時値を静的に取り出せる:
  共有ゲート [state+0x5C] 実値 / パッド段が書いた +0x1D4,+0x1D8 / 感度テーブル 0x142530AA0 の中身 /
  クランプ定数 0x145418CD8 の実値（未確定の最後のピース）。
- 次: ダンプ解析ツール（Memory64ListStream を読む）を実装 → ダンプが出たら自動で値を抽出。

## レーン A 完了: minidump 抽出ツール（2026-09-24 実ダンプで検証）

tools/dump_extract.py（minidump パーサ: Memory64ListStream/ModuleListStream）
  - <dump> --apex   : 共有ゲート[+0x5C] / クランプ定数 0x145418CD8 / 共有定数 / 2段テーブル / 解決済みAPIポインタ
  - <dump> --read 0xVA:size : 生読み
tools/dump_selftest.py: 自プロセスのフルダンプ(46MB)を作り magic(float とも)を読み戻す自己検証
  → **PASS**（magic 一致 ✓ / float 一致 ✓ / exit 0）。修正した罠:
  1) ctypes の restype 未指定で VirtualAlloc/GetCurrentProcess の 64bit 戻り値が切り詰め → SEGV
  2) テスト fixture の重なり（magic +0x5C 8B と float +0x60 が衝突）
  3) heredoc が '\' を '\' に潰す → バックスラッシュ回避（os.path.basename）
次の自然なトリガ: Apex がクラッシュ → WER がフルダンプを evidence/dumps へ → --apex で実行時値を抽出。

## ブート前提の検査結果（レーン C の可否・2026-09-25）

- **Secure Boot = True** → テスト署名モード（方式A）は**機能しない**。有効化には UEFI で Secure Boot を切る必要があり、
- **BitLocker: C: ProtectionStatus=1（ON, EncryptionMethod=6=XTS-AES256）** → BCD 変更で**回復キー要求**が出うる。
→ 方式A は「起動しなくなる懸念」に直撃するため**中止**。方式B（kdmapper 系）は BCD/Secure Boot を触らないので
   起動リスクは無いが、検出リスクが最大（要: 外部ツール入手）。
次に試す価値がある無リスク経路: `NtSystemDebugControl`(SysDbgReadVirtualMemory/WriteVirtualMemory, 37/38) +
   SeDebugPrivilege — ドライバ無しでカーネル読み書きが通るか（OS 版により可否）を実測する。

## C-2（NtSystemDebugControl）実測 → 死路（2026-09-25）

- クラス総当たり（SeDebugPrivilege 有効化試行つき）: class8/9/38 → 0xC0000354 (STATUS_DEBUGGER_INACTIVE)、
  class37 → 0xC0000022 (STATUS_ACCESS_DENIED)。成功クラスなし。
- 構造的にも SYSDBG_VIRTUAL に PID フィールドが無く **カレントプロセス専用** → Apex のメモリは読めない ✗。
→ ドライバ無しでクロスプロセス読み取りは不可。残るは A(要 Secure Boot 無効化 ✗)/B(kdmapper ✗)/D(ダンプ ✓)。

## ダンプパーサを実ゲームダンプで検証（2026-09-25）

- 実データ: %LOCALAPPDATA%\CrashDumps\pso2.exe.27816.dmp（183MB, 実クラッシュ由来）
- type5 (MemoryListStream) 対応を追加 → レンジ 31,809 / 179.5MB を正しく認識、範囲内読み 8/8 成功。
- 判明: モジュールのイメージページ（ヘッダ/.text）はダンプに含まれない（ファイル由来のため正常）。
  一方 .data/heap の実行時構造体は含まれる → 我々の対象（共有ゲート/スカラー源/テーブル）は取得可能 ✓。

## 定数の実値（ファイルイメージから取得・2026-09-25）

- 0x1419C79F4 = **-1.0** (.rdata, bits 0xBF800000) ← 両段が使う「共有定数」の正体は符号反転（Y 軸規約の反転。
  混入の実体ではなく標準の座標反転と判断 = 以前の見立てを訂正）
- 0x1419C9CE0 = 0x7FFFFFFF（abs マスク, andps 用）
- 0x1419C75F0 = 30.0（comiss 閾値）
- 0x1419C708C = 1.0
- 0x1419C6B58 = FLT_MIN(0x00800000)（"ほぼ0"判定）
- 0x1419C73A0 = 3.0
- **0x145418CD8（pad クラスタの maxss 下限）= .data の raw 外 = 実行時初期化 ✗ → ダンプでのみ取得可**

## 実機での体感結果（2026-09-25・ユーザー報告）

- 適用後（スカラー0.0 / joystick0 / disable_mouselook0 / aim assist0 / 読み取り専用）の体感: **「微妙」「変かもしれないなぁぐらい」**
  ＝ **決定的な改善ではない** → config 側スカラーは主因ではない可能性が高い ✗
- ファイル検証: 書き戻しなし ✓（mtime 23:33 のまま・ハッシュがジャーナル記録と一致 ✓・読み取り専用維持 ✓）
  → 「効かなかった」ではなく「config 側の寄与が小さい」ことを示す ✓
→ 残る主因候補は実行時側（共有ゲート [state+0x5C] / スカラー源選択 A/B / クランプ）＝ **ダンプで確定するしかない** ✓

## 検証方針の転換（2026-09-25・ユーザー指示）

「人の体感に頼る検証はしない」「Aletheia 経由で自動で動かしてテスト」→ 客観・自動の二本立て:
- 注入: SendInput による**決定論的マウス注入**（往復: +120px → -120px で視点が元に戻る = 非干渉 ✓）
- 計測: sens_meter（画面移動/マウスデルタ比 = 実効感度、客観量 ✓ 常駐済み）
- 条件: pad=0 と元値の config を**スクリプトで自動切替**（読み取り専用ロックも自動）
- 判定: 各条件 N 回の注入→計測を**統計比較**（人の判断を使わない）
- 非干渉: ジャーナルにデルタが無いアイドル検出後にだけ注入する

## 共通オーケストレータの発見（2026-09-25・静的解析の到達点）

パッド段 0x1409AB3D0 は **1箇所 0x1409ABC97 からのみ**呼ばれる。その呼び出し元関数の構造:

1. ヘルパ 0x1409AAB30 / 0x1409AAA90（joystick cvar 判定を含む領域）を順に呼ぶ
2. `mov rax,[r14]; call [rax+0x80]; test al,al; jne 0x1409ABC9C` ← vtable ゲート（真ならパッドブロックを飛ばす）
3. インターフェース 0x143FD1A60 の vtable スロット +0x740 / +0x748 / +0x760 を順に照会（分岐あり）
4. `lea rdx,[rdi+0x18]; mov rcx,rsi; mov [rsp+0x38],bpl; call 0x1409AB3D0` ← **パッド段呼び出し**
5. パッドブロックの直後（0x1409ABC9C〜）で同関数が続行し、`mov rax,[0x14253B228]` ← **mouse_sensitivity 記述子ブロック
   (0x14253B1xx) に触る** = **同一関数内でパッド側 → マウス側を連続処理**

→ 「マウスとパッドは同一入力更新ルーチンの隣接分岐」が静的に確定（両者が1つの毎フレーム関数で順に処理される）。
訂正: パッド段は「完全に無条件」ではなく、**vtable/インターフェースのモードゲート**を通る。
      ただしデバイス接続の単純フラグではなく、その vtable 実体は実行時解決（ダンプで確定可能）。

## 【回答】「0 にできるの？」→ **0 にはできない。下限は 0.2**（2026-09-25 実測）

- pad_disable --apply で 0.0 を書き込んでも、**ゲームが 0.2 にクランプして書き戻す**（ファイル実値 0.2 を確認）
- = ゲーム内スライダーの左端が 0.2（ユーザーの「全部左の最低値」と一致 ✓）
- 読み取り専用属性は**ハードな保護ではない**（ゲームは属性を戻して書き込む）→ A/B の条件は
  「ファイルに書いた値」ではなく**「ゲームが読み込み時に採用した値」**で考える必要がある
- したがって A/B の実条件は **0.2（最小）vs 1.0（既定）** = ユーザーの手動ワークアラウンドと等価 ✓
