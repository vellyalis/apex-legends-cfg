#!/usr/bin/env python
"""Extract (cvar name -> default string) pairs from the exe .rdata string pool.

Layout observed: b"<name>\\0" then zero padding (0-7 bytes), then b"<default>\\0"
for many entries; entries are 8-byte aligned. Some names have no adjacent
default (typed default stored elsewhere) - those are emitted with "".

Usage: python cvar_table.py <exe> <out.txt>
"""
import sys, re

NAME_RE = re.compile(rb'^[A-Za-z][A-Za-z0-9_]{1,63}$')
VALUE_HINT = re.compile(rb'^[A-Za-z0-9_.%\-+ "#/]{1,63}$')

def main():
    path, out = sys.argv[1], sys.argv[2]
    d = open(path, 'rb').read()
    # search the whole file; names+values are inline ascii in .rdata/.data
    results = []
    i = 0
    n = len(d)
    while i < n:
        # find a candidate name start
        j = d.find(b'\0', i)
        if j == -1:
            break
        k = d.find(b'\0', j + 1)
        if k == -1:
            break
        name = d[i:j] if j > i else b''
        i = j + 1
        if not name or not NAME_RE.match(name):
            continue
        # next token after padding zeros (0..8)
        p = j + 1
        pad = 0
        while p < n and d[p] == 0 and pad < 8:
            p += 1; pad += 1
        q = d.find(b'\0', p)
        if q == -1 or q - p > 80:
            continue
        val = d[p:q]
        if val == b'' or not VALUE_HINT.match(val):
            results.append((name.decode(), ''))
            continue
        results.append((name.decode(), val.decode()))
    # dedupe, keep first
    seen = {}
    for name, val in results:
        if name not in seen:
            seen[name] = val
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"# {path}: {len(seen)} name/value pairs (heuristic)\n")
        for name in sorted(seen):
            f.write(f"{name}\t{seen[name]}\n")
    print(f"{path}: {len(seen)} pairs -> {out}")

if __name__ == '__main__':
    main()
