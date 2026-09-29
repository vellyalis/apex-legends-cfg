#!/usr/bin/env python
"""Compare third-party autoexec.cfg files against the local cvar ledger.

Usage: python cmp_repos.py <exe> <ledger.tsv> <out.txt> <label:path> [label:path ...]

Classification per entry (cvar name only; binds/commands are skipped):
  live      = in ledger (registered in THIS build)
  cheat     = in ledger with FCVAR_CHEAT
  noread    = in ledger but no native reader
  name-only = name string exists in the exe but not registered (dead string)
  absent    = name not in the exe at all (dead)
Also reports, per file, the live entries that are NOT in out/autoexec.mine.cfg.
"""
import sys, os, re, collections

BIND = re.compile(r'^\s*(bind_?\w*|unbind|unbindall|sensitivity|m_rawinput)\s')
NAME = re.compile(r'^([A-Za-z_][A-Za-z0-9_.]*)\s*(.*)$')
MINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'autoexec.mine.cfg')


def load_mine():
    out = set()
    p = os.path.normpath(MINE)
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            body = l.split('//')[0].strip()
            m = NAME.match(body)
            if m and not body.startswith('//'):
                out.add(m.group(1))
    return out


def main():
    exe, ledger_p, out_p = sys.argv[1:4]
    pairs = [a.split(':', 1) for a in sys.argv[4:]]
    exe_b = open(exe, 'rb').read()
    ledger = {}
    for l in open(ledger_p, encoding='utf-8'):
        if l.startswith('#') or not l.strip():
            continue
        c = l.rstrip('\n').split('\t')
        ledger[c[0]] = c          # name, default, flags, flagstr, read, cheat, src, tier
    mine = load_mine()

    report = []
    for label, path in pairs:
        if not os.path.exists(path):
            report.append(f'{label}: MISSING {path}')
            continue
        names = []
        for l in open(path, encoding='utf-8', errors='replace'):
            body = l.split('//')[0].strip()
            if not body or BIND.match(body):
                continue
            m = NAME.match(body)
            if m:
                names.append(m.group(1))
        uniq = list(dict.fromkeys(names))
        cnt = collections.Counter()
        live_items, dead_items, cheat_items, noread_items = [], [], [], []
        for n in uniq:
            e = ledger.get(n)
            if e:
                if e[5] == '1':
                    cnt['cheat'] += 1
                    cheat_items.append(n)
                elif e[4] == '1':
                    cnt['live'] += 1
                    live_items.append(n)
                else:
                    cnt['noread'] += 1
                    noread_items.append(n)
            elif (n.encode() + b'\0') in exe_b:
                cnt['name-only'] += 1
                dead_items.append(n)
            else:
                cnt['absent'] += 1
                dead_items.append(n)
        missing_from_mine = [n for n in live_items if n not in mine]
        report.append(f'==== {label} ({os.path.basename(path)})')
        report.append(f'  entries(unique cvar names): {len(uniq)}')
        report.append(f'  live(登録済み)={cnt["live"]}  cheat={cnt["cheat"]}  '
                      f'登録あるが読み手なし={cnt["noread"]}  文字列のみ={cnt["name-only"]}  存在しない={cnt["absent"]}')
        report.append(f'  live のうち autoexec.mine.cfg に無いもの ({len(missing_from_mine)}): '
                      + ', '.join(missing_from_mine[:40]))
        report.append(f'  死に項目の例: ' + ', '.join(dead_items[:15]))
        report.append('')
    txt = '\n'.join(report)
    open(out_p, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
