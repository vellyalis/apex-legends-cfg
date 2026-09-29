#!/usr/bin/env python
"""Build the complete "what can be set from autoexec" ledger + readable list.

Inputs: cvar_fields_v2.tsv (descriptors), cvar_readers_v2.tsv (native readers),
        cvar_stubs.tsv (names any small function references),
        name-only extra names (scripts/dynamic registration) passed on stdin.

Outputs: <outdir>/cvar-ledger.tsv, <outdir>/CVAR-LIST-FULL.md
"""
import os, sys, os, re, collections

FLAGS = {0x1: 'UNREGISTERED', 0x2: 'DEVELOPMENTONLY', 0x4: 'GAMEDLL', 0x8: 'CLIENTDLL',
         0x10: 'HIDDEN', 0x20: 'PROTECTED', 0x40: 'SPONLY', 0x80: 'ARCHIVE',
         0x100: 'NOTIFY', 0x200: 'USERINFO', 0x400: 'PRINTABLEONLY', 0x800: 'UNLOGGED',
         0x1000: 'NEVER_AS_STRING', 0x2000: 'REPLICATED', 0x4000: 'CHEAT',
         0x8000: 'SSCLIENT', 0x10000: 'DEMO', 0x20000: 'DONTRECORD',
         0x40000: 'NOT_CONNECTED', 0x80000: 'ARCHIVE_XBOX', 0x100000: 'ACCESSIBLE_FROM_THREADS',
         0x200000: 'NOT_LOGGED', 0x400000: 'MATERIAL_SYSTEM_THREAD',
         0x800000: 'ALLOWED_IN_MATCHMAKING', 0x1000000: 'SCRIPTS_ONLY',
         0x2000000: 'CLIENTCMD_CAN_EXECUTE', 0x4000000: 'EXEC_ONLY',
         0x8000000: 'SERVER_EXEC', 0x10000000: 'ALLOW_CONNECTED',
         0x20000000: 'ALWAYS_QUERY', 0x40000000: 'NO_MIN_MAX_CHECK'}

GROUPS = [
    ('入力/マウス・パッド', r'^(mouse_|m_|gamepad_|joystick|input_|raw_input|cl_use_raw_input|cl_mouse|aimassist_)'),
    ('HUD/UI', r'^(hud_setting_|cl_hud|cc_|ui_|clubs_|dialogue_cat_|dialogue_)'),
    ('プレイヤー設定', r'^(player_setting_|weapon_setting_|colorblind|damage_indicator|localClientPlayer)'),
    ('FOV/視点', r'^(fov|cl_fov|viewmodel|slide_|sprint_|cl_idealpitch|c_thirdperson)'),
    ('描画', r'^(mat_|r_|dof_|csm_|shadow_|ssao|tsaa|dvs_|volumetric|static_shadow|tweak_light|vsm_|fog_|stream_|cl_parallel|cl_async|cl_precache)'),
    ('エフェクト/物理', r'^(cl_particle|r_particle|fx_|rope_|cl_ragdoll|g_ragdoll|cl_phys|props_|cl_gib|violence_|cl_drawmonitors|cl_cull|cl_aggregate|projectile_)'),
    ('アニメ', r'^(cl_anim|anim|cl_bones|cl_threaded_bone|cl_SetupAllBones|BlendBones|cl_skipAnim|cl_requireAnim)'),
    ('音', r'^(snd_|sound_|miles_|audio_|music|voice|fx_sound|footstep)'),
    ('ネット/予測', r'^(cl_(predict|interp|smoo|lagcomp|resend|cmdbackup|updaterate|updatevisibility|timeout|matchmaking|ranked|pred)|net_|rate|match_|host_|projectile_prediction)'),
    ('テレメトリ/プライバシー', r'^(telemetry|pin_|comms_)'),
    ('フレーム/性能', r'^(fps_|cl_force|spectate|budget_|fs_)'),
    ('マッチ/ゲーム進行', r'^(mp_|sv_|zip|g_|gamemode|playlist|nucleus|match)'),
]

