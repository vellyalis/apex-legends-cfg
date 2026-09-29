# CVAR-GUIDE — Apex Legends v3.0.1.28 で「効く」autoexec の中身

対象 exe: `r5apex_dx12.exe` sha256 `8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825`
（build `R5pc_r5-301_J28_CL11570498` / v3.0.1.28）

## 使い方

1. `autoexec.cfg` を `r5apex_dx12.exe` と同じフォルダに置く（管理者権限が要る）
2. 起動オプションに `+exec autoexec.cfg` を足す（EA アプリ / Steam の「ゲーム起動オプション」）
3. **ゲームを終了してから編集**。起動中に書き換えると終了時に上書きされる
4. いじったら 1 行ずつコメントを外す／書き換える。分からなくなったらこのガイドの表に戻る

各行の根拠マーク:
`[E]` = 登録スタブ＋ネイティブの読み手あり（このビルドで実際に読まれる）/ `[S]` = UI スクリプト側が読む（メニュー設定と同等）/
`[E?]` = 登録はあるが記述子の自動抽出に載らなかった（ゲーム自身が cfg に書く名前を含む）/ `[-]` = 登録はあるが読み手が見つからない（効果不明）

## 効く項目（セクション別）

「既定」はこのビルドの既定値。「変えると」は値の意味と副作用。

### 入力

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `m_acceleration` | `0` | `0` | マウス加速。0=加速なし / 0=無効(推奨)。実行時は感度計算側でも参照される | [E] |

### 操作

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `ordnanceSwapSelectCooldown` | `0.25` | `0` | グレネード選択のクールダウン(秒) / 既定0.25。0=即時切替 | [E] |
| `sidearmSwapSelectCooldown` | `0.25` | `0` | 武器切替のクールダウン(秒) / 既定0.25。0=即時切替 | [E] |
| `sidearmSwapSelectDoubleTapTime` | `0.25` | `0` | ダブルタップでの武器切替時間 / 既定0.25。読み手0 | [-] |
| `player_setting_autosprint` | `0` | `1` | オートスプリント / 既定0。1=常時スプリント | [E] |

