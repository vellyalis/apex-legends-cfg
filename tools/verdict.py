#!/usr/bin/env python
"""verdict.py - 蓄積した証拠から判定文を生成する（放置運用向け）

読むもの: evidence/auto/session-*.jsonl（生入力観測）, config-watch.jsonl（設定変化）
出すもの: evidence/auto/verdict.txt（判定文）+ 標準出力
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'evidence', 'auto')
GATE_CVARS = ('disable_mouselook', 'gamepad_', 'mouse_', 'sensitivity')


def summarize_session(path: str) -> dict:
    ticks = 0
    focused = 0
    gaps = 0
    deltas = 0
    last = None
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            ts = row.get('ts')
            if last is not None and isinstance(ts, (int, float)) and ts - last > 500:
                gaps += 1
            if isinstance(ts, (int, float)):
                last = ts
            if row.get('event') == 'focus':
                focused += 1
            if row.get('event') == 'tick':
                ticks += 1
                if abs(row.get('dx', 0)) + abs(row.get('dy', 0)) > 0 or row.get('mouse_events', 0) > 0:
                    deltas += 1
    return {'file': os.path.basename(path), 'ticks': ticks, 'focused': focused,
            'gaps_over_500ms': gaps, 'ticks_with_mouse_delta': deltas}


def config_changes(path: str) -> list:
    changes = []
    if not os.path.exists(path):
        return changes
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if 'changed' in row:
                changes.append(row)
    return changes


def main() -> int:
    lines = ['=== 放置監視 判定 (%s) ===' % os.path.basename(sys.argv[0]), '']
    sessions = sorted(glob.glob(os.path.join(OUT, 'session-*.jsonl')))
    if not sessions:
        lines.append('セッション記録なし（ゲーム未起動のまま）')
    for path in sessions:
        info = summarize_session(path)
        lines.append('セッション %s: ticks=%d 前面=%d 取りこぼし(>500ms)=%d デルタあり=%d'
                     % (info['file'], info['ticks'], info['focused'], info['gaps_over_500ms'],
                        info['ticks_with_mouse_delta']))
        if info['ticks'] and info['gaps_over_500ms'] / max(1, info['ticks']) > 0.05:
            lines.append('  → 警告: 入力取りこぼしが 5%% 超（フレーム供給が乱れている可能性）')
    changes = config_changes(os.path.join(OUT, 'config-watch.jsonl'))
    gate_hits = [row for row in changes
                 if any(key in json.dumps(row, ensure_ascii=False) for key in GATE_CVARS)]
    lines.append('')
    lines.append('設定変化: 全 %d 件 / 入力系 %d 件' % (len(changes), len(gate_hits)))
    for row in gate_hits[:12]:
        lines.append('  %s' % json.dumps(row, ensure_ascii=False)[:300])
    if not gate_hits:
        lines.append('  → 入力系 cvar（disable_mouselook / gamepad_* / mouse_* / *sensitivity*）の変化は記録されていない')
    lines.append('')
    lines.append('判定: %s' % ('入力系設定の変化あり → ゲート経路の実機証拠を確認' if gate_hits
                               else '入力系設定の変化なし → ゲート経路は実機では発火していない（現時点）'))
    text = '\n'.join(lines) + '\n'
    with open(os.path.join(OUT, 'verdict.txt'), 'w', encoding='utf-8') as handle:
        handle.write(text)
    print(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
