#!/usr/bin/env python
"""cvar object/handle inventory + reader-function graph (PE, x64).

For each cvar name:
  * find registration stub (function referencing the name string)
  * disassemble stub: track lea targets, stores of those regs into globals
  * per-cvar unique globals -> object VA (value stored) and handle global
Then xref object+handle from .text, map hit->function via .pdata, and build a
function -> {cvar} matrix. Prints:
  INVENTORY: name, object va, handle va, default/val strings seen in stub
  READERS:   per cvar, list of reader functions
  MATRIX:    functions touching >=2 cvars (esp. mixed mouse/gamepad/stream)

Usage: python cvar_graph.py <exe> <out.txt> <name1> [name2 ...]
"""
import sys, os, struct, bisect, re
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

def read_cstr(d, secs, va, maxlen=120, minlen=1):
    off = va2off(secs, va)
    if off is None: return None
    out = []
    for b in d[off:off+maxlen]:
        if b == 0: break
        if 32 <= b < 127: out.append(chr(b))
        else: return None
    return ''.join(out) if len(out) >= minlen else None

def parse_pdata(d, ib, secs):
    vaddr, vsize, rawptr, rawsize = secs['.pdata']
    funcs = []
    for i in range(0, rawsize // 12 * 12, 12):
        begin, end, unwind = struct.unpack_from('<III', d, rawptr + i)
        if end <= begin: continue
        funcs.append((ib + begin, ib + end))
    funcs.sort()
    return funcs

def main():
    path, out = sys.argv[1], sys.argv[2]
    names = sys.argv[3:]
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

    def func_of(va):
        i = bisect.bisect_right(starts, va) - 1
        if i >= 0 and funcs[i][0] <= va < funcs[i][1]:
            return funcs[i]
        return None

    def xref_hits(target_va, cap=4000):
        disp = (target_va - (text_abs + idxs_all + 4)) & 0xffffffff
        mask = vals == disp.astype(np.uint32)
        idx = np.nonzero(mask)[0]
        return [text_abs + int(i) + 4 for i in idx[:cap]], len(idx)

    def disasm(start, end):
        off = start - text_abs
        return list(md.disasm(text[off:end - text_abs], start))

    def ripref(insn):
        for op in insn.operands:
            if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                return insn.address + insn.size + op.mem.disp
        return None

    # ---- stage 1: stub inventory
    inv = {}          # name -> dict(obj, handle, data_targets, strings)
    all_data_targets = {}
    for nm in names:
        pat = nm.encode('ascii') + b'\0'
        i = d.find(pat)
        if i == -1:
            inv[nm] = {'error': 'string not found'}
            continue
        name_va = ib + off2va(secs, i)
        hits, n = xref_hits(name_va)
        stub = None
        for hva in hits:
            f = func_of(hva)
            if f:
                stub = f
                break
        if not stub:
            inv[nm] = {'error': f'no stub (hits={n})'}
            continue
        regs = {}
        globs = []      # (global_va, value_va)
        leas = []       # (insn_addr, dst_reg, target_va)
        strings = []
        consts = []
        for insn in disasm(*stub):
            t = ripref(insn)
            if t is not None:
                s = read_cstr(d, secs, t)
                if s is not None and insn.mnemonic != 'cmp':
                    strings.append(s)
                if insn.mnemonic == 'lea':
                    dst = insn.op_str.split(',')[0].strip()
                    regs[dst] = t
                    leas.append((insn.address, dst, t))
                elif insn.mnemonic == 'mov' and ',' in insn.op_str:
                    src = insn.op_str.split(',')[1].strip()
                    if re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', src) and src in regs:
                        globs.append((t, regs[src]))
                    else:
                        consts.append((t, src))
            else:
                m = re.fullmatch(r'(r[a-z0-9]+), (0x[0-9a-f]+)', insn.op_str)
                if insn.mnemonic == 'mov' and m and re.fullmatch(r'(r[a-z0-9]+|e[a-z]+)', m.group(1)):
                    try:
                        regs[m.group(1)] = int(m.group(2), 16)
                    except Exception:
                        pass
        inv[nm] = {'stub': stub, 'globs': globs, 'leas': leas,
                   'strings': sorted(set(strings)), 'consts': consts[:12]}
        for g, v in globs:
            all_data_targets.setdefault(g, set()).add(nm)

    lines = ["## INVENTORY"]
    for nm, info in inv.items():
        if 'error' in info:
            lines.append(f"{nm}: ERROR {info['error']}")
            continue
        lines.append(f"{nm}: stub 0x{info['stub'][0]:x} strings={info['strings'][:6]}")
        for g, v in info['globs']:
            cnt = len(all_data_targets.get(g, []))
            s = read_cstr(d, secs, v)
            lines.append(f"    glob 0x{g:x} <- 0x{v:x} [{sect_of(secs,v)}] {('str=' + repr(s)) if s else ''} (glob_used_by {cnt} cvars)")

    # ---- stage 2: per-cvar unique (object, handle)
    obj_map = {}   # cvar -> object va
    hdl_map = {}   # cvar -> handle global
    for nm, info in inv.items():
        if 'error' in info:
            continue
        cand = []
        for g, v in info['globs']:
            if len(all_data_targets.get(g, [])) != 1:
                continue  # shared global
            if read_cstr(d, secs, v) is not None:
                continue  # points at a string
            if sect_of(secs, v) not in ('.data',):
                continue
            cand.append((g, v))
        if cand:
            # object = the data the last unique global points to; handle = the global
            g, v = cand[-1]
            obj_map[nm] = v
            hdl_map[nm] = g
    lines.append("\n## UNIQUE OBJECTS")
    for nm in obj_map:
        lines.append(f"{nm}: object=0x{obj_map[nm]:x} handle=0x{hdl_map[nm]:x}")

    # ---- stage 3: readers
    va2cvar = {}
    for nm in obj_map:
        va2cvar[obj_map[nm]] = nm
        va2cvar[hdl_map[nm]] = nm
    func_cvars = {}
    lines.append("\n## READERS")
    for nm in obj_map:
        for va in (obj_map[nm], hdl_map[nm]):
            hits, n = xref_hits(va)
            hs = sorted(set(h for h in hits))
            lines.append(f"-- {nm} va=0x{va:x}: {n} hits")
            for h in hs[:60]:
                f = func_of(h)
                if not f:
                    lines.append(f"     0x{h:x} (no func)")
                    continue
                if f[0] == inv[nm]['stub'][0]:
                    lines.append(f"     0x{h:x} in stub")
                    continue
                func_cvars.setdefault(f, set()).add(nm)
                lines.append(f"     0x{h:x} in func 0x{f[0]:x}-0x{f[1]:x}")

    lines.append("\n## FUNCTIONS TOUCHING MULTIPLE CVARS")
    multi = {f: cs for f, cs in func_cvars.items() if len(cs) >= 2}
    for f, cs in sorted(multi.items()):
        lines.append(f"func 0x{f[0]:x}-0x{f[1]:x}: {sorted(cs)}")
    lines.append(f"\n(total reader funcs: {len(func_cvars)}, multi-cvar: {len(multi)})")

    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines[:400]))
    print(f"[written {out}]")

if __name__ == '__main__':
    main()
