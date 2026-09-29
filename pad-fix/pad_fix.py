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
import json
import os
import re
import shutil
import sys
import time

SAVED = os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex')
# GetFileAttributesW は失敗時に -1 を返す。既定の restype(int) では 0xFFFFFFFF と比較できないため明示する
_k32 = ctypes.windll.kernel32
_k32.GetFileAttributesW.restype = ctypes.c_uint32
_k32.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
_k32.SetFileAttributesW.restype = ctypes.c_int
_k32.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
INVALID = 0xFFFFFFFF
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')
MANIFEST = os.path.join(BACKUP, 'manifest.json')
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
    attrs = _k32.GetFileAttributesW(path)
    if attrs == INVALID:
        raise OSError('ファイルが見つからない/属性を読めない: %s' % path)
    want = (attrs | READONLY) if locked else (attrs & ~READONLY)
    if not _k32.SetFileAttributesW(path, want):
        raise OSError('属性を変更できなかった: %s' % path)


def is_locked(path):
    """True/False、取得できなければ None"""
    attrs = _k32.GetFileAttributesW(path)
    if attrs == INVALID:
        return None
    return bool(attrs & READONLY)


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


def legacy_order(path):
    """旧形式バックアップの並び: (時刻, 連番, 名前)。連番は同秒内の世代順"""
    name = os.path.basename(path)
    m = re.match(r'^(\d{8}-\d{6})(?:-(\d+))?__', name)
    if m:
        return (m.group(1), int(m.group(2) or 1), name)
    return ('00000000-000000', 1, name)


def load_manifest():
    """[{'backup':名前,'origin':元の絶対パス,'time':記録時刻}] の順序付きリスト"""
    if not os.path.exists(MANIFEST):
        return []
    try:
        data = json.load(open(MANIFEST, encoding='utf-8'))
    except ValueError:
        return []
    if isinstance(data, dict):          # 旧形式 {backup: origin} をリストへ移行
        return [{'backup': k, 'origin': v, 'time': 0.0} for k, v in data.items()]
    return list(data)


def backup(path):
    os.makedirs(BACKUP, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    dest = os.path.join(BACKUP, '%s__%s' % (stamp, os.path.basename(path)))
    n = 1
    while os.path.exists(dest):          # 同秒・同名でも上書きしない
        n += 1
        dest = os.path.join(BACKUP, '%s-%d__%s' % (stamp, n, os.path.basename(path)))
    shutil.copyfile(path, dest)
    set_lock(dest, False)
    manifest = load_manifest()
    manifest.append({'backup': os.path.basename(dest), 'origin': os.path.abspath(path),
                     'time': time.time()})
    with open(MANIFEST, 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    return dest


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--dry'
    files = targets()
    if not files:
        return 1

    if mode == '--restore':
        manifest = load_manifest()
        seen_backups = set()
        seen_origins = set()
        problems = []
        count = 0
        # 1) マニフェストに記録された「初回適用前」を復元する（元パスごとに最初の世代だけ）
        for entry in manifest:
            name = entry['backup']
            origin_key = entry['origin'].lower()
            if name in seen_backups or origin_key in seen_origins:
                continue
            seen_backups.add(name)
            seen_origins.add(origin_key)
            origin = entry['origin']
            src = os.path.join(BACKUP, name)
            if not os.path.exists(src):
                problems.append('初回バックアップが無い: %s（手動で復元してください）' % name)
                continue
            if not os.path.exists(origin):
                problems.append('復元先が無い: %s' % origin)
                continue
            set_lock(origin, False)
            shutil.copyfile(src, origin)
            set_lock(origin, False)
            print('復元(原値): %s <- %s' % (origin, name))
            count += 1
        # 2) マニフェスト外（旧形式）のバックアップ: 名前から復元先を探す
        #    - 既に復元済みのファイルには触らない（新しい世代で上書きしない）
        #    - 復元先が複数候補で特定できない場合は推測せず警告して失敗扱いにする
        manifest_names = {e['backup'] for e in manifest}
        for source in sorted(glob.glob(os.path.join(BACKUP, '*.cfg')), key=legacy_order):
            name = os.path.basename(source)
            if name in manifest_names:
                continue
            target = name.split('__', 1)[-1]
            hits = glob.glob(os.path.join(SAVED, '**', target), recursive=True)
            if not hits:
                problems.append('旧形式バックアップの復元先が見つからない: %s' % name)
                continue
            if len(hits) > 1:
                # 出所不明の旧バックアップは推測で戻さない（1件でも誤爆を防ぐ）
                problems.append('旧形式バックアップの復元先が一意でない（候補%d件）: %s' % (len(hits), name))
                continue
            origin = hits[0]
            if origin.lower() in seen_origins:
                continue                       # 既にマニフェスト側で復元済み
            set_lock(origin, False)
            shutil.copyfile(source, origin)
            set_lock(origin, False)
            print('復元(旧形式): %s <- %s' % (origin, name))
            seen_origins.add(origin.lower())
            count += 1
        for msg in problems:
            print('WARNING: %s' % msg)
        if not count and not problems:
            print('バックアップが無い（backup/ が空）')
            return 1
        return 1 if problems else 0

    if mode == '--unlock':
        for path, _ in files:
            set_lock(path, False)
            print('ロック解除: %s' % path)
        return 0

    if mode == '--apply':
        have = {os.path.basename(path) for path, _ in files}
        if have != {'profile.cfg', 'settings.cfg'}:
            print('ERROR: profile.cfg と settings.cfg の両方が必要（見つかったのは: %s）' % sorted(have or ['なし']))
            print('       Apex を一度起動して設定ファイルを作ってから実行する。')
            return 2

    total = 0
    failed = False
    for path, wanted in files:
        lines, changed = transform(path, wanted)
        for name, old, new in changed:
            print('  %s: %s -> %s' % (name, old, new))
        print('%s: 変更 %d 項目' % (os.path.basename(path), len(changed)))
        total += len(changed)
        if mode == '--apply':
            backup(path)            # 変更が無くても必ずバックアップ（初回適用前の状態を保証する）
            if changed:
                set_lock(path, False)
                with open(path, 'w', encoding='utf-8', newline='\r\n') as handle:
                    handle.write('\n'.join(lines) + '\n')
            set_lock(path, True)
            state = is_locked(path)
            if state is True:
                print('  → ロック適用: %s' % path)
            else:
                print('  → ERROR: 読み取り専用にできなかった/属性を確認できない（権限を確認）: %s' % path)
                failed = True
    print('合計 %d 項目（%s）' % (total, 'DRY RUN' if mode == '--dry' else mode))
    if mode == '--dry':
        print('※ 適用するには --apply（ゲームを終了してから）')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
