#!/usr/bin/env python
"""pad_fix.py — Apex Legends: パッド設定がマウス感度に混入するのを止める（設定値のみ・注入なし）

やること:
  profile.cfg の16項目と settings.cfg の2項目を「確定値」に揃え、最後に読み取り専用ロックする。
  既存行は値を書き換え、無い行は末尾に追記する（＝18項目を必ず保証する）。

使い方（ゲームを終了してから実行）:
  python pad_fix.py --dry       変更内容の表示のみ（書き込まない）
  python pad_fix.py --apply     バックアップして適用＋読み取り専用ロック
  python pad_fix.py --unlock    ロックだけ外す（手で編集したい時）
  python pad_fix.py --restore   初回適用前の状態に戻す（ロックも外す）

注意:
  - 反映は次回起動から。起動→終了後に値が戻っていないか確認する
  - ロック中は「そのファイル内の他の設定（解像度・バインド等）」も保存されなくなる
  - パッド未接続でも影響が出る／起動オプション -nojoy では防げない
"""
import ctypes
import glob
import os
import shutil
import sys
import time

SAVED = os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex')
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
READONLY = 0x01

SCALARS = {f'gamepad_ads_advanced_sensitivity_scalar_{i}': '0.2' for i in range(8)}
AIM_ASSIST = {name: '0.0' for name in (
    'gamepad_aim_assist_ads_high_power_scopes', 'gamepad_aim_assist_ads_low_power_scopes',
    'gamepad_aim_assist_hip_high_power_scopes', 'gamepad_aim_assist_hip_low_power_scopes',
    'gamepad_aim_assist_melee')}
PROFILE_ITEMS = {
    **SCALARS, **AIM_ASSIST,
    'gamepad_use_per_scope_sensitivity_scalars': '1',   # これが 1 でないと上の 0.2 が効かない
    'joystick': '0',
    'disable_mouselook': '0',
}
SETTINGS_ITEMS = {'joystick': '0', 'disable_mouselook': '0'}


def set_lock(path, locked):
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
    if attrs == 0xFFFFFFFF:
        raise OSError('ファイルが見つからない: %s' % path)
    ctypes.windll.kernel32.SetFileAttributesW(
        path, (attrs | READONLY) if locked else (attrs & ~READONLY))


def is_locked(path):
    return bool(ctypes.windll.kernel32.GetFileAttributesW(path) & READONLY)


def parse(line):
    if '"' not in line:
        return None, None
    parts = line.split('"')
    if len(parts) < 3:
        return None, None
    return parts[0].strip(), parts[1]


def equal_value(current, want):
    try:
        return float(current) == float(want)
    except ValueError:
        return current == want


def transform(path, wanted):
    with open(path, encoding='utf-8', errors='replace') as handle:
        lines = handle.read().splitlines()
    changed, seen = [], set()
    for index, line in enumerate(lines):
        name, value = parse(line)
        if name is None:
            continue
        seen.add(name)
        if name in wanted and not equal_value(value, wanted[name]):
            lines[index] = line.split('"')[0] + '"%s"' % wanted[name]
            changed.append((name, value, wanted[name]))
    for name, value in wanted.items():
        if name not in seen:
            lines.append('%s "%s"' % (name, value))
            changed.append((name, '(なし)', value))
    return lines, changed


def targets():
    out = []
    for name, wanted in (('profile.cfg', PROFILE_ITEMS), ('settings.cfg', SETTINGS_ITEMS)):
        hits = glob.glob(os.path.join(SAVED, '**', name), recursive=True)
        if not hits:
            print('※ %s が見つからない（初回起動で作られる。起動後に再実行）' % name)
        for path in hits:
            out.append((path, wanted))
    return out


def backup(path):
    os.makedirs(BACKUP, exist_ok=True)
    dest = os.path.join(BACKUP, '%s__%s' % (time.strftime('%Y%m%d-%H%M%S'), os.path.basename(path)))
    shutil.copyfile(path, dest)
    set_lock(dest, False)
    return dest


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--dry'
    files = targets()
    if not files:
        return 1

    if mode == '--restore':
        earliest = {}
        for source in sorted(glob.glob(os.path.join(BACKUP, '*.cfg'))):
            earliest.setdefault(os.path.basename(source).split('__')[-1], source)
        count = 0
        for target, source in earliest.items():
            for candidate in glob.glob(os.path.join(SAVED, '**', target), recursive=True):
                set_lock(candidate, False)
                shutil.copyfile(source, candidate)
                set_lock(candidate, False)
                print('復元(原値): %s <- %s' % (candidate, os.path.basename(source)))
                count += 1
        if not count:
            print('バックアップが無い（backup/ が空）')
        return 0 if count else 1

    if mode == '--unlock':
        for path, _ in files:
            set_lock(path, False)
            print('ロック解除: %s' % path)
        return 0

    total = 0
    for path, wanted in files:
        lines, changed = transform(path, wanted)
        for name, old, new in changed:
            print('  %s: %s -> %s' % (name, old, new))
        print('%s: 変更 %d 項目' % (os.path.basename(path), len(changed)))
        total += len(changed)
        if mode == '--apply':
            if changed:
                backup(path)
                set_lock(path, False)
                with open(path, 'w', encoding='utf-8', newline='\r\n') as handle:
                    handle.write('\n'.join(lines) + '\n')
            else:
                set_lock(path, False)   # 変更なしでもロック状態を確定させる
            set_lock(path, True)
            print('  → ロック適用: %s（readonly=%s）' % (path, is_locked(path)))
    print('合計 %d 項目（%s）' % (total, 'DRY RUN' if mode == '--dry' else mode))
    if mode == '--dry':
        print('※ 適用するには --apply（ゲームを終了してから）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
