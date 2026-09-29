#!/usr/bin/env python
"""Build the cleaned autoexec.cfg from the audit verdicts.

Usage: python mk_fixed_cfg.py <autoexec.cfg> <audit3/autoexec-audit.tsv> <outfile>
Keeps entries whose cvar exists in the current build, comments out the rest with
the reason, and appends suggested entries that the original list missed.
"""
import sys, re

KEEP = {'registered', 'registered-scriptread', 'registered-noread', 'registered-unverified'}
SUGGEST = [
    ('cl_use_raw_input_buffer', '1', 'current raw-input path (replaces m_rawinput)'),
    ('fps_max_use_refresh', '0', 'fps_max override behaviour'),
    ('hud_setting_showEnemyHealthBar', '1', 'enemy health bar under crosshair'),
    ('hud_setting_compactOverHeadNames', '1', 'smaller name plates'),
    ('hud_setting_showButtonHints', '0', 'hide button hints'),
    ('player_setting_holdtosprint', '0', 'hold-to-sprint toggle'),
    ('weapon_setting_autocycle_on_empty', '1', 'auto weapon cycle on empty'),
    ('colorblind_mode', '0', 'colorblind filter'),
    ('cl_prevent_weapon_text_hints', '1', 'hide weapon text hints'),
    ('hud_setting_showHopUpPopUp', '0', 'hide hop-up popups'),
    ('miles_output_device', '', 'audio output device (written by the game)'),
    ('setting.ssao_downsample', '0', 'VIDEOCONFIG key, not a cvar - put it in videoconfig.txt'),
]


def main():
    cfg, audit, out = sys.argv[1], sys.argv[2], sys.argv[3]
    verdicts = {}
    for line in open(audit, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        verdicts[int(c[0])] = c
    kept = removed = 0
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('// autoexec.cfg  for Apex Legends v3.0.1.28 (build R5pc_r5-301_J28_CL11570498)\n'
                 '// audited against r5apex_dx12.exe sha256 8bacf98c9409352b198ece7800a09141585a95eaf6f9dc003c0f6c1114ca3825\n'
                 '// every uncommented line is a cvar that exists in THIS build (registration stub + reader found).\n'
                 '// lines commented out below are dead in this build (see the reason on each line).\n'
                 '// launch option: +exec autoexec.cfg   (put this file next to r5apex_dx12.exe)\n'
                 '// NOTE: "+fps_max 0" in the launch options runs AFTER +exec, so it wins over fps_max below.\n\n')
        for i, raw in enumerate(open(cfg, encoding='utf-8', errors='replace'), 1):
            line = raw.rstrip('\n')
            v = verdicts.get(i)
            if v is None or not v[1]:
                fh.write(line + '\n')
                continue
            name, value, verdict = v[1], v[2], v[3]
            note = v[12]
            if re.match(r'^\s*//', line) and not verdict:
                fh.write(line + '\n')
                continue
            if verdict in KEEP:
                extra = ''
                if verdict == 'registered-noread':
                    extra = ' [warn: no code reads this cvar]'
                if verdict == 'registered-unverified':
                    extra = ' [warn: registered, fields unverified]'
                fh.write(f'{name} "{value}"'.ljust(50) + f'// {note[:56]}{extra}\n')
                kept += 1
            else:
                why = dict(absent='name absent from this build',
                           **{'string-only': 'string exists but the cvar is not registered'},
                           **{'cheat': 'FCVAR_CHEAT: needs sv_cheats (server side)'},
                           **{'videoconfig-key': 'videoconfig.txt key, not a cvar'},
                           **{'registered-noread': 'registered but nothing reads it'}).get(verdict, verdict)
                fh.write(f'// DEAD  {name} "{value}"'.ljust(50) + f'// {verdict}: {why}\n')
                removed += 1
        fh.write('\n// ---- candidates this build has and the original list missed ----\n')
        for n, val, why in SUGGEST:
            fh.write(f'// {n} "{val}"'.ljust(50) + f'// {why}\n')
    print(f'kept={kept} removed={removed} -> {out}')


if __name__ == '__main__':
    main()
