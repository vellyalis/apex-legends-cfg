#!/usr/bin/env python
"""For a set of cvars: analyse registration stub, then find reader functions.

Usage: python readers.py <exe> <outdir> <cvar> [cvar2 ...]

Step 1: locate stub (function referencing the cvar name string).
Step 2: disassemble stub, track `lea reg,[rip+d]` and the stores of those regs
        into globals -> candidate object / handle data addresses; collect
        integer/float constants stored.
Step 3: xref object+handle VAs from .text (disp32 heuristic), map to functions
        via .pdata, disassemble readers, and list every RIP-relative target
        (string or data) each reader touches, annotating known cvar objects.
"""
import sys, os, struct, bisect
import numpy as np
import capstone

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
        name = d[off:off+8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs[name] = (vaddr, vsize, rawptr, rawsize)
        order.append(name)
    return d, ib, secs, order

def va2off(secs, va):
    for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
        if vaddr <= va < vaddr + max(vsize, rawsize):
            return rawptr + (va - vaddr)
    return None

def off2va(secs, off):
    for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
        if rawptr <= off < rawptr + rawsize:
            return vaddr + (off - rawptr)
    return None

def sect_of(secs, va):
    for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
        if vaddr <= va < vaddr + max(vsize, rawsize):
            return name
    return '?'

def read_cstr(d, secs, va, maxlen=200):
    off = va2off(secs, va)
    if off is None: return None
    out = []
    for b in d[off:off+maxlen]:
        if b == 0: break
        if 32 <= b < 127: out.append(chr(b))
        else: return None
    return ''.join(out) if len(out) >= 2 else None

def parse_pdata(d, ib, secs):
    vaddr, vsize, rawptr, rawsize = secs['.pdata']
    funcs = []
    for i in range(0, rawsize // 12 * 12, 12):
        begin, end, unwind = struct.unpack_from('<III', d, rawptr + i)
        if begin == 0 and end == 0: continue
        if end <= begin: continue
        funcs.append((ib + begin, ib + end))
    funcs.sort()
    return funcs

def main():
    path, outdir = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
    os.makedirs(outdir, exist_ok=True)
    d, ib, secs, order = parse_pe(path)
    text_va, text_vsize, text_ptr, text_size = secs['.text']
    text = d[text_ptr:text_ptr+text_size]
    text_abs = ib + text_va
    arr = np.frombuffer(text, dtype=np.uint8)
    w = np.lib.stride_tricks.sliding_window_view(arr, 4)
    vals = w.view(np.uint32).ravel()
    idxs_all = np.arange(len(vals), dtype=np.uint64)
    funcs = parse_pdata(d, ib, secs)
    starts = [f[0] for f in funcs]

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    def xref_funcs(target_va):
        disp = (target_va - (text_abs + idxs_all + 4)) & 0xffffffff
        mask = vals == disp.astype(np.uint32)
        out = set()
        for idx in np.nonzero(mask)[0]:
            hit = text_abs + int(idx) + 4
            i = bisect.bisect_right(starts, hit) - 1
            if i >= 0 and funcs[i][0] <= hit < funcs[i][1]:
                out.add(funcs[i])
        return out

    def disasm_range(start, end):
        off = start - text_abs
        return list(md.disasm(text[off:end - text_abs], start))

    def scope_insn(insn):
        """Return (target, kind) for a RIP-relative memory operand."""
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                tva = insn.address + insn.size + op.mem.disp
                return tva, op.access
        return None, None

    report = []
    cvar_objects = {}
    for nm in names:
        pat = nm.encode('ascii') + b'\0'
        i = d.find(pat)
        if i == -1:
            report.append(f"===== {nm}: string not found")
            continue
        rva = off2va(secs, i)
        name_va = ib + rva
        stubs = xref_funcs(name_va)
        report.append(f"\n===== {nm}  name_va=0x{name_va:x}  stubs={len(stubs)}")
        if not stubs:
            continue
        stub = sorted(stubs)[0]
        report.append(f"  stub: 0x{stub[0]:x}-0x{stub[1]:x}")
        regs = {}
        handles = {}
        consts = []
        for insn in disasm_range(*stub):
            tva, kind = scope_insn(insn)
            if tva is None:
                continue
            s = read_cstr(d, secs, tva)
            sec = sect_of(secs, tva)
            note = ''
            if s:
                note = f' "{s}"'
            if insn.mnemonic == 'lea':
                # dest reg
                try:
                    regname = insn.op_str.split(',')[0].strip()
                    regs[regname] = tva
                except Exception:
                    pass
                report.append(f"    0x{insn.address:x}: lea {insn.op_str}   ; 0x{tva:x} [{sec}]{note}")
            elif insn.mnemonic == 'mov' and ',' in insn.op_str:
                src = insn.op_str.split(',')[1].strip()
                if re_src_reg(src) and src in regs:
                    handles[src] = (tva, regs[src])
                    report.append(f"    0x{insn.address:x}: mov [0x{tva:x}] <- {src}=0x{regs[src]:x}  (handle for object 0x{regs[src]:x}) [{sec}]{note}")
                else:
                    report.append(f"    0x{insn.address:x}: {insn.mnemonic} {insn.op_str}   ; 0x{tva:x} [{sec}]{note}")
            else:
                report.append(f"    0x{insn.address:x}: {insn.mnemonic} {insn.op_str}   ; 0x{tva:x} [{sec}]{note}")
        objs = sorted(set(v for _, v in handles.values()))
        hs = sorted(set(k for k, _ in handles.values()))
        cvar_objects[nm] = {'objects': objs, 'handles': [h[0] for h in handles.values()]}
        report.append(f"  => object VA(s): {[hex(x) for x in objs]}  handle VA(s): {[hex(x) for x in cvar_objects[nm]['handles']]}")

    # readers
    for nm, info in cvar_objects.items():
        for kindname in ('objects', 'handles'):
            for va in info[kindname]:
                rf = xref_funcs(va)
                report.append(f"\n----- readers of {nm} {kindname[:-1]} 0x{va:x}: {len(rf)} funcs")
                for f in sorted(rf):
                    report.append(f"    func 0x{f[0]:x}-0x{f[1]:x}")
                    untouched = []
                    for insn in disasm_range(*f):
                        tva, k = scope_insn(insn)
                        if tva is None: continue
                        s = read_cstr(d, secs, tva)
                        untouched.append((insn.address, insn.mnemonic, insn.op_str, tva, s))
                    # only list unique data/string targets
                    seen = set()
                    for addr, mn, ops, tva, s in untouched:
                        key = (tva, s)
                        if key in seen: continue
                        seen.add(key)
                        if s:
                            report.append(f"        @0x{addr:x} {mn} {ops}  -> \"{s}\"")
                        elif tva in [x for xx in cvar_objects.values() for x in xx['objects']] or tva in [x for xx in cvar_objects.values() for x in xx['handles']]:
                            who = [k2 for k2, v2 in cvar_objects.items() if tva in v2['objects'] or tva in v2['handles']]
                            report.append(f"        @0x{addr:x} {mn} {ops}  -> [cvar:{','.join(who)}]")
    out = os.path.join(outdir, 'readers_report.txt')
    open(out, 'w', encoding='utf-8').write('\n'.join(report))
    print('\n'.join(report))
    print(f"[written {out}]")

import re
def re_src_reg(s):
    return re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', s) is not None

if __name__ == '__main__':
    main()
