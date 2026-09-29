# videoconfig.txt（実測ベース）— 各項目の意味と推奨値

- 正規キー: exe 内の `setting.*` 文字列 **46本**（このファイルに載せたのは 43本）
- 既定値は cvar 台帳（同名cvar・大文字小文字を無視して突合）から取得。`—` は cvar が無い（設定マネージャ側のキー）
- ★ = 推奨変更。それ以外は現行値のまま（無闇に変えない）

| key | 推奨 | 既定(cvar) | 現行 | グループ |
|---|---|---|---|---|
| `setting.last_display_width` | (現行維持) | — | 1920 | display |
| `setting.last_display_height` | (現行維持) | — | 1080 | display |
| `setting.defaultres` | (現行維持) | — | 1728 | display |
| `setting.defaultresheight` | (現行維持) | — | 1080 | display |
| `setting.fullscreen` | (現行維持) | — | 1 | display |
| `setting.nowindowborder` | (現行維持) | — | 1 | display |
| `setting.configversion` | (現行維持) | — | 10 | display |
| `setting.sound_volume` | (現行維持) | 1 | 1.000000 | audio |
| `setting.stream_memory` | 6000000 | 298000 | 300000 | visibility |
| `setting.r_lod_switch_scale` | 1.000000 | 1 | 0.600000 | visibility |
| `setting.mat_forceaniso` | 8 | 2 | 2 | visibility |
| `setting.ssao_enabled` | 0 | 1 | (無し) | visibility |
| `setting.ssao_quality` | (現行維持) | 3 | 0 | visibility |
| `setting.gamma` | (現行維持) | — | 0.700000 | visibility |
| `setting.mat_picmip` | (現行維持) | 0 | 0 | visual |
| `setting.mat_mip_linear` | (現行維持) | 1 | 1 | visual |
| `setting.mat_antialias_mode` | (現行維持) | — | 0 | visual |
| `setting.mat_vsync_mode` | (現行維持) | — | 0 | visual |
| `setting.mat_backbuffer_count` | (現行維持) | — | 1 | visual |
| `setting.fadeDistScale` | (現行維持) | — | 1.000000 | visual |
| `setting.map_detail_level` | (現行維持) | — | 1 | visual |
| `setting.new_shadow_settings` | (現行維持) | — | 1 | visual |
| `setting.dynamic_streaming_budget` | (現行維持) | — | 1 | visual |
| `setting.csm_enabled` | (現行維持) | 1 | 0 | shadow |
| `setting.csm_coverage` | (現行維持) | 2 | 1 | shadow |
| `setting.csm_cascade_res` | (現行維持) | 1024 | 512 | shadow |
| `setting.shadow_enable` | (現行維持) | 1 | 0 | shadow |
| `setting.shadow_depth_dimen_min` | (現行維持) | 192 | 0 | shadow |
| `setting.shadow_depth_upres_factor_max` | (現行維持) | 2 | 0 | shadow |
| `setting.shadow_maxdynamic` | (現行維持) | 4 | 0 | shadow |
| `setting.volumetric_lighting` | (現行維持) | — | 0 | glare |
| `setting.volumetric_fog` | (現行維持) | — | 0 | glare |
| `setting.particle_cpu_level` | (現行維持) | 0 | 0 | effects |
| `setting.cl_particle_fallback_base` | (現行維持) | 0 | 3 | effects |
| `setting.cl_particle_fallback_multiplier` | (現行維持) | 1 | 2 | effects |
| `setting.r_decals` | (現行維持) | 256 | 0 | decals |
| `setting.r_createmodeldecals` | (現行維持) | 1 | 0 | decals |
| `setting.cl_gib_allow` | (現行維持) | 1 | 0 | gore |
| `setting.cl_ragdoll_maxcount` | (現行維持) | 8 | 0 | gore |
| `setting.cl_ragdoll_self_collision` | (現行維持) | 1 | 1 | gore |
| `setting.dvs_enable` | (現行維持) | 1 | 0 | perf |
| `setting.dvs_gpuframetime_min` | (現行維持) | 15000 | 15000 | perf |
| `setting.dvs_gpuframetime_max` | (現行維持) | 16500 | 16500 | perf |

## 書かなかったキー

- `setting.cl_fovScale`: FOV。profile.cfg の cl_fovScale が正なので、ここには書かない（二重管理になると読み取り専用化した時にFOVを固定してしまう）
- `setting.set_dress_level`: exe内に文字列はあるが意味未特定・ゲームは書かない。触らない
- `setting.ssao_downsample`: AOのダウンサンプル段数。既定/範囲が静的に未確定で現行ファイルにも無いため収録しない（ssao_enabled=0なら無関係）

## 使い方（読み取り専用が前提）

1. `videoconfig.txt` を `%USERPROFILE%\Saved Games\Respawn\Apex\local\` にコピー（**ゲーム終了中に**）
2. 右クリック → プロパティ → 「読み取り専用」にチェック（または `attrib +R videoconfig.txt`）
3. ゲーム起動 → メニューの映像設定がこちらの値で固定される（メニューで変更しても保存されない）

**理由**: `videoconfig.txt` はゲーム自身が上書きするファイル。読み取り専用にしないと、次回終了時にメニューの値で書き戻され、コメントも消える。

**解除/戻し方**: `attrib -R videoconfig.txt` → ゲームを起動して映像設定を1回変更する（またはファイルを削除して起動＝既定で作り直される）。

**注意**: 読み取り専用中はメニューからの解像度/明るさ等の変更も保存されない。変えたい時は一度属性を外す。

