#!/usr/bin/env python
"""2 つのセッションスナップショットのうち、入力系 cvar の差分だけを出す。

usage: python config_diff.py <dirA> <dirB>
"""
import os
import re
import sys

KEYS = re.compile(r'^(mouse|gamepad|input|cl_|in_|disable_mouselook|aimassist|controller)', re.I)


def read_cvars(path):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            match = re.match(r'([A-Za-z0-9_]+)\s+"?([^"]*)"?$', line)
            if match:
                values[match.group(1)] = match.group(2)
    return values


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    left, right = sys.argv[1], sys.argv[2]
    changed = 0
    for name in ('settings.cfg', 'profile.cfg'):
        a = read_cvars(os.path.join(left, name))
        b = read_cvars(os.path.join(right, name))
        keys = sorted(set(a) | set(b))
        for key in keys:
            if not KEYS.match(key):
                continue
            if a.get(key) != b.get(key):
                changed += 1
                print('%-40s %-12s -> %-12s  (%s)' % (key, a.get(key, '(none)'), b.get(key, '(none)'), name))
    print('入力系の差分: %d 件' % changed)
    return 0


if __name__ == '__main__':
    sys.exit(main())
