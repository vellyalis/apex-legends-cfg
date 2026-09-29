#!/usr/bin/env python
"""pad_fix.py — Apex Legends: パッド設定のマウス感度への混入を最小化する

静的解析の結論: パッド側のスカラー設定が「共有ゲート／共有定数」経由でマウス感度段の
計算に混入する（パッド未接続でも毎フレーム無条件で共有状態が書かれる）。
よって「パッド側スカラーを下限に固定 + joystick 0 / disable_mouselook 0 を明示」が最小化になる。

使い方:
  python pad_fix.py --dry       変更内容の表示のみ
  python pad_fix.py --apply     バックアップして適用（最後に読み取り専用ロック）
  python pad_fix.py --unlock    ロックだけ外す（編集したい時）
  python pad_fix.py --restore   初回適用前の状態に戻す（ロックも外す）

注意:
  - ゲームを**終了してから**実行する
  - 反映は次回起動から。起動→終了後にファイルの値が戻っていないか確認する
  - ゲーム改造・注入は一切しない（設定ファイルの数値のみ）
"""
import ctypes
import glob
import os
import shutil
import sys
import time

SAVED = os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex')
BACKUP = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backup')

# 変更対象: 構造解析で「共有計算への混入」が確認された項目だけ
PATTERNS = ('gamepad_ads_advanced_sensitivity_scalar_', 'gamepad_aim_assist_')
# 存在しなければ末尾に追記する固定行（無くても動くように明示）
FORCE = {'joystick': '0', 'disable_mouselook': '0'}
# profile.cfg のみ: これが ON(1) でないと下の 0.2 スカラーが使われない
FORCE_PROFILE = {'gamepad_use_per_scope_sensitivity_scalars': '1'}

READONLY = 0x01


def set_lock(path, locked):
    attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
    ctypes.windll.kernel32.SetFileAttributesW(
        path, (attrs | READONLY) if locked else (attrs & ~READONLY))


def parse(line):
    if '"' not in line:
        return None, None
    parts = line.split('"')
    if len(parts) < 3:
        return None, None
    return parts[0].strip(), parts[1]


def minimize(value, name=''):
    try:
        number = float(value)
    except ValueError:
        return value
    if 'gamepad_ads_advanced_sensitivity_scalar' in name:
        # エンジン下限は 0.2。0.0 を書いても 0.2 にクランプされる（実測済み）
        return value if number == 0.2 else '0.2'
    return value if number == 0.0 else '0.0'


def transform(path):
    with open(path, encoding='utf-8', errors='replace') as handle:
        lines = handle.read().splitlines()
    changed, seen = [], set()
    for index, line in enumerate(lines):
        name, value = parse(line)
        if not name:
            continue
        seen.add(name)
        if name == 'gamepad_use_per_scope_sensitivity_scalars' and value not in ('1', '1.0'):
            lines[index] = '%s"1"' % line.split('"')[0]
            changed.append((name, value, '1'))
            continue
        if any(pattern in name for pattern in PATTERNS):
            new = minimize(value, name)
            if new != value:
                lines[index] = '%s"%s"' % (line.split('"')[0], new)
                changed.append((name, value, new))
    force = dict(FORCE)
    if os.path.basename(path) == 'profile.cfg':
        force.update(FORCE_PROFILE)
    for name, value in force.items():
        if name not in seen:
            lines.append('%s "%s"' % (name, value))
            changed.append((name, '(なし)', value))
    return lines, changed


def targets():
    found = []
    for name in ('profile.cfg', 'settings.cfg'):
        found += glob.glob(os.path.join(SAVED, '**', name), recursive=True)
    return found


def backup(path):
    os.makedirs(BACKUP, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M%S')
    dest = os.path.join(BACKUP, '%s__%s' % (stamp, os.path.basename(path)))
    shutil.copyfile(path, dest)
    set_lock(dest, False)
    return dest


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else '--dry'
    files = targets()
    if not files:
        print('対象が見つからない: %s' % SAVED)
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
        return 0 if count else 1

    if mode == '--unlock':
        for path in files:
            set_lock(path, False)
            print('ロック解除: %s' % path)
        return 0

    total = 0
    for path in files:
        lines, changed = transform(path)
        if not changed:
            print('%s: 変更なし（既に最小）' % path)
            continue
        for name, old, new in changed:
            print('  %s: %s -> %s' % (name, old, new))
        if mode == '--apply':
            backup(path)
            set_lock(path, False)
            with open(path, 'w', encoding='utf-8', newline='\r\n') as handle:
                handle.write('\n'.join(lines) + '\n')
            set_lock(path, True)
            print('適用+ロック: %s（バックアップ: backup/）' % path)
        total += len(changed)
    print('変更項目数: %d（%s）' % (total, 'DRY RUN' if mode == '--dry' else mode))
    return 0


if __name__ == '__main__':
    sys.exit(main())
