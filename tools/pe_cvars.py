#!/usr/bin/env python
"""Extract cvar-table context from a PE binary by locating pointers to strings.

Usage: python pe_cvars.py <exe> <out.txt> <string1> [string2 ...]
For each requested string it finds the string VA, then all 64-bit little-endian
occurrences of that VA in the file (i.e. structure fields pointing at the name),
and dumps the surrounding struct: hex + any qwords that dereference to printable
ASCII strings.
"""
import sys, struct, os

def parse_pe(path):
    d = open(path, 'rb').read()
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    assert d[e_lfanew:e_lfanew+4] == b'PE\0\0', 'not PE'
    coff = e_lfanew + 4
    nsec, = struct.unpack_from('<H', d, coff + 2)
    opt_size, = struct.unpack_from('<H', d, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from('<H', d, opt)
    if magic == 0x20b:
        image_base, = struct.unpack_from('<Q', d, opt + 24)
    else:
        image_base, = struct.unpack_from('<I', d, opt + 28)
    secs = []
    so = opt + opt_size
    for i in range(nsec):
        off = so + i * 40
        name = d[off:off+8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs.append((name, vaddr, vsize, rawptr, rawsize))
    return d, image_base, secs

def rva_to_off(secs, rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None

def off_to_rva(secs, off):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if rawptr <= off < rawptr + rawsize:
            return vaddr + (off - rawptr)
    return None

def read_str(d, secs, va, maxlen=200):
    off = rva_to_off(secs, va - None if False else (va))
    return None

def read_str_at(d, secs, image_base, va, maxlen=300):
    off = rva_to_off(secs, va - image_base)
    if off is None or off >= len(d):
        return None
    chunk = d[off:off+maxlen]
    s = []
    for b in chunk:
        if b == 0:
            break
        if 32 <= b < 127:
            s.append(chr(b))
        else:
            return None
    return ''.join(s) if len(s) >= 2 else None

def main():
    path, out = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    d, ib, secs = parse_pe(path)
    lines = []
    lines.append(f"# {path} image_base=0x{ib:x}")
    for sec in secs:
        lines.append(f"# sec {sec[0]} rva=0x{sec[1]:x} vsize=0x{sec[2]:x} raw=0x{sec[3]:x}+0x{sec[4]:x}")

    for nm in names:
        pat = nm.encode('ascii') + b'\0'
        start = 0
        found = []
        while True:
            i = d.find(pat, start)
            if i == -1:
                break
            rva = off_to_rva(secs, i)
            if rva is not None:
                found.append((i, rva, ib + rva))
            start = i + 1
        lines.append(f"\n===== '{nm}' string occurrences: {len(found)}")
        for off, rva, va in found:
            lines.append(f"  file 0x{off:x} rva 0x{rva:x} va 0x{va:x}")
            ptr = struct.pack('<Q', va)
            # find pointer occurrences (skip the string itself)
            pstart = 0
            cnt = 0
            while cnt < 6:
                j = d.find(ptr, pstart)
                if j == -1:
                    break
                pstart = j + 1
                if j == off:
                    continue
                cnt += 1
                lines.append(f"   --- ptr @file 0x{j:x} (rva 0x{(off_to_rva(secs,j) or 0):x})")
                lo = max(0, j - 8 * 6)
                hi = min(len(d), j + 8 * 14)
                blob = d[lo:hi]
                for k in range(0, len(blob), 8):
                    q = blob[k:k+8]
                    if len(q) < 8:
                        break
                    val, = struct.unpack('<Q', q)
                    desc = ''
                    s = read_str_at(d, secs, ib, val, 120)
                    if s:
                        desc = f' -> "{s}"'
                    else:
                        i32, = struct.unpack('<i', q[:4])
                        f32, = struct.unpack('<f', q[:4])
                        if abs(f32) > 1e-6 and abs(f32) < 1e9:
                            desc = f' (int {i32}, float {f32:.6g})'
                        elif val != 0:
                            desc = f' (hex 0x{val:x})'
                    lines.append(f"     +0x{(lo+k)-j:+d}: {q.hex(' ')} {desc}")
        if not found:
            lines.append("  (not found as ascii)")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:400]))
    print(f"\n[written to {out}]")

if __name__ == '__main__':
    main()
