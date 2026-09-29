#!/usr/bin/env python
"""Generate the annotated, hand-editable autoexec.cfg + CVAR-GUIDE.md.

Data comes from the audit (which cvars exist in THIS build, their build default,
their flags and whether native code reads them).  The Japanese annotation dict
below says what each knob does and what a sane value is.

Usage: python mk_documented_cfg.py <fields.tsv> <audit.tsv> <cand.tsv> <outdir>
"""
import sys, os, re

# name -> (section, what it does, value advice)
ANNOT = {
 # ---------------- 入力 / マウス ----------------
 'm_acceleration': ('入力', 'マウス加速。0=加速なし', '0=無効(推奨)。実行時は感度計算側でも参照される'),
 'fps_max': ('フレーム', '最大FPS。既定-1=無制限', 'モニタHz-1 が定番 (144Hz→143)。※起動オプション +fps_max 0 を付けるとそちらが後勝ち'),
 # ---------------- フレーム / 処理 ----------------
 'cl_threaded_bone_setup': ('処理', 'ボーンセットアップを別スレッド化', '1=有効(既定)'),
 'r_threaded_particles': ('処理', 'パーティクルを並列処理', '1=有効(既定)'),
 'cl_SetupAllBones': ('処理', '全ボーンを毎フレーム設定(重い)', '0=無効(既定)'),
 'r_norefresh': ('処理', '不要なフレーム時間変数の更新を止める', '1でわずかに軽くなる(読み手0=効果不明)'),
 'cl_phys_maxticks': ('処理', '物理の最大tick数', '0で物理更新を抑制'),
 # ---------------- ネットワーク / 予測 ----------------
 'cl_pred_optimize': ('ネット', '予測の最適化', '1(既定)'),
 'cl_predictweapons': ('ネット', '武器を予測(スクリプト値)', '1(既定/推奨)'),
 'cl_lagcompensation': ('ネット', 'ラグ補正(サーバー側)', '1(既定)。クライアントからは実質変更不可'),
 'cl_cmdbackup': ('ネット', 'パケロス対策のバックアップコマンド数', '2(既定)。上げると通信量増'),
 'cl_resend': ('ネット', 'パケット再送までの秒数', '0.5(既定)が最速。4にすると再送が遅くなる=パケロス時により待つ'),
 'net_maxcleartime': ('ネット', '送信を待つ最大時間', '既定4.0。小さいほど送信が早いが帯域使用増(読み手あり)'),
 'cl_updaterate_mp': ('ネット', 'サーバーからの更新頻度(USERINFO)', '既定20。上げてもApex側でクランプされる可能性が高い'),
 'match_updateRate': ('ネット', '更新レート関連(読み手0)', '既定30。効果不明'),
 'host_limitlocal': ('ネット', 'ローカルホスト時の制限', '0(既定)'),
 'cl_matchmaking_timeout': ('ネット', 'マッチングのタイムアウト(秒)', '既定1。100でタイムアウトしにくくなる(元リスト通り)'),
 'cl_ranked_reconnect_timeout': ('ネット', 'ランクの再接続猶予(秒)', '既定15。300で猶予を伸ばす'),
 'projectile_prediction': ('ネット', '弾のクライアント予測', '1(既定)'),
 'projectile_predictionErrorCorrectTime': ('ネット', '予測誤差の修正時間', '既定0.3。0.1で修正を速く'),
 'cl_smooth': ('ネット', '予測誤差の見た目を平滑化', '1(既定)。0=平滑化オフ(元リストは0と1を併記=後勝ちの1)'),
 'cl_smoothtime': ('ネット', '平滑化の時間', '既定0.25。0.01でほぼ無効'),
 # ---------------- テレメトリ / プライバシー ----------------
 'telemetry_client_enable': ('テレメトリ', 'クライアントテレメトリ送信', '0=停止'),
 'telemetry_client_sendInterval': ('テレメトリ', '送信間隔(秒)', '0=送らない'),
 'pin_opt_in': ('テレメトリ', 'PIN(EA調査)へのオプトイン', '0=拒否'),
 'pin_plat_id': ('テレメトリ', 'プラットフォームID送信', '0=送らない(既定0)'),
 # ---------------- FOV / 視点 ----------------
 'cl_fovScale': ('FOV', 'FOVスケール(USERINFOでサーバーにも送信)', '既定1.27216005 = 90FOV。1.55=110FOV。※必ずゲーム内設定と一致させる、不一致は挙動が乱れる'),
 'sprint_view_shake_style': ('視点', 'スプリント時の画面揺れ', '既定0。1で揺れを軽減(元リスト)'),
 'viewmodelShake': ('視点', '武器の揺れ(ビューモデル)', '既定1。0=揺れなし'),
 'viewmodelShake_sourceRollRange': ('視点', '同 揺れ量', '既定3。0=なし'),
 'viewmodel_selfshadow': ('視点', '武器の自己影', '既定1。0=影を落とさない'),
 'cl_idealpitchscale': ('視点', '理想ピッチのスケール', '0(既定)'),
 'slide_viewTiltSide': ('視点', 'スライド時の画面傾き(度)', '既定15。0=傾けない'),
 'cl_showpos': ('視点', '座標/速度表示', '0=非表示(既定)'),
 # ---------------- 描画 (LOD/テクスチャ) ----------------
 'r_lod_switch_scale': ('描画', 'LOD切替距離(1=標準)', '既定1。0.3=遠くを早く低ポリ化=FPS↑/見た目↓'),
 'mat_picmip': ('描画', 'テクスチャ解像度(大きいほど粗い)', '既定0。4=最粗(元リスト)'),
 'stream_memory': ('描画', 'テクスチャのストリーミング予算(バイト)', '既定298000。0=最小(荒い)/GPUのVRAMに応じ 1000000〜3000000'),
 'mat_forceaniso': ('描画', '異方性フィルタ', '既定2。0=切る'),
 'mat_mip_linear': ('描画', 'ミップの線形フィルタ', '既定1。0=切る(チラつくが見た目は軽い)'),
 'mat_filtertextures': ('描画', 'テクスチャフィルタ', '既定1。0=切る(粗く表示)'),
 'mat_diffuse': ('描画', '拡散照明の扱い', '1(既定)。0でプラスチック的な見た目'),
 'cl_decal_alwayswhite': ('描画', 'デカールを常に白で描く', '1(既定)'),
 'mat_autoexposure_min': ('明るさ', '自動露出の最小値', '既定0.5。1.5で下限を明るく(暗所が見える/白飛びしやすい)'),
 'mat_autoexposure_max': ('明るさ', '自動露出の最大値', '既定3。1.5で上限を下げる(白飛び抑制)'),
 'mat_autoexposure_speed': ('明るさ', '露出が変わる速さ', '既定0.1。1.5で素早く(屋内⇄屋外の切替が速い)'),
 'mat_autoexposure_min_multiplier': ('明るさ', '露出最小の倍率', '既定1.0'),
 'mat_autoexposure_max_multiplier': ('明るさ', '露出最大の倍率', '既定1.0'),
 'mat_hide_sun_in_last_cascade': ('描画', '遠景カスケードの太陽を隠す', '既定0。1=遠くの光源グレアを消す'),
 'mat_screen_blur_enabled': ('描画', '画面ブラー(被弾/ダッシュ等)', '既定1。0=ブラーなし'),
 # ---------------- シャドウ / SSAO ----------------
 'static_shadow': ('影', '静的な影の解像度/段(0=切)', '既定3。0=静的影を描かない'),
 'tweak_light_shadows_every_frame': ('影', '毎フレーム影を更新', '0=切(既定)'),
 'vsm_ignore_face_planes': ('影', 'VSMの面カリング', '1=面を無視(元リスト)'),
 'ssao_enabled': ('SSAO', '環境遮蔽', '既定1。0=切る(FPS↑/陰影が薄くなる)'),
 'ssao_blur': ('SSAO', 'SSAOのブラー', '既定1。0=切る'),
 # ---------------- パーティクル/エフェクト ----------------
 'cl_aggregate_particles': ('エフェクト', 'パーティクルのまとめ描画', '1(既定)'),
 'r_particle_timescale': ('エフェクト', 'パーティクルの時間倍率', '既定1.0。3=速く消える(元リスト)'),
 'cl_cull_weapon_fx': ('エフェクト', '武器エフェクトのカリング', '既定1。0=カリングしない'),
 'cl_show_splashes': ('エフェクト', '水しぶき', '既定1。0=切る'),
 'cl_drawmonitors': ('エフェクト', 'ゲーム内モニタの描画', '既定1。0=切る'),
 'projectile_muzzleOffsetFirstPersonDecayMaxTime': ('エフェクト', '自分視点の弾の軌跡フェード時間', '既定0.3。0=即消し(元リスト)'),
 'projectile_muzzleOffsetFirstPersonDecayDist': ('エフェクト', '同 距離', '既定1000。0=即消し'),
 'bink_materials_enabled': ('エフェクト', 'Bink動画マテリアル(ロビー等)', '既定1。0=動画マテリアルを使わない'),
 # ---------------- 血/ラグドール ----------------
 'violence_ablood': ('暴力表現', '血のエフェクト', '既定1。0=血なし'),
 'violence_agibs': ('暴力表現', 'ギブス', '既定1。0=なし'),
 'violence_hblood': ('暴力表現', '人間の血', '既定1。0=なし'),
 'violence_hgibs': ('暴力表現', '人間のギブス', '既定1。0=なし'),
 'cl_ragdoll_maxcount': ('ラグドール', '同時ラグドール数', '既定8。0=ラグドールなし'),
 'cl_ragdoll_force_fade_time': ('ラグドール', 'ラグドールの消滅までの時間', '既定5。0=即消し'),
 'cl_ragdoll_force_fade_time_local_view_player': ('ラグドール', '自プレイヤー視点での消滅時間', '既定20'),
 'cl_ragdoll_force_fade_time_on_moving_geo': ('ラグドール', '動く地形上の消滅時間', '既定5'),
 'cl_ragdoll_self_collision': ('ラグドール', 'ラグドール同士の衝突', '既定1。0=計算を切る'),
 'cl_always_ragdoll_radius': ('ラグドール', '常にラグドール化する半径', '既定500。0=常時ラグドールをやめる'),
 'g_ragdoll_fadespeed': ('ラグドール', 'ラグドールのフェード速度', '既定600。10000=ほぼ即消滅。0はメモリリークの恐れ'),
 'g_ragdoll_lvfadespeed': ('ラグドール', '低暴力モードのフェード速度', '既定100。10000=即消滅'),
 # ---------------- アニメーション詳細 ----------------
 'cl_anim_detail_dist': ('アニメ', '詳細アニメを使う距離', '既定1500。1=ほぼ常に簡易アニメ'),
 'cl_anim_face_dist': ('アニメ', '表情アニメの距離', '既定250。1=表情を切る'),
 # ---------------- 音 ----------------
 'miles_channels': ('音', '音声エンジンへ渡すチャンネル数', '既定0(=自動)。2=ステレオ固定'),
 'sound_num_speakers': ('音', 'スピーカー数', '既定2。6/8=5.1/7.1(読み手0=効果不明)'),
 'miles_occlusion_force': ('音', '音の遮蔽処理の強制値', '既定-1(自動)。0=遮蔽なし'),
 'miles_occlusion': ('音', '壁越しの音の遮蔽', '0=遮蔽なし(軽い)'),
 'miles_occlusion_partial': ('音', '部分遮蔽', '0=なし'),
 'cl_footstep_event_max_dist': ('音', '足音イベントの最大距離', '既定4000。5000=遠くの足音も鳴らす(元リスト)※大きくすると負荷増'),
 'rope_wind_dist': ('音', 'ロープ/ジップの風切り音距離', '既定1000。4000=遠くまで鳴る(元リスト)'),
 'sound_musicReduced': ('音', '音楽を減らす(スクリプト値)', '0(既定)'),
 'sound_volume_music_game': ('音', 'ゲーム中の音楽音量', '既定1。0=無音'),
 'sound_volume_music_lobby': ('音', 'ロビーの音楽音量', '既定1。0=無音'),
 'sound_without_focus': ('音', '非フォーカス時も音を鳴らす', '1=鳴らす'),
 # ---------------- HUD / UI ----------------
 'hud_setting_minimapRotate': ('HUD', 'ミニマップを視点に合わせて回転', '既定0。1=回転する'),
 'hud_setting_pingDoubleTapEnemy': ('HUD', 'ダブルタップで敵ピン', '既定1'),
 'hud_setting_adsDof': ('HUD', 'ADS中の被写界深度(ボケ)', '既定1。0=ボケなし'),
 'hud_setting_pingAlpha': ('HUD', 'ピンの表示不透明度', '既定1.0。0.3=薄くする'),
 'hud_setting_damageTextStyle': ('HUD', 'ダメージ数字の表示形式', '既定1。0=オフ/1=積算/2=浮遊/3=両方'),
 'player_setting_damage_closes_deathbox_menu': ('HUD', '被弾でデスボックスが閉じる', '既定1。0=閉じない'),
 'player_setting_autosprint': ('操作', 'オートスプリント', '既定0。1=常時スプリント'),
 'localClientPlayerCachedLevel': ('UI', 'ランクキュー時のレベル表示キャッシュ', '既定1。25で「味方からLv1に見える」不具合回避(元リスト)'),
 'noise_filter_scale': ('描画', 'フィルムグレイン量(スクリプト値)', '既定0.006。0=グレインなし'),
 'chroma_enable': ('周辺機器', 'Razer Chroma等のライト反応', '既定1。0=切る(読み手0)'),
 # ---------------- デバッグ表示 ----------------
 'net_netGraph2': ('デバッグ', 'ネットグラフ表示(スクリプト値)', '既定0。1=表示'),
 'cl_showfiredbullets': ('デバッグ', '弾のデバッグ表示', '0(既定)'),
 # ---------------- その他(読み手0=効果不明) ----------------
 'cl_particle_fallback_base': ('エフェクト', '負荷時に安いエフェクトへ落とす基準', '既定0。読み手が見つからず効果不明'),
 'cl_particle_fallback_multiplier': ('エフェクト', '同 倍率', '既定1。読み手が見つからず効果不明'),
 'sidearmSwapSelectDoubleTapTime': ('操作', 'ダブルタップでの武器切替時間', '既定0.25。読み手0'),
 'ordnanceSwapSelectCooldown': ('操作', 'グレネード選択のクールダウン(秒)', '既定0.25。0=即時切替'),
 'sidearmSwapSelectCooldown': ('操作', '武器切替のクールダウン(秒)', '既定0.25。0=即時切替'),
 'fov_disableAbilityScaling': ('FOV', 'アビリティ使用時のFOV変化を無効化', '1=無効化(元リスト)。ゲーム自身が profile.cfg に書く名前'),
 'tsaa_blendfactoroverride': ('描画', 'TSAAブレンド係数の上書き', '既定-1=上書きなし。1=上書きする(元リスト)'),
 'tsaa_curframeblendamount': ('描画', 'TSAAの現フレームブレンド量', '既定0.05。小さいほどゴースト減/ノイズ増'),
 'tsaa_numsamples': ('描画', 'TSAAのサンプル数', '既定64。4=軽い(元リスト)'),
 'fog_enable': ('描画', 'フォグ(霧)', '既定1。0=霧を切る(遠くが見える/演出は消える)'),
 'fog_enableskybox': ('描画', '空にかかるフォグ', '既定1。1=空にも霧(元リストのままだと有効)'),
 'mat_colcorrection_disableentities': ('描画', 'エンティティへの色補正を無効化', '既定0。1=モデルに色補正を掛けない(読み手0)'),
 'rope_shake': ('エフェクト', 'ロープ(ジップライン)の揺れ', '既定0'),
 'rope_collide': ('エフェクト', 'ロープの衝突判定', '既定1。0=判定を切る(軽い)'),
 'cl_gib_allow': ('暴力表現', 'ギブス(破片)の発生', '既定1。0=なし'),
 'props_break_max_pieces': ('エフェクト', '破壊可能オブジェクトの破片数', '既定-1。0=破片を出さない'),
 'stream_cache_high_priority_static_models': ('描画', '静的モデルをキャッシュ優先で読む', '1=優先ロード'),
 'stream_cache_preload_from_rpak': ('描画', 'pakから事前ロード', '1(既定)'),
 'stream_drop_unused': ('描画', '未使用テクスチャを積極的に解放', '既定0。1=解放(VRAM節約/再読込のヒッチの可能性)'),
 'sound_cache_settings': ('音', '', ''),
}

