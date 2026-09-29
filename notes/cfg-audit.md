# 外部 autoexec.cfg の静的監査（Apex Legends v3.0.1.28）

対象: `salvatorepolverino/Apex-Legends-Best-Configs-Ever-Made` の `autoexec.cfg`（main, 2026-09-28 取得, 305行/224項目）
照合先: `C:\Program Files\EA Games\Apex\r5apex_dx12.exe`
build `R5pc_r5-301_J28_CL11570498_FSv30_1_2026_09_16_17_18` / v3.0.1.28
sha256 `8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825`（42,934,112 bytes）
配布モジュール: `EOSSDK-Win64-Shipping.dll`, `paks/Win64/ui(01).dll`, `steamnetworkingsockets.dll`, `bink2w64.dll`,
`steam_api64.dll`, `OriginSDK.dll`, `GFSDK_Aftermath_Lib.x64.dll`, `Core/Activation*.dll`, `start_protected_game.exe` 等15本

## 手法（すべて静的・ローカル）

1. **登録スタブ列挙** `tools/cvar_stubs.py` — `.text` 内の RIP相対 `lea r64,[rip+d]` を総走査し、
   name風文字列を指すサイトを `.pdata` で関数に帰属。関数サイズ ≤0x600 のもの＝登録スタブ候補。
   結果: 77,545関数中 8,778関数 / 14,573サイト。
2. **記述子フィールド抽出** `tools/cvar_fields.py` — スタブ内のストアを解析し
   `obj+0x10=name, +0x28=flags, +0x38=handle, +0x40=既定値文字列, +0x50=type, +0x64/68=min/max` を回収。
   → **3,608 cvar の記述子を確定**（既定値・flags・min/max 付き）。`evidence/cvar_fields.tsv`
3. **読み手カウント** `tools/cvar_readers2.py` — `.text` の全 dword を1パス走査し、
   各 cvar のハンドル（obj+0x38）と値スロット（obj+0x58）への RIP相対参照を数える。
   検証: `mouse_sensitivity` の読み手は `0x1409b6e10`（感度計算関数, 既知）✓。`evidence/cvar_readers2.tsv`
4. **モジュール横断の名前探索** `tools/name_exists.py` — exe＋全 DLL/EXE で `"<name>\0"` を完全一致検索
   （大文字小文字違いは別枠で記録）。`evidence/audit/absent-names.tsv`
5. **突き合わせ** `tools/cfg_audit3.py` → `evidence/audit3/{autoexec-audit.tsv,candidates-by-category.tsv,equivalents.tsv}`
6. **クリーン cfg 生成** `tools/mk_fixed_cfg.py` → `evidence/audit3/fixed-autoexec.cfg`

再現:
```bash
cd G:/apex-analysis/tools
../.venv/Scripts/python.exe cvar_stubs.py   "C:/Program Files/EA Games/Apex/r5apex_dx12.exe" ../evidence/cvar_stubs.tsv
../.venv/Scripts/python.exe cvar_fields.py  "C:/Program Files/EA Games/Apex/r5apex_dx12.exe" ../evidence/cvar_fields.tsv
../.venv/Scripts/python.exe cvar_readers2.py "C:/Program Files/EA Games/Apex/r5apex_dx12.exe" ../evidence/cvar_fields.tsv ../evidence/cvar_readers2.tsv
../.venv/Scripts/python.exe cfg_audit3.py <autoexec.cfg> ../evidence/cvar_fields.tsv ../evidence/cvar_readers2.tsv \
        ../evidence/cvar_stubs.tsv ../evidence/audit/absent-names.tsv "C:/Program Files/EA Games/Apex/r5apex_dx12.exe" ../evidence/audit3
```

## 結果サマリ（224項目）

| 判定 | 件数 | 意味 |
|---|---|---|
| registered | 94 | 記述子あり・このビルドのコードが値を読む＝**有効** |
| registered-scriptread | 8 | 記述子あり・`SCRIPTS_ONLY`（スクリプト側が名前で読むので native xref は0）＝有効 |
| registered-unverified | 5 | 登録スタブはあるが記述子の自動抽出に載らなかった（ゲーム自身が cfg に書く名前を含む）＝有効 |
| registered-noread | 12 | 登録はあるが native の読み手が見つからない（効果不明） |
| cheat | 13 | `FCVAR_CHEAT(0x4000)`：sv_cheats が必要＝**MPでは効かない** |
| string-only | 8 | 文字列だけ存在し cvar として登録されていない（他cvar名の部分一致含む） |
| videoconfig-key | 1 | `setting.*` キー（videoconfig.txt 行き） |
| absent | 83 | **このビルドに名前自体が存在しない**（=死に項目） |

