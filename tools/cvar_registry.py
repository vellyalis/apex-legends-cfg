#!/usr/bin/env python
"""Enumerate every registered cvar descriptor in the exe.

Discovery: every cvar descriptor holds a qword pointer to its name string.
We locate all qwords (8-aligned, in read/write data sections) pointing at a
name-like ASCII string, then validate the struct around that pointer.

Usage:
  python cvar_registry.py probe   <exe> <cvar...>     # dump layout around known cvars
  python cvar_registry.py scan    <exe> <out.tsv>     # enumerate all registrations
"""
import sys, os, struct, re
import numpy as np

NAME_RE = re.compile(rb'[A-Za-z][A-Za-z0-9_]{2,63}\x00')
PRINT_RE = re.compile(rb'[ -~]{1,80}\x00')

RW_SECTIONS = ('.rdata', '.data', '.rodata')


def parse_pe(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    coff = e + 4
    nsec, = struct.unpack_from('<H', d, coff + 2)
    opt_size, = struct.unpack_from('<H', d, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from('<H', d, opt)
    ib, = struct.unpack_from('<Q', d, opt + 24) if magic == 0x20b else struct.unpack_from('<I', d, opt + 28)
    secs, order = {}, []
    so = opt + opt_size
    for i in range(nsec):
        off = so + i * 40
        name = d[off:off + 8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs[name] = (vaddr, vsize, rawptr, rawsize)
        order.append(name)
    return d, ib, secs, order


class PE:
    def __init__(self, path):
        self.path = path
        self.d, self.ib, self.secs, self.order = parse_pe(path)
        # VA ranges for target lookup
        self.ranges = []
        self.name_starts = set()
        for nm in self.order:
            vaddr, vsize, rawptr, rawsize = self.secs[nm]
            if nm not in RW_SECTIONS or rawsize == 0:
                continue
            blob = self.d[rawptr:rawptr + rawsize]
            self.ranges.append((self.ib + vaddr, self.ib + vaddr + rawsize, rawptr, nm))
            for m in NAME_RE.finditer(blob):
                self.name_starts.add(self.ib + vaddr + m.start())
        self.ranges.sort()

    def sect_of(self, va):
        for lo, hi, rawptr, nm in self.ranges:
            if lo <= va < hi:
                return nm
        return None

    def off_of(self, va):
        for lo, hi, rawptr, nm in self.ranges:
            if lo <= va < hi:
                return rawptr + (va - lo)
        return None

    def cstr(self, va, maxlen=80):
        off = self.off_of(va)
        if off is None:
            return None
        out = []
        for b in self.d[off:off + maxlen]:
            if b == 0:
                break
            if 32 <= b < 127:
                out.append(chr(b))
            else:
                return None
        return ''.join(out) if out else None

    def _all_qwords(self):
        if getattr(self, '_qws', None) is None:
            offs, vals = [], []
            for lo, hi, rawptr, nm in self.ranges:
                rawsize = hi - lo
                arr = np.frombuffer(self.d[rawptr:rawptr + rawsize], dtype=np.uint64)
                nz = np.nonzero(arr)[0]
                offs.append(rawptr + nz.astype(np.int64) * 8)
                vals.append(arr[nz])
            self._qws = (np.concatenate(offs), np.concatenate(vals))
        return self._qws

    def ptr_sites(self, targets=None):
        """Yield (offset, qword_value) for 8-aligned qwords in rw sections that
        point at a name-string start (targets=None) or at the given VA set."""
        offs, vals = self._all_qwords()
        if targets is None:
            tset = self.name_starts
        else:
            tset = targets
        mask = np.array([int(v) in tset for v in vals], dtype=bool)
        for o, v in zip(offs[mask], vals[mask]):
            yield int(o), int(v)


def probe(pe, names):
    for nm in names:
        pat = nm.encode() + b'\0'
        sva = None
        for m in re.finditer(re.escape(pat), pe.d):
            rva = None
            for lo, hi, rawptr, sec in pe.ranges:
                if rawptr <= m.start() < hi:
                    rva = lo + (m.start() - rawptr)
                    break
            if rva is not None:
                sva = rva
                break
        if sva is None:
            print(f"{nm}: string not found")
            continue
        print(f"\n===== {nm}  nameVA=0x{sva:x}")
        n = 0
        for off, v in pe.ptr_sites({sva}):
            if v != sva:
                continue
            n += 1
            va = pe.ib + off - pe.secs['.rdata'][0] if False else None
            print(f"  ptr@ file 0x{off:x}")
            for delta in range(-0x18, 0x78, 8):
                q = struct.unpack_from('<Q', pe.d, off + delta)[0]
                s = pe.cstr(q) if q else None
                tag = f'str="{s}"' if s else (f'0x{q:x}' if q else '0')
                i32 = struct.unpack_from('<i', pe.d, off + delta)[0]
                f32 = struct.unpack_from('<f', pe.d, off + delta)[0]
                extra = ''
                if not s and q and pe.sect_of(q) is None:
                    extra = f' (int {i32}, float {f32:.6g})'
                print(f"    {delta:+#06x}: {tag}{extra}")
            if n >= 4:
                break


FLAGS_NAMES = {
    0x1: 'UNREGISTERED', 0x2: 'DEVELOPMENTONLY', 0x4: 'GAMEDLL', 0x8: 'CLIENTDLL',
    0x10: 'HIDDEN', 0x20: 'PROTECTED', 0x40: 'SPONLY', 0x80: 'ARCHIVE',
    0x100: 'NOTIFY', 0x200: 'USERINFO', 0x400: 'PRINTABLEONLY', 0x800: 'UNLOGGED',
    0x1000: 'NEVER_AS_STRING', 0x2000: 'REPLICATED', 0x4000: 'CHEAT',
    0x8000: 'SSCLIENT', 0x10000: 'DEMO', 0x20000: 'DONTRECORD',
    0x40000: 'NOT_CONNECTED', 0x80000: 'ARCHIVE_XBOX', 0x100000: 'ACCESSIBLE_FROM_THREADS',
    0x200000: 'NOT_LOGGED', 0x400000: 'MATERIAL_SYSTEM_THREAD',
    0x800000: 'ALLOWED_IN_MATCHMAKING', 0x1000000: 'SCRIPTS_ONLY',
    0x2000000: 'CLIENTCMD_CAN_EXECUTE', 0x4000000: 'EXEC_ONLY',
    0x8000000: 'SERVER_EXEC', 0x10000000: 'ALLOW_CONNECTED',
    0x20000000: 'ALWAYS_QUERY', 0x40000000: 'NO_MIN_MAX_CHECK',
}


def flag_str(f):
    out = [n for bit, n in sorted(FLAGS_NAMES.items()) if f & bit]
    rem = f & ~sum(k for k in FLAGS_NAMES)
    if rem:
        out.append(f'0x{rem:x}')
    return '|'.join(out) if out else '0'


def scan(pe, out):
    rows = []
    for off, sva in pe.ptr_sites():
        # candidate descriptor: name pointer sits at +0x10
        base = off - 0x10
        if base < 0:
            continue
        try:
            pre = struct.unpack_from('<Q', pe.d, base + 0x00)[0]
            dflt32 = struct.unpack_from('<Q', pe.d, base + 0x28)[0]
            dflt40 = struct.unpack_from('<Q', pe.d, base + 0x40)[0]
            flags = struct.unpack_from('<i', pe.d, base + 0x50)[0]
            fval = struct.unpack_from('<f', pe.d, base + 0x58)[0]
            bval = struct.unpack_from('<i', pe.d, base + 0x5c)[0]
            fmin = struct.unpack_from('<f', pe.d, base + 0x64)[0]
            fmax = struct.unpack_from('<f', pe.d, base + 0x68)[0]
        except struct.error:
            continue
        if flags == 0:
            continue
        name = pe.cstr(sva)
        ds = pe.cstr(dflt32) if pe.sect_of(dflt32) else None
        ds2 = pe.cstr(dflt40) if pe.sect_of(dflt40) else None
        sec = pe.sect_of(pe.ib + base - 0)  # section of descriptor itself
        rows.append((name, off, sec, ds, ds2, flags, fval, bval, fmin, fmax, dflt32, dflt40))
    # keep one row per name (first), report duplicates count
    seen = {}
    for r in rows:
        seen.setdefault(r[0], []).append(r)
    with open(out, 'w', encoding='utf-8') as f:
        f.write("# cvar\tdesc_off\tsection\tdefault(+0x28)\tdefault(+0x40)\tflags\tflags_decoded\tfloat+0x58\tint+0x5c\tmin+0x64\tmax+0x68\tn_sites\n")
        for name in sorted(seen):
            r = seen[name][0]
            f.write(f"{name}\t0x{r[1]:x}\t{r[2]}\t{r[3] or ''}\t{r[4] or ''}\t0x{r[5]:x}\t{flag_str(r[5])}\t"
                    f"{r[6]:.6g}\t{r[7]}\t{r[8]:.6g}\t{r[9]:.6g}\t{len(seen[name])}\n")
    print(f"{len(seen)} unique names from {len(rows)} candidate sites -> {out}")


def main():
    mode = sys.argv[1]
    pe = PE(sys.argv[2])
    if mode == 'probe':
        probe(pe, sys.argv[3:])
    elif mode == 'scan':
        scan(pe, sys.argv[3])


if __name__ == '__main__':
    main()