SECTION_ORDER = ['入力', '操作', '視点', 'FOV', 'フレーム', '描画', '明るさ', '影', 'SSAO',
                 'エフェクト', '暴力表現', 'ラグドール', 'アニメ', '音', 'HUD', 'UI',
                 '処理', 'ネット', 'テレメトリ', '周辺機器', 'デバッグ']

# name, default(reference), advice
CAND = [
 ('cl_use_raw_input_buffer', '1', '生入力バッファを使う(現行の raw input 経路。旧 m_rawinput の置き換え)'),
 ('raw_input_deadzone', '1024', '生入力のデッドゾーン。既定のまま推奨'),
 ('fps_max_use_refresh', '0', 'fps_max の代わりにリフレッシュレートを使う(0=使わない)'),
 ('fps_max_vsync', '0', 'VSync時のフレーム上限の扱い'),
 ('fps_absolute_max', '300.0', '上限の絶対値'),
 ('cl_precache_use_pso_threads', '1', 'PSO(パイプライン)キャッシュをスレッドで処理'),
 ('cl_parallelParticlePreDrawWork', '1', 'パーティクル描画前処理の並列化'),
 ('cl_parallel_clientside_animations', '1', 'クライアントアニメの並列化'),
 ('cl_async_bone_setup', '1', 'ボーンセットアップの非同期化'),
 ('hud_setting_showEnemyHealthBar', '1', 'クロスヘア下の敵HPバー'),
 ('hud_setting_showEnemyHighlight', '1', '敵ハイライト表示'),
 ('hud_setting_compactOverHeadNames', '0', '頭上ネームプレートを小さく'),
 ('hud_setting_showCallsigns', '1', 'コールサイン表示'),
 ('hud_setting_showButtonHints', '1', 'ボタンヒント表示'),
 ('hud_setting_showHopUpPopUp', '1', 'ホップアップ通知'),
 ('hud_setting_showLevelUp', '1', 'レベルアップ通知'),
 ('hud_setting_showMeter', '1', 'メーター表示'),
 ('hud_setting_accessibleChat', '0', 'アクセシブルチャット'),
 ('hud_setting_chainHeal', '1', '連続回復の表示'),
 ('hud_setting_damageIndicatorStyle', '2', '被弾方向表示の形式(0=オフ/1=X/2=シールド付きX)'),
 ('damage_indicator_style_pilot', '2', '被弾表示の形式(元リストの damage_indicator_style_pilot と同系統)'),
 ('colorblind_mode', '0', '色覚モード(0=通常)'),
 ('player_setting_holdtosprint', '0', 'ホールドでスプリント'),
 ('player_setting_stickysprintforward', '0', '前進時にスプリント継続'),
 ('weapon_setting_autocycle_on_empty', '1', '弾切れで自動武器切替'),
 ('cl_prevent_weapon_text_hints', '1', '武器のヒントテキストを抑制'),
 ('cl_particle_batch_mode', '1', 'パーティクルをバッチ描画'),
 ('cl_viewmodel_pre_animate', '0', 'ビューモデルの先行アニメ'),
 ('csm_enabled', '1', 'カスケード影(全体ON/OFF)'),
 ('csm_coverage', '2', '影のカバー範囲'),
 ('csm_cascade_res', '1024', '影カスケードの解像度'),
 ('viewmodel_selfshadow_enabled', '1', '武器の自己影(新名)'),
 ('miles_output_device', '(ゲームが書く)', '音声出力デバイス。ゲーム内設定で選ぶのが正'),
 ('miles_cache_size', '32', '音声キャッシュ(MB)'),
 ('miles_driver_mix_mode', '0', '音声ミックスの方式'),
 ('miles_bankpaging', '1', '音声バンクのページング'),
 ('fx_sound_oneshot_max_radius', '15000', '単発効果音の最大距離'),
 ('dof_enable', '1', '被写界深度(全体)'),
 ('dof_variable_blur', '0', '距離に応じた可変ボケ'),
 ('shadow_depth_upres_factor_max', '3', '影の深度解像度の上限'),
 ('setting.ssao_downsample', '0', 'VIDEOCONFIG のキー(cvarではない)。videoconfig.txt に書く'),
]

