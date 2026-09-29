#!/usr/bin/env python
"""Dump printable strings inside a file-offset region, with offsets.

Usage: python region_strings.py <file> <lo_hex> <hi_hex> [minlen]
"""
import sys, re

def main():
    path = sys.argv[1]
    lo = int(sys.argv[2], 16); hi = int(sys.argv[3], 16)
    minlen = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    d = open(path, 'rb').read()[lo:hi]
    for m in re.finditer(rb'[\x20-\x7e]{%d,}' % minlen, d):
        print(f"0x{lo + m.start():08x}  {m.group().decode('ascii')}")

if __name__ == '__main__':
    main()
