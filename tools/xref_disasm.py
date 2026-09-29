#!/usr/bin/env python
"""Find RIP-relative code xrefs to strings/data in a PE and disassemble around them.

Usage: python xref_disasm.py <exe> <out.txt> <string-or-0xVA> [more...]

For each target: resolve VA (searching ascii string if not 0x-prefixed), find all
disp32 occurrences in .text such that code_va + insn_end + disp == target
(the disp field is assumed to be the last field of the instruction), then
disassemble a window around each hit with capstone, annotating RIP-relative
memory operands with the string/data they point at.
"""
import sys, struct, os
import numpy as np
import capstone

def parse_pe(path):
    d = open(path, 'rb').read()
    e_lfanew = struct.unpack_from('<I', d, 0x3c)[0]
    assert d[e_lfanew:e_lfanew+4] == b'PE\0\0'
    coff = e_lfanew + 4
    nsec, = struct.unpack_from('<H', d, coff + 2)
    opt_size, = struct.unpack_from('<H', d, coff + 16)
    opt = coff + 20
    magic, = struct.unpack_from('<H', d, opt)
    if magic == 0x20b:
        image_base, = struct.unpack_from('<Q', d, opt + 24)
    else:
        image_base, = struct.unpack_from('<I', d, opt + 28)
    secs = {}
    so = opt + opt_size
    order = []
    for i in range(nsec):
        off = so + i * 40
        name = d[off:off+8].rstrip(b'\0').decode('ascii', 'replace')
        vsize, vaddr = struct.unpack_from('<II', d, off + 8)
        rawsize, rawptr = struct.unpack_from('<II', d, off + 16)
        secs[name] = (vaddr, vsize, rawptr, rawsize)
        order.append(name)
    return d, image_base, secs, order

def rva_of_string(d, secs, s):
    pat = s.encode('ascii') + b'\0'
    i = d.find(pat)
    if i == -1:
        return None
    for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
        if rawptr <= i < rawptr + rawsize:
            return vaddr + (i - rawptr)
    return None

def read_cstr(d, secs, va, maxlen=160):
    for name, (vaddr, vsize, rawptr, rawsize) in secs.items():
        if vaddr <= va < vaddr + max(vsize, rawsize):
            off = rawptr + (va - vaddr)
            chunk = d[off:off+maxlen]
            out = []
            for b in chunk:
                if b == 0:
                    break
                if 32 <= b < 127:
                    out.append(chr(b))
                else:
                    return None
            return ''.join(out) if len(out) >= 2 else None
    return None

def main():
    path, out = sys.argv[1], sys.argv[2]
    targets = sys.argv[3:]
    d, ib, secs, order = parse_pe(path)
    text_va, text_vsize, text_ptr, text_size = secs['.text']
    text = d[text_ptr:text_ptr+text_size]
    b = np.frombuffer(text, dtype=np.uint8)
    w = np.lib.stride_tricks.sliding_window_view(b, 4)
    vals = w.view(np.uint32).ravel()

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    md.detail = True

    lines = [f"# {path} image_base=0x{ib:x} .text va=0x{ib+text_va:x} size=0x{text_size:x}"]
    for t in targets:
        if t.startswith('0x'):
            va = int(t, 16)
            label = f"0x{va:x}"
        else:
            rva = rva_of_string(d, secs, t)
            if rva is None:
                lines.append(f"\n===== {t}: NOT FOUND")
                continue
            va = ib + rva
            label = f'"{t}"'
        disp = (va - (ib + text_va + np.arange(len(vals), dtype=np.uint64) + 4)) & 0xffffffff
        mask = vals == disp.astype(np.uint32)
        idxs = np.nonzero(mask)[0]
        lines.append(f"\n===== {label}  va=0x{va:x}  xref_candidates={len(idxs)}")
        # group nearby hits (same function) - just cap at 40
        for k, idx in enumerate(idxs[:40]):
            insn_end_va = ib + text_va + int(idx) + 4
            start_va = insn_end_va - 5 - 24
            lines.append(f"\n--- xref #{k}: disp field @0x{ib+text_va+int(idx)+4-4:x} (roughly insn end 0x{insn_end_va:x})")
            buf_off = start_va - (ib + text_va)
            if buf_off < 0:
                buf_off = 0
            code = text[buf_off:buf_off+48]
            for insn in md.disasm(code, ib + text_va + buf_off):
                ann = ''
                for op in insn.operands:
                    if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_RIP:
                        tva = insn.address + insn.size + op.mem.disp
                        s = read_cstr(d, secs, tva)
                        if s:
                            ann = f'   ; -> "{s}"'
                        else:
                            ann = f'   ; -> 0x{tva:x}'
                mark = ' <== TARGET' if ann and ('-> "' + t.replace('0x','') in ann or f'0x{va:x}' in ann) else ''
                lines.append(f"  0x{insn.address:x}: {insn.mnemonic:<8} {insn.op_str}{ann}{mark}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write('\n'.join(lines))
    print('\n'.join(lines))
    print(f"[written {out}]")

if __name__ == '__main__':
    main()