### 視点

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_idealpitchscale` | `0` | `0` | 理想ピッチのスケール / 0(既定) | [E] |
| `cl_showpos` | `0` | `0` | 座標/速度表示 / 0=非表示(既定) | [E] |
| `viewmodelShake` | `1` | `0` | 武器の揺れ(ビューモデル) / 既定1。0=揺れなし | [E] |
| `viewmodelShake_sourceRollRange` | `3` | `0` | 同 揺れ量 / 既定3。0=なし | [E] |
| `viewmodel_selfshadow` | `1` | `0` | 武器の自己影 / 既定1。0=影を落とさない | [E] |
| `sprint_view_shake_style` | `0` | `1` | スプリント時の画面揺れ / 既定0。1で揺れを軽減(元リスト) | [E] |
| `slide_viewTiltSide` | `15` | `0` | スライド時の画面傾き(度) / 既定15。0=傾けない | [E] |

### FOV

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `fov_disableAbilityScaling` | `` | `1` | アビリティ使用時のFOV変化を無効化 / 1=無効化(元リスト)。ゲーム自身が profile.cfg に書く名前 | [E?] |
| `cl_fovScale` | `1.27216005`（範囲 1.0〜1.7000000476837158） | `1.55` | FOVスケール(USERINFOでサーバーにも送信) / 既定1.27216005 = 90FOV。1.55=110FOV。※必ずゲーム内設定と一致させる、不一致は挙動が乱れる | [E] |

### フレーム

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `fps_max` | `-1` | `143` | 最大FPS。既定-1=無制限 / モニタHz-1 が定番 (144Hz→143)。※起動オプション +fps_max 0 を付けるとそちらが後勝ち | [E] |

### 描画

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_decal_alwayswhite` | `1` | `1` | デカールを常に白で描く / 1(既定) | [E] |
| `tsaa_blendfactoroverride` | `-1` | `1` | TSAAブレンド係数の上書き / 既定-1=上書きなし。1=上書きする(元リスト) | [E] |
| `tsaa_curframeblendamount` | `0.05` | `0.05` | TSAAの現フレームブレンド量 / 既定0.05。小さいほどゴースト減/ノイズ増 | [E] |
| `tsaa_numsamples` | `64` | `4` | TSAAのサンプル数 / 既定64。4=軽い(元リスト) | [E] |
| `mat_hide_sun_in_last_cascade` | `0` | `1` | 遠景カスケードの太陽を隠す / 既定0。1=遠くの光源グレアを消す | [E] |
| `mat_colcorrection_disableentities` | `0` | `1` | エンティティへの色補正を無効化 / 既定0。1=モデルに色補正を掛けない(読み手0) | [-] |
| `mat_screen_blur_enabled` | `1` | `0` | 画面ブラー(被弾/ダッシュ等) / 既定1。0=ブラーなし | [E] |
| `noise_filter_scale` | `0.006` | `0` | フィルムグレイン量(スクリプト値) / 既定0.006。0=グレインなし | [S] |
| `fog_enable` | `1` | `0` | フォグ(霧) / 既定1。0=霧を切る(遠くが見える/演出は消える) | [E] |
| `fog_enableskybox` | `1` | `1` | 空にかかるフォグ / 既定1。1=空にも霧(元リストのままだと有効) | [E] |
| `r_lod_switch_scale` | `1` | `0.3` | LOD切替距離(1=標準) / 既定1。0.3=遠くを早く低ポリ化=FPS↑/見た目↓ | [E] |
| `mat_forceaniso` | `2`（範囲 0.0〜16.0） | `0` | 異方性フィルタ / 既定2。0=切る | [E] |
| `mat_mip_linear` | `1` | `0` | ミップの線形フィルタ / 既定1。0=切る(チラつくが見た目は軽い) | [E] |
| `mat_filtertextures` | `1` | `0` | テクスチャフィルタ / 既定1。0=切る(粗く表示) | [E] |
| `stream_cache_high_priority_static_models` | `` | `1` | 静的モデルをキャッシュ優先で読む / 1=優先ロード | [E?] |
| `stream_cache_preload_from_rpak` | `1` | `1` | pakから事前ロード / 1(既定) | [E] |
| `stream_drop_unused` | `0` | `1` | 未使用テクスチャを積極的に解放 / 既定0。1=解放(VRAM節約/再読込のヒッチの可能性) | [E] |
| `mat_diffuse` | `1` | `1` | 拡散照明の扱い / 1(既定)。0でプラスチック的な見た目 | [E] |
| `mat_picmip` | `0`（範囲 0.0〜4.0） | `4` | テクスチャ解像度(大きいほど粗い) / 既定0。4=最粗(元リスト) | [E] |
| `stream_memory` | `298000` | `0` | テクスチャのストリーミング予算(バイト) / 既定298000。0=最小(荒い)/GPUのVRAMに応じ 1000000〜3000000 | [E] |

### 明るさ

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `mat_autoexposure_min` | `0.5` | `1.5` | 自動露出の最小値 / 既定0.5。1.5で下限を明るく(暗所が見える/白飛びしやすい) | [E] |
| `mat_autoexposure_max` | `3` | `1.5` | 自動露出の最大値 / 既定3。1.5で上限を下げる(白飛び抑制) | [E] |
| `mat_autoexposure_speed` | `0.1` | `1.5` | 露出が変わる速さ / 既定0.1。1.5で素早く(屋内⇄屋外の切替が速い) | [E] |
| `mat_autoexposure_max_multiplier` | `1.0` | `1` | 露出最大の倍率 / 既定1.0 | [E] |
| `mat_autoexposure_min_multiplier` | `1.0` | `1` | 露出最小の倍率 / 既定1.0 | [E] |

### 影

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `tweak_light_shadows_every_frame` | `0` | `0` | 毎フレーム影を更新 / 0=切(既定) | [E] |
| `vsm_ignore_face_planes` | `0` | `1` | VSMの面カリング / 1=面を無視(元リスト) | [E] |
| `static_shadow` | `3` | `0` | 静的な影の解像度/段(0=切) / 既定3。0=静的影を描かない | [E] |

### SSAO

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `ssao_enabled` | `1` | `0` | 環境遮蔽 / 既定1。0=切る(FPS↑/陰影が薄くなる) | [E] |
| `ssao_blur` | `1` | `0` | SSAOのブラー / 既定1。0=切る | [E] |