GUIDE_HEAD = """# CVAR-GUIDE — Apex Legends v3.0.1.28 で「効く」autoexec の中身

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
"""

GUIDE_TAIL = """
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

解析の詳細・生データ: `notes\\cfg-audit.md` と `evidence/audit3/`。
判定は「存在するか（登録スタブ）」「読まれるか（ハンドル参照）」「既定値/範囲/flags」まで。
**値の因果（FPS が何%上がる等）は測っていない**ので、そこは各自で A/B してほしい。
"""

HDR = """// ============================================================================
//  autoexec.cfg  —  Apex Legends v3.0.1.28 (build R5pc_r5-301_J28_CL11570498)
//  r5apex_dx12.exe sha256 8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825
//
//  このファイルは「この exe に実在し、コードが実際に読んでいる cvar」だけで作ってある。
//  各行の [E] は根拠:
//    [E]  = 登録スタブ＋ネイティブの読み手あり(実測)      … 効く
//    [S]  = SCRIPTS_ONLY。UI/スクリプト側が読む(メニュー設定と同等)
//    [E?] = 登録はあるが記述子の自動抽出に載らなかった(ゲーム自身がcfgに書く名前を含む)
//    [-]  = 登録はあるがネイティブの読み手が見つからない   … 効果不明(消してよい)
//  「既定=X」はこのビルドの既定値。同じ値なら実質そのまま。
//
//  置き場所: r5apex_dx12.exe と同じフォルダ (C:\\Program Files\\EA Games\\Apex\\)
//  起動オプション: +exec autoexec.cfg
//  ※ 起動オプションは左から順に実行されるので、後ろに +fps_max 0 を書くと
//     このファイルの fps_max は上書きされる(README の並びはこれに当たる)
//  ※ 一度ゲームを終了させてから編集すること。起動中に書くと終了時に上書きされる
// ============================================================================
"""


