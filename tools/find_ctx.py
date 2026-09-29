#!/usr/bin/env python
"""Dump hex+ascii context windows around byte patterns in a binary.

Usage: python find_ctx.py <binary> <out.txt> <pattern1> [pattern2 ...]
Patterns are matched as bytes; prefix with u16: for UTF-16LE, jp: for Japanese UTF-8.
"""
import sys, os, re

def windows(data, pat, pad=192):
    out = []
    i = data.find(pat)
    while i != -1:
        s = max(0, i - pad); e = min(len(data), i + len(pat) + pad)
        out.append((i, data[s:e]))
        i = data.find(pat, i + 1)
        if len(out) > 200:
            break
    return out

def fmt(off, chunk):
    lines = [f"@0x{off:x}"]
    for j in range(0, len(chunk), 16):
        row = chunk[j:j+16]
        hexs = ' '.join(f'{b:02x}' for b in row)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in row)
        lines.append(f"  {hexs:<48} {asc}")
    return '\n'.join(lines)

def main():
    path, out = sys.argv[1], sys.argv[2]
    pats = sys.argv[3:]
    data = open(path, 'rb').read()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', errors='replace') as f:
        f.write(f"# {path}  size={len(data)}\n\n")
        for p in pats:
            if p.startswith('u16:'):
                pat = p[4:].encode('utf-16-le'); label = p
            elif p.startswith('jp:'):
                pat = p[3:].encode('utf-8'); label = p
            else:
                pat = p.encode('ascii'); label = p
            ws = windows(data, pat)
            f.write(f"===== {label}  hits={len(ws)}\n")
            for off, chunk in ws[:12]:
                f.write(fmt(off, chunk) + "\n\n")
            f.write("\n")
            print(f"{label}: hits={len(ws)}")

if __name__ == '__main__':
    main()