「有効」側 107項目・死に項目 91（absent83+string-only8）＋13項目が CHEAT で実質無効。
＝**元リストの 41%（91/224）は現行ビルドでは何も起きない**。README の `(Works)` 表記は根拠なし。

## 死に項目（absent 83）と現行の代替名

エンジン世代が古い（Titanfall/Source2013 由来の名前、CS:GO 系の名前）ものが大半。

| 死名 | 現行の対応 |
|---|---|
| `m_rawinput` | `cl_use_raw_input_buffer`（def=1, READ）/ `raw_input_deadzone` |
| `cl_bones_incremental_blend` | `cl_bones_incremental_transform` |
| `cl_interp` | `cl_interpolate`（def=1.0）, `cl_interpolation_before_prediction` |
| `mat_antialias` | `mat_antialias_mode`（videoconfig `setting.mat_antialias_mode`） |
| `r_shadows` / `mat_shadowstate` / `r_shadowmaxrendered` / `r_shadowrendertotexture` | 影は csm 系 + videoconfig `setting.shadow_enable` / `setting.shadow_maxdynamic` / `setting.csm_*` |
| `mat_disable_bloom` / `mat_bloom_scalefactor_scalar` | `mat_bloom_*`（clamp 系）, videoconfig `setting.volumetric_lighting` |
| `mat_depthfeather_enable` | `dof_*`（`dof_enable` ほか）, `hud_setting_adsDof` |
| `cl_phys_props_enable/max` | `max_props`, `sv_max_props_*`, `props_break_max_pieces*` |
| `cl_detailfade` / `cl_detaildist` | `cl_anim_detail_dist`(1500)/`cl_anim_face_dist`(250)/`r_lod_switch_scale` |
| `mat_disable_bloom`, `mat_bumpmap`, `mat_specular`, `r_eyes`, `r_teeth`, `r_flex`, `r_drawmodeldecals`, `r_maxmodeldecal`, `mp_usehwmmodels`, `mp_usehwmvcds`, `cl_ejectbrass`, `tracer_extra`, `r_drawtracers_firstperson`, `r_fastzreject`, `r_lightaverage`, `r_hunkalloclightmaps`, `r_queued_post_processing`, `r_water*`, `rope_*`(smooth/subdiv/rendersolid), `env_lightglow`, `glow_outline_effect_enable`, `r_cleardecals`(→ string-only), `snd_mixahead`, `snd_musicvolume`, `snd_async_fullyasync`, `snd_headphone_pan_exponent`, `snd_setmixer`, `sound_classic_music`, `miles_nonactor_occlusion`, `miles_max_sounds_per_server_frame`, `cl_timeout`, `cl_cmdrate`, `net_compresspackets(_minsize)`, `cl_forcepreload`, `sv_forcepreload`, `mat_queue_mode`, `r_dxgi_max_frame_latency`, `voice_forcemicrecord`, `cl_wpn_sway_interp`, `tf_particles_disable_weather`, `stream_mips_use_staging_texture`, `sort_opaque_meshes`, `net_compresspackets`, ... | **対応なし（削除済み）** |

全リストは `evidence/audit3/autoexec-audit.tsv` の verdict=absent 行。候補名の機械推定は `equivalents.tsv`。

## `FCVAR_CHEAT` 13項目（MPでは効かない）

`building_cubemaps` `cl_disable_ragdolls` `cl_particle_limiter_max_particle_count` `cl_particle_limiter_max_system_count`
`cl_particle_limiter_min_kill_distance` `cl_particle_snoozetime` `map_settings_override` `mat_fullbright`
`mat_colorcorrection` `nx_static_lobby_mode` `mat_postprocess_enable` `host_sleep` `r_drawsky`