### エフェクト

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `bink_materials_enabled` | `1` | `0` | Bink動画マテリアル(ロビー等) / 既定1。0=動画マテリアルを使わない | [E] |
| `cl_aggregate_particles` | `1` | `1` | パーティクルのまとめ描画 / 1(既定) | [E] |
| `cl_cull_weapon_fx` | `1` | `0` | 武器エフェクトのカリング / 既定1。0=カリングしない | [E] |
| `projectile_muzzleOffsetFirstPersonDecayMaxTime` | `0.3` | `0` | 自分視点の弾の軌跡フェード時間 / 既定0.3。0=即消し(元リスト) | [E] |
| `projectile_muzzleOffsetFirstPersonDecayDist` | `1000` | `0` | 同 距離 / 既定1000。0=即消し | [E] |
| `r_particle_timescale` | `1.0` | `3` | パーティクルの時間倍率 / 既定1.0。3=速く消える(元リスト) | [E] |
| `cl_show_splashes` | `1` | `0` | 水しぶき / 既定1。0=切る | [E] |
| `cl_particle_fallback_multiplier` | `1` | `9` | 同 倍率 / 既定1。読み手が見つからず効果不明 | [-] |
| `cl_particle_fallback_base` | `0` | `9` | 負荷時に安いエフェクトへ落とす基準 / 既定0。読み手が見つからず効果不明 | [-] |
| `rope_shake` | `0` | `0` | ロープ(ジップライン)の揺れ / 既定0 | [E] |
| `rope_collide` | `1` | `0` | ロープの衝突判定 / 既定1。0=判定を切る(軽い) | [E] |
| `cl_drawmonitors` | `1` | `0` | ゲーム内モニタの描画 / 既定1。0=切る | [E] |
| `props_break_max_pieces` | `-1` | `0` | 破壊可能オブジェクトの破片数 / 既定-1。0=破片を出さない | [E] |

### 暴力表現

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_gib_allow` | `1` | `0` | ギブス(破片)の発生 / 既定1。0=なし | [E] |
| `violence_ablood` | `1` | `0` | 血のエフェクト / 既定1。0=血なし | [E] |
| `violence_agibs` | `1` | `0` | ギブス / 既定1。0=なし | [E] |
| `violence_hblood` | `1` | `0` | 人間の血 / 既定1。0=なし | [E] |
| `violence_hgibs` | `1` | `0` | 人間のギブス / 既定1。0=なし | [E] |

### ラグドール

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_always_ragdoll_radius` | `500` | `0` | 常にラグドール化する半径 / 既定500。0=常時ラグドールをやめる | [E] |
| `cl_ragdoll_force_fade_time` | `5` | `0` | ラグドールの消滅までの時間 / 既定5。0=即消し | [E] |
| `cl_ragdoll_force_fade_time_local_view_player` | `20` | `0` | 自プレイヤー視点での消滅時間 / 既定20 | [E] |
| `cl_ragdoll_force_fade_time_on_moving_geo` | `5` | `0` | 動く地形上の消滅時間 / 既定5 | [E] |
| `cl_ragdoll_self_collision` | `1` | `0` | ラグドール同士の衝突 / 既定1。0=計算を切る | [E] |
| `cl_ragdoll_maxcount` | `8`（範囲 0.0〜8.0） | `0` | 同時ラグドール数 / 既定8。0=ラグドールなし | [E] |
| `g_ragdoll_fadespeed` | `600` | `10000` | ラグドールのフェード速度 / 既定600。10000=ほぼ即消滅。0はメモリリークの恐れ | [E] |
| `g_ragdoll_lvfadespeed` | `100` | `10000` | 低暴力モードのフェード速度 / 既定100。10000=即消滅 | [E] |

