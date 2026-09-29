#!/usr/bin/env python
"""Dump the raw struct at a given VA (hex qwords + string decode) for cvar
descriptor layout verification.

Usage: python dump_va.py <exe> <va_hex> [bytes]
"""
import sys, struct
from cvar_registry import PE


def main():
    pe = PE(sys.argv[1])
    va = int(sys.argv[2], 16)
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 0x90
    off = pe.off_of(va)
    print(f"VA 0x{va:x} -> file 0x{off:x} section {pe.sect_of(va)}")
    for d in range(0, n, 8):
        q = struct.unpack_from('<Q', pe.d, off + d)[0]
        s = pe.cstr(q) if q else None
        i32 = struct.unpack_from('<i', pe.d, off + d)[0]
        f32 = struct.unpack_from('<f', pe.d, off + d)[0]
        f64 = struct.unpack_from('<d', pe.d, off + d)[0]
        s2 = pe.cstr(q) if (q and pe.sect_of(q)) else None
        if s2:
            tag = f'str "{s2}"'
        elif pe.sect_of(q):
            tag = f'VA 0x{q:x} [{pe.sect_of(q)}]'
        elif q:
            tag = f'raw 0x{q:x} (i32 {i32}, f32 {f32:.6g}, f64 {f64:.6g})'
        else:
            tag = '0'
        print(f"  +0x{d:03x}: {tag}")


if __name__ == '__main__':
    main()