ANNOT = {
 'mouse_sensitivity': 'マウス感度', 'm_acceleration': 'マウス加速(0=off)',
 'mouse_use_per_scope_sensitivity_scalars': 'スコープ毎感度の有効化',
 'mouse_zoomed_sensitivity_scalar_0': 'アイアンサイト/1x感度', 'cl_use_raw_input_buffer': '生入力バッファ',
 'raw_input_deadzone': '生入力デッドゾーン', 'gamepad_aim_speed': 'パッド感度',
 'gamepad_look_curve': 'パッドのカーブ', 'gamepad_custom_enabled': 'パッド詳細感度の有効化',
 'hud_setting_minimapRotate': 'ミニマップ回転', 'hud_setting_adsDof': 'ADSのボケ',
 'hud_setting_pingAlpha': 'ピンの不透明度', 'hud_setting_damageTextStyle': 'ダメージ数字',
 'player_setting_autosprint': 'オートスプリント', 'cl_fovScale': 'FOVスケール',
 'fps_max': 'FPS上限', 'fps_absolute_max': 'FPS上限の絶対値', 'fps_max_use_refresh': 'リフレッシュ基準の上限',
 'mat_picmip': 'テクスチャ解像度(粗さ)', 'stream_memory': 'テクスチャ予算',
 'mat_forceaniso': '異方性フィルタ', 'r_lod_switch_scale': 'LOD切替距離',
 'ssao_enabled': '環境遮蔽', 'static_shadow': '静的影', 'mat_fullbright': '全面発光(CHEAT)',
 'cl_footstep_event_max_dist': '足音の最大距離', 'miles_channels': '音声チャンネル数',
 'miles_output_device': '音声出力デバイス', 'telemetry_client_enable': 'テレメトリ送信',
 'pin_opt_in': 'PIN調査オプトイン', 'cl_ragdoll_maxcount': 'ラグドール数',
 'rope_wind_dist': 'ジップ風切り音の距離', 'viewmodelShake': '武器の揺れ',
 'noise_filter_scale': 'フィルムグレイン', 'net_netGraph2': 'ネットグラフ',
}


CONFIRMED_FAMILIES = re.compile(
    r'^(mouse_zoomed_sensitivity_scalar_\d|gamepad_ads_advanced_sensitivity_scalar_\d|'
    r'gamepad_aim_speed_ads_\d|gamepad_custom_|dialogue_cat_|zipline_cooldown_time_\d|'
    r'miles_output_device|fov_disableAbilityScaling|sound_without_focus|bind_US_standard|bind_held)')

USER_CFG = (os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'local', 'settings.cfg'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'profile', 'profile.cfg'),
            os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'local', 'videoconfig.txt'))