根拠: 記述子 +0x28 の flags が 0x4000（exe 内に Source の flag名テーブル `CHEAT "cheat"` / `GAMEDLL "sv"` / `USERINFO "user"` 等が存在）。
`sv_cheats` 自身の記述子は `REPLICATED|ARCHIVE_XBOX`＝サーバー権威で、通常MPでは 0。
傍証: ゲーム自身が書く `settings.cfg` / `profile.cfg` / `videoconfig.txt` に CHEAT cvar は1つも現れない。
（フラグによる設定可否ゲートの分岐自体は本パスでは逆解析していない＝下記「限界」）

## 読まれない12項目（効果不明）

`cl_SetupAllBones` `cl_predictweapons` `cl_showfiredbullets` `sidearmSwapSelectDoubleTapTime` `chroma_enable`
`mat_colcorrection_disableentities` `sound_num_speakers` `cl_particle_fallback_base` `cl_particle_fallback_multiplier`
`r_norefresh` `cl_lagcompensation` `match_updateRate`
※ ハンドル経由の参照が0。値ポインタが初期化時に他所へコピーされる型は拾えないため「無効」ではなく「効果不明」。
※ 逆に `SCRIPTS_ONLY` 系（hud_setting_* 等）はスクリプトが名前で引くので native xref が0で正常。

## 元リストに無い現行 cvar（抜け候補）

`evidence/audit3/candidates-by-category.tsv`（3,482項目から CHEAT/開発用/test系を除外しカテゴリ分類）。
注目度の高いもの:

- 入力: `cl_use_raw_input_buffer`(1) / `raw_input_deadzone` / `gamepad_*`（前回のパッド漏れ対策で既知）
- 性能: `fps_max_use_refresh`(0) `fps_max_vsync`(0) `fps_absolute_max`(300) `cl_precache_use_pso_threads`(1)
- HUD: `hud_setting_showEnemyHealthBar`(1) `hud_setting_compactOverHeadNames`(0) `hud_setting_showCallsigns`(1)
  `hud_setting_showButtonHints`(1) `hud_setting_showHopUpPopUp`(1) `hud_setting_aind`(0) `hud_setting_chainHeal`(1)
- 表示/操作: `colorblind_mode`(0) `damage_indicator_style_pilot`(2) `player_setting_holdtosprint`(0)
  `weapon_setting_autocycle_on_empty`(1) `cl_prevent_weapon_text_hints`(1)
- オーディオ: `miles_output_device`（ゲーム自身が書く）, `miles_*` 群（occlusion/cache/driver mix 等）
- テレメトリ: `pin_opt_in` `telemetry_*`（元リストにもあるが現行仕様の再確認対象）
- 影: videoconfig 側 `setting.csm_*` / `setting.shadow_*`（cvar 名で書いても効く: `csm_enabled`, `csm_coverage`,
  `csm_cascade_res`, `viewmodel_selfshadow_enabled` は登録済み）

## 運用上の注意

- 元 cfg の `fps_max "143"` は README の起動オプション `+fps_max 0` に**上書きされる**（`+exec` が先に実行され、後続の `+fps_max` が後勝ち）。
- `cl_smooth` は同ファイル内で 2 回定義（`0`→後に `1`）＝**後勝ち**。`snd_setmixer` も2行あるが両方死に。
- `ssao_downsample` は cvar ではなく videoconfig のキー → `videoconfig.txt` に `"setting.ssao_downsample" "0"` として書く。
- `stream_cache_high_priority_static_models` / `stream_cache_preload_from_rpak` / `stream_drop_unused` は現行ビルドに有効。

## 限界（未検証）

- フラグ（CHEAT/DEVELOPMENTONLY）による実行時ゲートの分岐は未逆解析。DEV フラグは「-dev 無しでは効かない」という
  Source 解釈もあるが、本ビルドでは `cl_use_raw_input_buffer`(DEV) がゲーム自身に読まれており、DEV=即無効とは言えない。
- pak 内（圧縮）は文字列が読めない。cvar 登録は native 側なので影響は無いが、**スクリプト専用の名前**は追えない。
- `string-only` の一部（`rate`, `r_cleardecals` 等）は「別名で存在」ではなく「別用途の文字列」の可能性が高い
  （`rate` は EOSSDK/steamnetworkingsockets 内の一般語にも一致）。

## カバレッジ実測（tools/coverage.py, 2026-09-28）

