#!/usr/bin/env python
"""Coverage measurement: how complete is the cvar enumeration really?

A = validated descriptors (cvar_fields.tsv)
B = names lea'd by SMALL functions (<=0x600 bytes)  (cvar_stubs.tsv)
C = names lea'd by ANY function in .text
D = names appearing as "<name>\\0<default>\\0" pairs in the string pool
U = names the game itself writes into the user cfg files

Usage: python coverage.py <exe> <fields.tsv> <stubs.tsv> <out.txt>
"""
import sys, os, re
from cvar_registry import PE
from cvar_stubs import Text

CFG = [r'C:\Users\kazuy\Saved Games\Respawn\Apex\local\settings.cfg',
       r'C:\Users\kazuy\Saved Games\Respawn\Apex\profile\profile.cfg',
       r'C:\Users\kazuy\Saved Games\Respawn\Apex\local\videoconfig.txt']
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_.]{1,63}$')
KEY = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_.]*)\s')


def main():
    exe, fp, sp, out = sys.argv[1:5]
    pe = PE(exe)
    t = Text(pe)
    A = set()
    for l in open(fp, encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            A.add(l.split('\t')[0])
    B = set()
    for l in open(sp, encoding='utf-8'):
        if not l.startswith('#') and l.strip():
            B.add(l.split('\t')[0])
    C = set()
    big = set()
    for site, tgt in t.lea_sites():
        if tgt not in pe.name_starts:
            continue
        s = pe.cstr(tgt)
        if not s or not NAME.match(s):
            continue
        C.add(s)
        f = t.func_of(site)
        if f and (f[1] - f[0]) > 0x600:
            big.add(s)
    U = set()
    for p in CFG:
        if not os.path.exists(p):
            continue
        for l in open(p, encoding='utf-8', errors='replace'):
            m = KEY.match(l)
            if m:
                U.add(m.group(1))
    lines = [f"validated descriptors (A)          : {len(A)}",
             f"small-stub names (B)              : {len(B)}   B-A = {len(B - A)}",
             f"any-function names (C)            : {len(C)}   C-A = {len(C - A)}  C-B = {len(C - B)}",
             f"names only from BIG functions     : {len(big - B)}",
             f"user-cfg keys (U)                 : {len(U)}",
             f"  U not in A                      : {len(U - A)}",
             f"  U not in A and not in B         : {len(U - A - B)}",
             f"  U not in A/B/C                  : {len(U - A - B - C)}"]
    sample_big = sorted(n for n in (C - B) if NAME.match(n))
    lines.append("\n-- names referenced only from large functions (first 60) --")
    lines += ['  ' + n for n in sample_big[:60]]
    lines.append("\n-- user-cfg keys missing from A (these definitely exist) --")
    lines += ['  ' + n for n in sorted(U - A) if not n.startswith('setting.')]
    lines.append("\n-- user-cfg setting.* keys --")
    lines += ['  ' + n for n in sorted(n for n in U if n.startswith('setting.'))]
    txt = '\n'.join(lines)
    open(out, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    main()