### アニメ

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_anim_detail_dist` | `1500` | `1` | 詳細アニメを使う距離 / 既定1500。1=ほぼ常に簡易アニメ | [E] |
| `cl_anim_face_dist` | `250` | `1` | 表情アニメの距離 / 既定250。1=表情を切る | [E] |

### 音

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `sound_without_focus` | `` | `1` | 非フォーカス時も音を鳴らす / 1=鳴らす | [E?] |
| `miles_channels` | `0` | `2` | 音声エンジンへ渡すチャンネル数 / 既定0(=自動)。2=ステレオ固定 | [E] |
| `sound_num_speakers` | `2` | `2` | スピーカー数 / 既定2。6/8=5.1/7.1(読み手0=効果不明) | [-] |
| `miles_occlusion` | `` | `0` | 壁越しの音の遮蔽 / 0=遮蔽なし(軽い) | [E?] |
| `miles_occlusion_force` | `-1` | `0` | 音の遮蔽処理の強制値 / 既定-1(自動)。0=遮蔽なし | [E] |
| `miles_occlusion_partial` | `` | `0` | 部分遮蔽 / 0=なし | [E?] |
| `cl_footstep_event_max_dist` | `4000` | `5000` | 足音イベントの最大距離 / 既定4000。5000=遠くの足音も鳴らす(元リスト)※大きくすると負荷増 | [E] |
| `rope_wind_dist` | `1000` | `4000` | ロープ/ジップの風切り音距離 / 既定1000。4000=遠くまで鳴る(元リスト) | [E] |
| `sound_musicReduced` | `0` | `0` | 音楽を減らす(スクリプト値) / 0(既定) | [E] |
| `sound_volume_music_game` | `1` | `0.000000` | ゲーム中の音楽音量 / 既定1。0=無音 | [E] |
| `sound_volume_music_lobby` | `1` | `0.000000` | ロビーの音楽音量 / 既定1。0=無音 | [E] |

### HUD

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `player_setting_damage_closes_deathbox_menu` | `1` | `0` | 被弾でデスボックスが閉じる / 既定1。0=閉じない | [S] |
| `hud_setting_minimapRotate` | `0` | `1` | ミニマップを視点に合わせて回転 / 既定0。1=回転する | [S] |
| `hud_setting_pingDoubleTapEnemy` | `1` | `1` | ダブルタップで敵ピン / 既定1 | [S] |
| `hud_setting_adsDof` | `1` | `0` | ADS中の被写界深度(ボケ) / 既定1。0=ボケなし | [S] |
| `hud_setting_pingAlpha` | `1.0` | `0.300000` | ピンの表示不透明度 / 既定1.0。0.3=薄くする | [S] |
| `hud_setting_damageTextStyle` | `1` | `1` | ダメージ数字の表示形式 / 既定1。0=オフ/1=積算/2=浮遊/3=両方 | [S] |

### UI

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `localClientPlayerCachedLevel` | `1` | `25` | ランクキュー時のレベル表示キャッシュ / 既定1。25で「味方からLv1に見える」不具合回避(元リスト) | [E] |

### 処理

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_SetupAllBones` | `0` | `0` | 全ボーンを毎フレーム設定(重い) / 0=無効(既定) | [-] |
| `cl_threaded_bone_setup` | `1` | `1` | ボーンセットアップを別スレッド化 / 1=有効(既定) | [E] |
| `r_threaded_particles` | `1` | `1` | パーティクルを並列処理 / 1=有効(既定) | [E] |
| `cl_phys_maxticks` | `3` | `0` | 物理の最大tick数 / 0で物理更新を抑制 | [E] |
| `r_norefresh` | `0` | `1` | 不要なフレーム時間変数の更新を止める / 1でわずかに軽くなる(読み手0=効果不明) | [-] |

