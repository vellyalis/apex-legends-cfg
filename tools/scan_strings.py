#!/usr/bin/env python
"""Scan a binary (exe/rpak) for ASCII strings, group by keyword.

Usage: python scan_strings.py <binary> <out.txt> [keyword ...]
Writes: header + per-keyword section with sorted unique strings (capped).
Also extracts 'setting.*' keys and cvar-like tokens for Apex analysis.
"""
import re, sys, os

def strings(path, minlen=4):
    data = open(path, 'rb').read()
    pat = rb'[\x20-\x7e]{%d,}' % minlen
    return [s.decode('ascii') for s in re.findall(pat, data)]

def main():
    path, out = sys.argv[1], sys.argv[2]
    keys = sys.argv[3:] or []
    dec = strings(path)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"# source: {path}\n# total ascii strings (>=4): {len(dec)}\n\n")
        sett = sorted(set(s for s in dec if 'setting.' in s))
        f.write(f"### 'setting.' keys: {len(sett)}\n")
        for s in sett: f.write(s + "\n")
        f.write("\n")
        for k in keys:
            hits = sorted(set(s for s in dec if k.lower() in s.lower()))
            f.write(f"### '{k}': {len(hits)}\n")
            for h in hits[:600]: f.write(h + "\n")
            f.write("\n")
    print(f"{path}: {len(dec)} strings -> {out}")

if __name__ == '__main__':
    main()
