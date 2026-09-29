#!/usr/bin/env python
"""Report: call-site context for two functions, and reader functions of a cvar
object discovered from its name string's registration stub.

Usage: python callsite.py <exe> <out.txt>
"""
import struct, capstone, bisect, re, sys
import numpy as np

p = r"C:\Program Files\EA Games\Apex\r5apex_dx12.exe"
out = sys.argv[2] if len(sys.argv) > 2 else "evidence/callsite.txt"
d = open(p, 'rb').read(); ib = 0x140000000
e = struct.unpack_from('<I', d, 0x3c)[0]; coff = e + 4
nsec, = struct.unpack_from('<H', d, coff + 2); opt_size, = struct.unpack_from('<H', d, coff + 16); opt = coff + 20
secs = {}
for i in range(nsec):
    off = opt + opt_size + i * 40
    nm = d[off:off+8].rstrip(b'\0').decode()
    vs, va = struct.unpack_from('<II', d, off + 8); rs, rp = struct.unpack_from('<II', d, off + 16)
    secs[nm] = (va, vs, rp, rs)
tva, tvs, tp, ts = secs['.text']; text = d[tp:tp+ts]; tabs = ib + tva
arr = np.frombuffer(text, dtype=np.uint8)
vals = np.lib.stride_tricks.sliding_window_view(arr, 4).view(np.uint32).ravel()
base = ((tabs + 4 + np.arange(len(vals), dtype=np.uint64)) & 0xffffffff).astype(np.uint32)
np.seterr(over='ignore')
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64); md.detail = True
pva, pvs, prp, prs = secs['.pdata']
funcs = []
for i in range(0, prs//12*12, 12):
    b, en, u = struct.unpack_from('<III', d, prp+i)
    if en > b: funcs.append((ib+b, ib+en))
funcs.sort(); starts = [f[0] for f in funcs]

def func_of(va):
    i = bisect.bisect_right(starts, va) - 1
    return funcs[i] if i >= 0 and funcs[i][0] <= va < funcs[i][1] else None

def cstr(va, n=140):
    rva = va - ib
    for nm, (va0, vs, rp0, rs) in secs.items():
        if va0 <= rva < va0 + rs:
            o = rp0 + (rva - va0); out2 = []
            for b in d[o:o+n]:
                if b == 0: break
                if 32 <= b < 127: out2.append(chr(b))
                else: return None
            return ''.join(out2) if out2 else None
    return None

def xrefs(va):
    diff = np.uint32(va & 0xffffffff) - base
    idx = np.nonzero(vals == diff)[0]
    return [tabs + int(i) + 4 for i in idx]

def disasm(s, en):
    return list(md.disasm(text[s-tabs:en-tabs], s))

lines = []
# (a) call sites
for label, fva in (('MOUSE_SCALE 0x1409b6e10', 0x1409b6e10), ('PAD_LOOK 0x1408a5350', 0x1408a5350)):
    lines.append(f"\n##### call sites of {label}")
    for h in xrefs(fva):
        f = func_of(h)
        lines.append(f"  caller func 0x{f[0]:x}-0x{f[1]:x} callsite 0x{h:x}")
        lo = max(f[0], h - 0x60)
        for insn in disasm(lo, min(f[1], h + 8)):
            ann = ''
            for op in insn.operands:
                if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                    t = insn.address + insn.size + op.mem.disp
                    s = cstr(t)
                    if s: ann = f'   ; "{s}"'
            lines.append(f"    0x{insn.address:x}: {insn.mnemonic} {insn.op_str}{ann}")

# (b) readers of video cvars
for name in ('mat_forceaniso', 'stream_memory'):
    nva = None
    i = d.find(name.encode() + b'\0')
    if i == -1:
        lines.append(f"\n##### {name}: string not found"); continue
    rva = None
    for nm, (va0, vs, rp0, rs) in secs.items():
        if rp0 <= i < rp0 + rs:
            rva = va0 + (i - rp0)
    nva = ib + rva
    cands = []
    for h in xrefs(nva):
        f = func_of(h)
        if f and (f[1]-f[0]) < 0x600: cands.append(f)
    lines.append(f"\n##### {name} name_va=0x{nva:x} stubs={len(cands)}")
    if not cands: continue
    stub = sorted(cands, key=lambda f: f[1]-f[0])[0]
    obj = None; handle = None
    regs = {}
    for insn in disasm(*stub):
        t = None
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                t = insn.address + insn.size + op.mem.disp
        if t is None: continue
        if insn.mnemonic == 'lea':
            dst = insn.op_str.split(',')[0].strip(); regs[dst] = t
        elif insn.mnemonic == 'mov' and ',' in insn.op_str:
            src = insn.op_str.split(',')[1].strip()
            if re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', src) and src in regs:
                v = regs[src]
                if cstr(v) is None and 0x14200000 < (v - ib) < 0x2800000:
                    obj, handle = v, t
    lines.append(f"  stub 0x{stub[0]:x} obj={hex(obj) if obj else None} handle={hex(handle) if handle else None}")
    if obj:
        fs = {}
        for h in xrefs(obj) + (xrefs(handle) if handle else []):
            f = func_of(h)
            if f and f[0] != stub[0]: fs.setdefault(f, 0); fs[f] += 1
        lines.append(f"  readers: {len(fs)}")
        for f, n in sorted(fs.items()):
            strs = []
            for insn in disasm(*f):
                for op in insn.operands:
                    if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                        s = cstr(insn.address + insn.size + op.mem.disp)
                        if s and s not in strs: strs.append(s)
            lines.append(f"    func 0x{f[0]:x}-0x{f[1]:x} ({n}) strs={strs[:8]}")
open(out, 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