### ネット

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_predictweapons` | `1` | `1` | 武器を予測(スクリプト値) / 1(既定/推奨) | [-] |
| `cl_smooth` | `1` | `0` | 予測誤差の見た目を平滑化 / 1(既定)。0=平滑化オフ(元リストは0と1を併記=後勝ちの1) | [E] |
| `cl_resend` | `0.5`（範囲 0.5〜20.0） | `4` | パケット再送までの秒数 / 0.5(既定)が最速。4にすると再送が遅くなる=パケロス時により待つ | [E] |
| `cl_cmdbackup` | `2` | `2` | パケロス対策のバックアップコマンド数 / 2(既定)。上げると通信量増 | [E] |
| `cl_lagcompensation` | `1` | `1` | ラグ補正(サーバー側) / 1(既定)。クライアントからは実質変更不可 | [-] |
| `cl_smooth` | `1` | `1` | 予測誤差の見た目を平滑化 / 1(既定)。0=平滑化オフ(元リストは0と1を併記=後勝ちの1) | [E] |
| `cl_smoothtime` | `0.25`（範囲 0.009999999776482582〜2.0） | `0.01` | 平滑化の時間 / 既定0.25。0.01でほぼ無効 | [E] |
| `projectile_prediction` | `1` | `1` | 弾のクライアント予測 / 1(既定) | [E] |
| `projectile_predictionErrorCorrectTime` | `0.3` | `0.1` | 予測誤差の修正時間 / 既定0.3。0.1で修正を速く | [E] |
| `cl_matchmaking_timeout` | `1`（範囲 0.5〜20000.0） | `100` | マッチングのタイムアウト(秒) / 既定1。100でタイムアウトしにくくなる(元リスト通り) | [E] |
| `cl_ranked_reconnect_timeout` | `15`（範囲 0.5〜20000.0） | `300` | ランクの再接続猶予(秒) / 既定15。300で猶予を伸ばす | [E] |
| `net_maxcleartime` | `4.0` | `0.020346` | 送信を待つ最大時間 / 既定4.0。小さいほど送信が早いが帯域使用増(読み手あり) | [E] |
| `host_limitlocal` | `0` | `0` | ローカルホスト時の制限 / 0(既定) | [E] |
| `cl_pred_optimize` | `1` | `1` | 予測の最適化 / 1(既定) | [E] |
| `match_updateRate` | `30` | `60` | 更新レート関連(読み手0) / 既定30。効果不明 | [-] |
| `cl_updaterate_mp` | `20` | `60` | サーバーからの更新頻度(USERINFO) / 既定20。上げてもApex側でクランプされる可能性が高い | [E] |

### テレメトリ

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `telemetry_client_enable` | `1` | `0` | クライアントテレメトリ送信 / 0=停止 | [E] |
| `telemetry_client_sendInterval` | `10.0` | `0` | 送信間隔(秒) / 0=送らない | [E] |
| `pin_opt_in` | `1` | `0` | PIN(EA調査)へのオプトイン / 0=拒否 | [E] |
| `pin_plat_id` | `0` | `0` | プラットフォームID送信 / 0=送らない(既定0) | [E] |

### 周辺機器

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `chroma_enable` | `1` | `0` | Razer Chroma等のライト反応 / 既定1。0=切る(読み手0) | [-] |

### デバッグ

| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |
|---|---|---|---|---|
| `cl_showfiredbullets` | `0` | `0` | 弾のデバッグ表示 / 0(既定) | [-] |
| `net_netGraph2` | `0` | `1` | ネットグラフ表示(スクリプト値) / 既定0。1=表示 | [S] |

## 抜けていた候補（このビルドに実在・旧リスト未収録）

| cvar | 既定 | 意味 / 使いどころ |
|---|---|---|
| `cl_use_raw_input_buffer` | `1` | 生入力バッファを使う(現行の raw input 経路。旧 m_rawinput の置き換え) |
| `raw_input_deadzone` | `1024` | 生入力のデッドゾーン。既定のまま推奨 |
| `fps_max_use_refresh` | `0` | fps_max の代わりにリフレッシュレートを使う(0=使わない) |
| `fps_max_vsync` | `0` | VSync時のフレーム上限の扱い |
| `fps_absolute_max` | `300.0` | 上限の絶対値 |
| `cl_precache_use_pso_threads` | `1` | PSO(パイプライン)キャッシュをスレッドで処理 |
| `cl_parallelParticlePreDrawWork` | `1` | パーティクル描画前処理の並列化 |
| `cl_parallel_clientside_animations` | `1` | クライアントアニメの並列化 |
| `cl_async_bone_setup` | `1` | ボーンセットアップの非同期化 |
| `hud_setting_showEnemyHealthBar` | `1` | クロスヘア下の敵HPバー |
| `hud_setting_showEnemyHighlight` | `1` | 敵ハイライト表示 |
| `hud_setting_compactOverHeadNames` | `0` | 頭上ネームプレートを小さく |
| `hud_setting_showCallsigns` | `1` | コールサイン表示 |
| `hud_setting_showButtonHints` | `1` | ボタンヒント表示 |
| `hud_setting_showHopUpPopUp` | `1` | ホップアップ通知 |
| `hud_setting_showLevelUp` | `1` | レベルアップ通知 |
| `hud_setting_showMeter` | `1` | メーター表示 |
| `hud_setting_accessibleChat` | `0` | アクセシブルチャット |
| `hud_setting_chainHeal` | `1` | 連続回復の表示 |
| `hud_setting_damageIndicatorStyle` | `2` | 被弾方向表示の形式(0=オフ/1=X/2=シールド付きX) |
| `damage_indicator_style_pilot` | `2` | 被弾表示の形式(元リストの damage_indicator_style_pilot と同系統) |
| `colorblind_mode` | `0` | 色覚モード(0=通常) |
| `player_setting_holdtosprint` | `0` | ホールドでスプリント |
| `player_setting_stickysprintforward` | `0` | 前進時にスプリント継続 |
| `weapon_setting_autocycle_on_empty` | `1` | 弾切れで自動武器切替 |
| `cl_prevent_weapon_text_hints` | `1` | 武器のヒントテキストを抑制 |
| `cl_particle_batch_mode` | `1` | パーティクルをバッチ描画 |
| `cl_viewmodel_pre_animate` | `0` | ビューモデルの先行アニメ |
| `csm_enabled` | `1` | カスケード影(全体ON/OFF) |
| `csm_coverage` | `2` | 影のカバー範囲 |
| `csm_cascade_res` | `1024` | 影カスケードの解像度 |
| `viewmodel_selfshadow_enabled` | `1` | 武器の自己影(新名) |
| `miles_output_device` | `(ゲームが書く)` | 音声出力デバイス。ゲーム内設定で選ぶのが正 |
| `miles_cache_size` | `32` | 音声キャッシュ(MB) |
| `miles_driver_mix_mode` | `0` | 音声ミックスの方式 |
| `miles_bankpaging` | `1` | 音声バンクのページング |
| `fx_sound_oneshot_max_radius` | `15000` | 単発効果音の最大距離 |
| `dof_enable` | `1` | 被写界深度(全体) |
| `dof_variable_blur` | `0` | 距離に応じた可変ボケ |
| `shadow_depth_upres_factor_max` | `3` | 影の深度解像度の上限 |
| `setting.ssao_downsample` | `0` | VIDEOCONFIG のキー(cvarではない)。videoconfig.txt に書く |

## 効果不明・消してよい候補（`[-]`）

登録はされているがネイティブの読み手が見つからなかったもの。値を書いても何も起きない可能性が高い
（ただし「値ポインタが初期化時に他所へコピーされる型」は静的には拾えないので、断定はしない）:
`cl_SetupAllBones` `cl_showfiredbullets` `sidearmSwapSelectDoubleTapTime` `chroma_enable`
`mat_colcorrection_disableentities` `sound_num_speakers` `cl_particle_fallback_base`
`cl_particle_fallback_multiplier` `r_norefresh` `cl_lagcompensation` `match_updateRate` `cl_predictweapons`

## 旧リストの死に項目（再追加しないこと）

`absent` = このビルドに名前が存在しない / `string-only` = 文字列だけ残っている /
`cheat` = `FCVAR_CHEAT`（MP では `sv_cheats` が必要） / `videoconfig-key` = videoconfig.txt 側のキー。
一覧は `autoexec.cfg` の末尾に全部書いてある（代替名は `evidence/audit3/equivalents.tsv`）。

代表的な置き換え:

| 旧名 | いまの名前 |
|---|---|
| `m_rawinput` | `cl_use_raw_input_buffer` / `raw_input_deadzone` |
| `mat_antialias` | `mat_antialias_mode`（videoconfig `setting.mat_antialias_mode`） |
| `cl_interp` | `cl_interpolate` / `cl_interpolation_before_prediction` |
| `cl_bones_incremental_blend` | `cl_bones_incremental_transform` |
| `r_shadows` `mat_shadowstate` `r_shadowmaxrendered` | `csm_*` と videoconfig `setting.shadow_*` |
| `mat_depthfeather_enable` | `dof_*` / `hud_setting_adsDof` |
| `cl_detailfade` `cl_detaildist` | `cl_anim_detail_dist` / `cl_anim_face_dist` / `r_lod_switch_scale` |
| `cl_phys_props_enable` `cl_phys_props_max` | `max_props` / `sv_max_props_*` / `props_break_max_pieces*` |
| `ssao_downsample` | videoconfig の `setting.ssao_downsample` |
| `snd_setmixer` `snd_mixahead` `snd_musicvolume` `cl_cmdrate` `cl_timeout` `net_compresspackets` `mat_queue_mode` `cl_ejectbrass` `rope_*` ほか | 代替なし（削除済み） |

---

解析の詳細・生データ: `G:\apex-analysis\notes\cfg-audit.md` と `evidence/audit3/`。
判定は「存在するか（登録スタブ）」「読まれるか（ハンドル参照）」「既定値/範囲/flags」まで。
**値の因果（FPS が何%上がる等）は測っていない**ので、そこは各自で A/B してほしい。
