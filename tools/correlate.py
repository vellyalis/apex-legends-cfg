#!/usr/bin/env python
"""apex_observer のジャーナルを集計し、パッド活動とマウス入力の関係を出す。

usage: python correlate.py <journal.jsonl> [--deadzone 7849] [--quiet-threshold 0.02]

出力:
  - 全体: 期間、tick 数、マウスの総移動量、イベント数
  - パッド活動区間 / 非活動区間 それぞれの「1 tick あたりの移動量・イベント数・取りこぼし率」
  - 判定に使う数値だけを並べる（人間の解釈は後段の自律ループで）
"""
import argparse
import json
import sys


def load(path):
    ticks = []
    focus = []
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get('event') == 'tick':
                ticks.append(row)
            elif row.get('event') == 'focus':
                focus.append(row)
    return ticks, focus


def pad_active(row, deadzone):
    pad = row.get('pad')
    if not pad:
        return False
    if abs(pad.get('lx', 0)) > deadzone or abs(pad.get('ly', 0)) > deadzone:
        return True
    if abs(pad.get('rx', 0)) > deadzone or abs(pad.get('ry', 0)) > deadzone:
        return True
    if pad.get('lt', 0) > 32 or pad.get('rt', 0) > 32 or pad.get('buttons', 0):
        return True
    return False


def summarize(rows, label):
    if not rows:
        print('%-14s: データなし' % label)
        return
    ticks = len(rows)
    motion = sum(abs(r.get('dx', 0)) + abs(r.get('dy', 0)) for r in rows)
    events = sum(r.get('mouse_events', 0) for r in rows)
    active_ticks = sum(1 for r in rows if r.get('dx') or r.get('dy'))
    print('%-14s: ticks=%d  移動量=%d  events=%d  動いたtick=%d (%.1f%%)  1tick平均=%.3f' % (
        label, ticks, motion, events, active_ticks, 100.0 * active_ticks / ticks,
        motion / ticks if ticks else 0.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('journal')
    parser.add_argument('--deadzone', type=int, default=7849)
    args = parser.parse_args()
    ticks, focus = load(args.journal)
    if not ticks:
        print('tick がありません')
        return 1
    pad_present = any('pad' in row for row in ticks)
    active = [r for r in ticks if pad_active(r, args.deadzone)]
    idle = [r for r in ticks if not pad_active(r, args.deadzone)]
    first = ticks[0].get('ts', 0)
    last = ticks[-1].get('ts', 0)
    print('期間: %.1f 秒 / tick=%d / パッド情報=%s' % ((last - first) / 1000.0, len(ticks),
                                                     'あり' if pad_present else 'なし'))
    if focus:
        seen = []
        for row in focus:
            name = row.get('process', '')
            if not seen or seen[-1] != name:
                seen.append(name)
        print('前面プロセスの遷移: %s' % ' -> '.join(seen[:12]))
    summarize(ticks, '全体')
    summarize(active, 'パッド活動中')
    summarize(idle, 'パッド非活動')
    # 取りこぼし（移動があったのにイベント0の tick）を数える
    gaps = sum(1 for r in ticks if r.get('mouse_events', 0) == 0 and (r.get('dx') or r.get('dy')))
    print('矛盾 tick（移動あり / events=0）: %d' % gaps)
    return 0


if __name__ == '__main__':
    sys.exit(main())