def main():
    fp, rp, sp, outdir = sys.argv[1:5]
    strict = set()
    if len(sys.argv) > 5:
        for l in open(sys.argv[5], encoding='utf-8'):
            if not l.startswith('#') and l.strip():
                strict.add(l.split('\t')[0])
    usercfg = set()
    for p2 in USER_CFG:
        try:
            for l in open(p2, encoding='utf-8', errors='replace'):
                m = re.match(r'\s*"?([A-Za-z_][A-Za-z0-9_.]*)"?\s', l)
                if m:
                    usercfg.add(m.group(1).replace('setting.', ''))
        except OSError:
            pass
    extra = [l.strip() for l in sys.stdin if l.strip()]
    fields = {}
    for l in open(fp, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        c = l.rstrip('\n').split('\t')
        fields[c[0]] = c
    readers = {}
    for l in open(rp, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        c = l.rstrip('\n').split('\t')
        readers[c[0]] = c

    def flagnames(v):
        if not v:
            return ''
        f = int(v, 16)
        return '|'.join(n for b, n in sorted(FLAGS.items()) if f & b)

    rows = []
    for n, c in fields.items():
        r = readers.get(n)
        hx = int(r[6]) if r else 0
        vx = int(r[7]) if r else 0
        flags = c[3]
        fv = int(flags, 16) if flags else 0
        usable = not (fv & 0x4000)
        if strict:
            if n in strict:
                tier = 'A'
            elif n in usercfg or CONFIRMED_FAMILIES.match(n):
                tier = 'A2'
            elif c[5] and flags != '0x1':
                tier = 'A2'      # name + flags + default value string => recovered cvar
            else:
                tier = 'X'       # engine name table, not a cvar
        else:
            tier = 'A'
        rows.append(dict(name=n, default=c[5], flags=flags, flagstr=flagnames(flags),
                         read=hx > 0 or vx > 0, hx=hx, vx=vx, cheat=bool(fv & 0x4000),
                         script=bool(fv & 0x1000000), src='static', tier=tier))
    known = {r['name'] for r in rows}
    for n in extra:
        if n in known:
            continue
        known.add(n)
        rows.append(dict(name=n, default='', flags='', flagstr='(動的登録: 既定値は静的取得不可)',
                         read=True, hx=0, vx=0, cheat=False, script=False, src='dynamic', tier='C'))

    with open(os.path.join(outdir, 'cvar-ledger.tsv'), 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tdefault\tflags\tflags_decoded\tread_by_native\tcheat\tsource\ttier\n")
        for r in sorted(rows, key=lambda r: r['name']):
            if r['tier'] == 'X':
                continue
            fh.write(f"{r['name']}\t{r['default']}\t{r['flags']}\t{r['flagstr']}\t"
                     f"{int(r['read'])}\t{int(r['cheat'])}\t{r['src']}\t{r['tier']}\n")
    with open(os.path.join(outdir, 'non-cvar-name-tables.txt'), 'w', encoding='utf-8') as fh:
        fh.write("# 登録スタブの形をしていない名前テーブル（cvar ではない。参考として保存）\n")
        for r in sorted(rows, key=lambda r: r['name']):
            if r['tier'] == 'X':
                fh.write(r['name'] + '\n')

    # readable full list
    used = set()
    buckets = collections.OrderedDict((g, []) for g, _ in GROUPS)
    buckets['その他'] = []
    for r in sorted(rows, key=lambda r: r['name']):
        if r['tier'] == 'X':
            continue
        for g, pat in GROUPS:
            if re.match(pat, r['name']):
                buckets[g].append(r)
                used.add(r['name'])
                break
        else:
            buckets['その他'].append(r)
    os.makedirs(outdir, exist_ok=True)
    md = os.path.join(outdir, 'CVAR-LIST-FULL.md')
    with open(md, 'w', encoding='utf-8') as fh:
        fh.write('# autoexec から設定できる cvar 全リスト（静的解析 / v3.0.1.28）\n\n'
                 f'対象 `r5apex_dx12.exe` sha256 `8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825`\n\n'
                 f'- **{len(rows)}** 件（うち静的に記述子まで取得: {sum(1 for r in rows if r["src"] == "static")} 件、'
                 f'動的登録（コードが名前で読むが記述子は静的になし）: {sum(1 for r in rows if r["src"] == "dynamic")} 件）\n'
                 f'- `読み` = このビルドのネイティブコードが値を参照しているか（ハンドル/値スロットへの xref）\n'
                 f'- `CHEAT` 付きは MP では `sv_cheats`が必要＝実質使えない\n\n'
                 f'書式: `cvar` 既定=… [flags] (読み)\n\n')
        for g, items in buckets.items():
            if not items:
                continue
            fh.write(f'## {g} ({len(items)})\n\n')
            for r in items:
                note = ANNOT.get(r['name'])
                tag = []
                if r['cheat']:
                    tag.append('CHEAT')
                elif r['src'] == 'dynamic':
                    tag.append('動的登録=既定値不明')
                elif not r['read']:
                    tag.append('native読み手なし')
                if r.get('tier', 'A').startswith('B'):
                    tag.append('B/確定' if r['tier'] == 'B-confirmed' else 'B=未確定')
                line = f"- `{r['name']}` 既定=`{r['default'] or ' '}`"
                if r['flagstr']:
                    line += f" [{r['flagstr']}]"
                if tag:
                    line += f" ({', '.join(tag)})"
                if note:
                    line += f" — {note}"
                fh.write(line + '\n')
            fh.write('\n')
    print(f'ledger rows: {len(rows)}  -> {outdir}/cvar-ledger.tsv, CVAR-LIST-FULL.md')
    import collections as _c
    print('tiers:', dict(_c.Counter(r.get('tier') for r in rows)))
    print('cheat:', sum(1 for r in rows if r['cheat']),
          'no-reader:', sum(1 for r in rows if not r['read'] and r['src'] == 'static'),
          'dynamic:', sum(1 for r in rows if r['src'] == 'dynamic'))


if __name__ == '__main__':
    main()