def fnum(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def main():
    fields_p, audit_p, cand_p, outdir = sys.argv[1:5]
    fields = {}
    for l in open(fields_p, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        c = l.rstrip('\n').split('\t')
        fields[c[0]] = c
    rows = []
    for l in open(audit_p, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        rows.append(l.rstrip('\n').split('\t'))
    live = [r for r in rows if r[3].startswith('registered')]
    dead = [r for r in rows if not r[3].startswith('registered') and r[1]]

    def is_float(s):
        return bool(re.match(r'^-?\d+\.\d+', s or ''))

    sec = {}
    used = set()
    for r in live:
        name, val, verdict = r[1], r[2], r[3]
        ann = ANNOT.get(name)
        section = ann[0] if ann and ann[0] in SECTION_ORDER else 'その他'
        f = fields.get(name)
        default = f[5] if f else ''
        minv = f[7] if f and len(f) > 7 else ''
        maxv = f[8] if f and len(f) > 8 else ''
        tags = {'registered': '[E]', 'registered-scriptread': '[S]',
                'registered-noread': '[-]', 'registered-unverified': '[E?]'}[verdict]
        bits = []
        if ann and ann[1]:
            bits.append(ann[1])
        if ann and ann[2]:
            bits.append('推奨: ' + ann[2])
        meta = f'既定={default}' if default else ''
        if fnum(minv) != 0.0 or fnum(maxv) != 0.0:
            meta += f' 範囲={minv}〜{maxv}'
        if val and default and val.strip('.0') == default.strip('.0'):
            meta += ' ※既定と同値'
        if not ann or not ann[1]:
            bits.append('(説明未整理・登録と読み手のみ確認)')
        comment = ' | '.join(bits)
        sec.setdefault(section, []).append((name, val, tags, meta, comment))
        used.add(name)

    order = [s for s in SECTION_ORDER if s in sec] + (['未分類'] if 'その他' in sec else [])
    if 'その他' in sec:
        sec['未分類'] = sec.pop('その他')
    if sec.get('未分類'):
        print('unclassified:', [n for n, *_ in sec['未分類']])
    os.makedirs(outdir, exist_ok=True)
    cfg = os.path.join(outdir, 'autoexec.cfg')
    with open(cfg, 'w', encoding='utf-8') as fh:
        fh.write(HDR)
        for s in order:
            fh.write(f'\n// ---------------------------------------------------------------------------\n'
                     f'//  {s}\n'
                     f'// ---------------------------------------------------------------------------\n')
            for name, val, tag, meta, comment in sec[s]:
                fh.write(f'{name} "{val}"'.ljust(52) + f'// {tag} {comment}')
                if meta:
                    fh.write(f'   [{meta}]')
                fh.write('\n')
        fh.write('\n// ===========================================================================\n'
                 '//  以下は「旧リストにあったが、このビルドでは無効」な行（再追加しないため）\n'
                 '// ===========================================================================\n')
        for r in dead:
            name, val, verdict = r[1], r[2], r[3]
            why = {'absent': 'このビルドに名前が存在しない',
                   'string-only': '文字列だけ残っていて cvar として未登録',
                   'cheat': 'FCVAR_CHEAT：sv_cheats が必要＝MPでは効かない',
                   'videoconfig-key': 'videoconfig.txt の setting.* キー',
                   }.get(verdict, verdict)
            fh.write(f'// {name} "{val}"'.ljust(52) + f'// {why}\n')
        fh.write('\n// ===========================================================================\n'
                 '//  抜けていた候補（このビルドに実在・旧リスト未収録）\n'
                 '//  使うなら // を外して上のセクションに移す\n'
                 '// ===========================================================================\n')
        cur = None
        for name, default, advice in CAND:
            fh.write(f'// {name} "{default}"'.ljust(52) + f'// {advice}\n')
        # 追加回収分（家族/テーブル経由で登録される cvar）。ledger があれば載せる。
        ledger = os.path.join(outdir, 'cvar-ledger.tsv')
        if os.path.exists(ledger):
            fh.write('\n// ---- 追加回収分: 家族/テーブル経由で登録される設定（このビルドで実在） ----\n')
            added = set(n for n, _, _ in CAND) | set(used)
            for line in open(ledger, encoding='utf-8'):
                if line.startswith('#') or not line.strip():
                    continue
                c = line.rstrip('\n').split('\t')
                if c[7] != 'A2' or c[0] in added:
                    continue
                if c[5] == '1':      # cheat
                    continue
                fh.write(f'// {c[0]} "{c[1]}"'.ljust(52) +
                         f'// 既定={c[1] or "?"} [{c[3]}] {"読み手あり" if c[4] == "1" else "読み手なし"}\n')

    guide = os.path.join(outdir, 'CVAR-GUIDE.md')
    with open(guide, 'w', encoding='utf-8') as fh:
        fh.write(GUIDE_HEAD)
        for s in order:
            fh.write(f'\n### {s}\n\n| cvar | 既定 | このファイルの値 | 変えると / 注意 | 根拠 |\n|---|---|---|---|---|\n')
            for name, val, tag, meta, comment in sec[s]:
                default = meta.split(' ')[0].replace('既定=', '') if meta.startswith('既定=') else ''
                rng = ''
                m = re.search(r'範囲=([^ \]]+)', meta)
                if m:
                    rng = f'（範囲 {m.group(1)}）'
                note = comment.replace('推奨: ', '').replace(' | ', ' / ')
                fh.write(f'| `{name}` | `{default}`{rng} | `{val}` | {note} | {tag} |\n')
        fh.write('\n## 抜けていた候補（このビルドに実在・旧リスト未収録）\n\n'
                 '| cvar | 既定 | 意味 / 使いどころ |\n|---|---|---|\n')
        for name, default, advice in CAND:
            fh.write(f'| `{name}` | `{default}` | {advice} |\n')
        fh.write(GUIDE_TAIL)
    print('wrote', cfg, 'and', guide, 'live:', sum(len(v) for v in sec.values()), 'dead:', len(dead))
    return sec, dead


if __name__ == '__main__':
    main()