| 対象 | 数 | 備考 |
|---|---|---|
| 検証済み記述子（既定値/フラグ/読み手まで抽出） | **3,612** | `evidence/cvar_fields.tsv`（関数サイズ上限を外しても +4 のみ → 律速はサイズではなく抽出パターン） |
| 小関数から名前参照あり・記述子未検証 | 5,438 | ランダム抽出すると大半は非cvar（RUIプロパティ `HudElemSetColorBG`、型名 `VertexBuffer`、アニメ名 `ACT_180_LEFT` 等）。実体は文字列テーブル |
| ゲーム自身が user cfg に書く名前 | 197 | うち **36 が台帳外**＝穴の実在証明。全部 C（何らかの関数から参照）に含まれる＝コードには存在する |
| 台帳外の36名の正体 | `mouse_zoomed_sensitivity_scalar_0..7`, `gamepad_ads_advanced_sensitivity_scalar_0..7`, `gamepad_aim_speed_ads_0..7`, `dialogue_cat_*`(9), `bind_US_standard`, `bind_held_US_standard`, `miles_output_device`, `fov_disableAbilityScaling`, `sound_without_focus` | 家族(indexed)登録は 3,799B級の大きなルーチンで行われ **lea→store の対応が取れない**ため抽出漏れ |
| 「ユーザー設定っぽい接頭辞」で C−A に残る名前 | 141 | 実cvarは `aimassist_*` 群, `miles_*` 群, 上記スカラー群, `dialogue_cat_*` など数十。残りは音イベント名/スクリプトプロパティ |
| videoconfig `setting.*` キー | 46 | 27 は同名 cvar あり、19 はキー専用 (`gamma`, `fullscreen`, `defaultres`, `mat_vsync_mode`, `volumetric_*`, `ssao_quality`, `map_detail_level`, `dynamic_streaming_budget` …) |

未着手の面: **ConCommand 一覧**（`weapon_inspect` `miles_reboot` `exec` `unbind` 等は個別確認のみ）、**キーバインド**（任意・無限）、**起動オプション**（存在確認のみ）、**pak内スクリプト**（圧縮で不可読）。
→ 「ユーザーが触れる全項目」の完全列挙は原理的に不可（バインド/スクリプト）。実用ノブ（cvar＋videoconfigキー）は上記の精度。

## 「autoexec で触れる全項目」の全件解析（2026-09-28 追加パス）

`tools/cvar_fields2.py`（ストアトラッカー v2）で家族・テーブル経由の登録まで回収。

| tier | 件数 | 内容 | 出典 |
|---|---|---|---|
| A | 3,608 | 登録スタブ完全一致（name@+0x10 / handle自己参照@+0x38 / flags / 既定値） | `evidence/cvar_fields.tsv` |
| A2 | 135 | 家族・テーブル経由で回収（既定値文字列あり）: `mouse_zoomed_sensitivity_scalar_0..6`, `gamepad_ads_advanced_sensitivity_scalar_0..6`, `gamepad_aim_speed_ads_0..6`, `dialogue_cat_*`(9), `zipline_cooldown_time_*`, `miles_*`(38), `stream_cache_*`, `cl_view_cone` 等 | `evidence/cvar_fields_v2.tsv` |
| C | 29 | 名前は実在しコードが名前ルックアップで読むが、記述子が静的領域に存在しない（動的登録＝pak内スクリプト由来の可能性）: `aimassist_*`(22), `cl_hud_minmode`, `r_drawDecals` 等 | `out/cvar-ledger.tsv` |
| X | 1,763 | cvar ではないエンジンの名前テーブル（RUIメソッド `RTKPanel_Destroy`/`GetPlaylistCount` 等） | `out/non-cvar-name-tables.txt` |

**結論: autoexec から設定できる cvar は 3,743件（A+A2、既定値/フラグ付き）＋動的登録29件（既定値は静的取得不可）＝ 3,772件。**
X は cvar ではないため台帳から除外した。

回収値の検証（前セッションの手動解析と一致）:
- `mouse_zoomed_sensitivity_scalar_0..7` 既定 `1.0` / min 0.1 / max 20、flags `ARCHIVE(0x80)` ✓（notes の手動解析と一致）
- `gamepad_aim_speed_ads_0..7` 既定 `-1` / 範囲 -1〜7 ✓（-1=ヒップ値を継承するセンチネル、という前回の結論と一致）
- `gamepad_ads_advanced_sensitivity_scalar_0..7` 既定 `1.0` / min 0.1 / max 20 ✓

