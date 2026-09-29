#!/usr/bin/env python
"""Map cvar-name strings to the functions that reference them (PE, x64).

Uses:
  * .pdata RUNTIME_FUNCTION entries -> exact function boundaries
  * RIP-relative disp32 heuristic  -> code xrefs to string VAs
  * 8-byte imm64 scan in .text     -> mov reg, imm64 style references

Usage: python func_xref.py <exe> <out_dir> [name1 name2 ...]
Writes:
  <out_dir>/function_strings.tsv  : func_va \t list-of-referenced-strings
  <out_dir>/asm/<funcva>_<tag>.txt: full disassembly of candidate functions
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

def read_cstr(d, secs, va, maxlen=200):
    off = va2off(secs, va)
    if off is None:
        return None
    out = []
    for b in d[off:off+maxlen]:
        if b == 0:
            break
        if 32 <= b < 127:
            out.append(chr(b))
        else:
            return None
    return ''.join(out) if len(out) >= 2 else None

def parse_pdata(d, ib, secs):
    vaddr, vsize, rawptr, rawsize = secs['.pdata']
    funcs = []
    for i in range(0, rawsize // 12 * 12, 12):
        begin, end, unwind = struct.unpack_from('<III', d, rawptr + i)
        if begin == 0 and end == 0:
            continue
        if begin >= vsize * 4 or end <= begin:
            continue
        funcs.append((ib + begin, ib + end))
    funcs.sort()
    return funcs

def find_func(funcs, va):
    starts = [f[0] for f in funcs]
    i = bisect.bisect_right(starts, va) - 1
    if i >= 0 and funcs[i][0] <= va < funcs[i][1]:
        return funcs[i]
    return None

def main():
    path, outdir = sys.argv[1], sys.argv[2]
    targets = sys.argv[3:] or ["mouse_sensitivity", "gamepad_look_curve"]
    os.makedirs(outdir, exist_ok=True)
    asmdir = os.path.join(outdir, 'asm')
    os.makedirs(asmdir, exist_ok=True)
    d, ib, secs, order = parse_pe(path)
    text_va, text_vsize, text_ptr, text_size = secs['.text']
    text = d[text_ptr:text_ptr+text_size]
    b = np.frombuffer(text, dtype=np.uint8)
    w = np.lib.stride_tricks.sliding_window_view(b, 4)
    vals = w.view(np.uint32).ravel()
    funcs = parse_pdata(d, ib, secs)
    print(f"functions in .pdata: {len(funcs)}")

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = False

    text_abs = ib + text_va
    target_va = {}
    for t in targets:
        pat = t.encode('ascii') + b'\0'
        i = d.find(pat)
        if i == -1:
            print(f"  ! string not found: {t}")
            continue
        rva = off2va(secs, i)
        if rva is None:
            continue
        target_va[t] = ib + rva

    # hits per target -> function
    func_targets = {}
    for t, va in target_va.items():
        disp = (va - (text_abs + np.arange(len(vals), dtype=np.uint64) + 4)) & 0xffffffff
        mask = vals == disp.astype(np.uint32)
        idxs = np.nonzero(mask)[0]
        imm = struct.pack('<Q', va)
        extra = []
        p = text.find(imm)
        while p != -1:
            extra.append(p)
            p = text.find(imm, p + 1)
        for idx in list(idxs) + extra:
            hit_va = text_abs + int(idx) + 4
            fn = find_func(funcs, hit_va)
            if fn:
                func_targets.setdefault(fn, set()).add(t)
    print(f"functions referencing targets: {len(func_targets)}")

    # disassemble each candidate function fully; collect referenced strings
    rows = []
    for fn, tgts in sorted(func_targets.items()):
        start, end = fn
        off = start - text_abs
        code = text[off:end - text_abs]
        refs = []
        for insn in md.disasm(code, start):
            mn = insn.op_str
            if 'rip +' in mn or 'rip -' in mn:
                try:
                    disp = int(mn.split('rip')[1].strip().split(']')[0].replace('+','').replace('- ','-'), 0)
                    rva = insn.address + insn.size + disp
                    s = read_cstr(d, secs, rva)
                    if s:
                        refs.append(s)
                except Exception:
                    pass
        tag = ','.join(sorted(tgts))[:80].replace('/', '_')
        rows.append((start, sorted(set(refs)), sorted(tgts)))
        with open(os.path.join(asmdir, f"{start:x}.txt"), 'w', encoding='utf-8') as f:
            f.write(f"# func 0x{start:x}-0x{end:x} target_hits={sorted(tgts)}\n")
            for insn in md.disasm(code, start):
                ann = ''
                if 'rip +' in insn.op_str:
                    try:
                        disp = int(insn.op_str.split('rip')[1].strip().split(']')[0].replace('+',''), 0)
                        rva = insn.address + insn.size + disp
                        s = read_cstr(d, secs, rva)
                        if s:
                            ann = f'   ; "{s}"'
                    except Exception:
                        pass
                f.write(f"0x{insn.address:x}: {insn.mnemonic} {insn.op_str}{ann}\n")

    with open(os.path.join(outdir, 'function_strings.tsv'), 'w', encoding='utf-8') as f:
        f.write("func_va\ttarget_hits\treferenced_strings\n")
        for start, refs, tgts in rows:
            f.write(f"0x{start:x}\t{','.join(tgts)}\t{' | '.join(refs[:120])}\n")
    print(f"wrote {len(rows)} functions -> {outdir}")

    # cross-group summary
    pad = [t for t in targets if t.startswith('gamepad')]
    mouse = [t for t in targets if t.startswith('mouse') or t.startswith('raw_input') or t.startswith('cl_use_raw')]
    for start, refs, tgts in rows:
        has_pad = any(t.startswith('gamepad') for t in tgts)
        has_mouse = any(t.startswith('mouse') or t.startswith('raw_input') or t.startswith('cl_use_raw') for t in tgts)
        if has_pad and has_mouse:
            print(f"  !! MIXED pad+mouse: 0x{start:x} {sorted(tgts)}")

if __name__ == '__main__':
    main()