残る未取得: 動的登録29件の既定値、ConCommand 一覧、キーバインド、起動オプション、pak内スクリプト。
成果物: `out/CVAR-LIST-FULL.md`（全3,772件の可読一覧）, `out/cvar-ledger.tsv`（機械可読）, `out/autoexec.cfg`（末尾に追加回収分の候補）。

## 競技ルールの確認（外部一次資料・2026-09-28取得）

`evidence/rules/` に ALGS ルールブック本体（Year2 / Year5 / Year6）と config 関連記述のスキャン結果を保存。

| ルールブック | ページ | `autoexec`/`videoconfig`/`local.cfg`/`fps_max`/`letterbox`/`csm_enabled` |
|---|---|---|
| Year 2（Battlefy配信） | 8p | すべて**あり**（「編集中身は5項目に限定」方式） |
| Year 5 | 55p | **0件** |
| Year 6（現行, algs.ea.com/year-6-rules.pdf） | 54p | **0件** |

- Year 2 の実文: 「Competitors may only add or edit the following Game files and configuration: local.cfg / autoexec.cfg / videoconfig.txt / Launch Options」＋「…configuration items specified above: fps_max / mat_letterbox_aspect_goal / mat_letterbox_aspect_threshold / "setting.csm_enabled" "0" / custom reticles」
- 現行は config ファイルの節が消えており、代わりに包括条項（unfair advantage を与えるソフト/ハードの使用禁止、exploits/undocumented features の利用禁止）のみ。
- つまり「autoexecはファイルとして許可、中身は5項目」は **Year 2 時点の運用**。 EAフォーラム等で今も引用されている同文言はその孫引き。
- ゲーム側（Respawn）は別レイヤー: 2024/2 に `+exec` の cfg チェーンを無効化＋自動化を不正と宣言（現行も有効）。

## 3バリアントの確定（最終成果物）

`configs/` に配置。いずれも「このビルドのコードが値を読む」cvarのみで構成（111行版が full 相当）。

| 版 | 有効行 | 差分 | 位置づけ |
|---|---|---|---|
| `configs/full/autoexec.cfg` | 111 | — | 視覚カット全部入り（コミュニティ標準＋α） |
| `configs/ranked/autoexec.cfg` | 105 | 「情報・挙動に触る6行」を除外（`fog_enable`, `r_particle_timescale`, `cl_footstep_event_max_dist`, `rope_wind_dist`, `ordnanceSwapSelectCooldown`, `sidearmSwapSelectCooldown`） | ランク向けの中間 |
| `configs/low-risk/autoexec.cfg` | 35 | ゲーム自身が `settings.cfg`/`profile.cfg`/`videoconfig.txt` に書くキーのみ（＋`fps_max`） | 規約文言に厳密な人向け |

- 層分類の根拠: 層1=メニュー到達可能（ゲーム自身が書くキー34本＋`fps_max`）。層2=演出カット（メニュー外）。層3=情報・挙動（足音/視界/遮蔽/切替時間）。層4=自動化（本cfgにはゼロ）。
- EULA 文言: 「Modify any file or any other part of the EA Service that EA does not specifically authorize you to modify」。演出カット系cvarでのBAN確例は未確認（フォーラムの自称投稿のみ）。

## 実機設置（2026-09-28）

- `C:\Program Files\EA Games\Apex\autoexec.cfg` に **full版**（111有効行）を設置。17,115 bytes / sha256 `0bacd73a…a097`（ソースと一致） / 属性 `ReadOnly, Archive`。
- 既存ファイルは無し（バックアップ不要）。UAC昇格コピーで実施し、`%TEMP%\apex_install_log.txt` に記録。
- **残: EAアプリの起動オプションに `+exec autoexec.cfg -novid` を追加**（EXE内に `autoexec` 文字列が0ヒット＝自動実行されないため必須）。EAアプリの起動オプションはレジストリ/ローカルiniに保存が見つからず、UI操作が必要。
- 編集時は `attrib -R` で読み取り専用を外す。原本は `configs/full/autoexec.cfg`（＋`out/autoexec.final.cfg`）。
