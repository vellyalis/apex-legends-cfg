"""Compare what the mouse-sensitivity path and the pad-look path actually touch.

apex-analysis の静的結論「pad look と mouse sens に直接 xref が無い」を、
共有している *メモリ*（グローバル/状態）の観点で詰める。両関数を逆アセンブルして
RIP 相対で参照している絶対アドレスを取り出し、共通部分を出す。

usage: python xref_compare.py [--mouse 0x1409b6e10] [--pad 0x1408a5350]
"""
import argparse
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_MEM, X86_REG_RIP

IMAGE = 'C:/Program Files/EA Games/Apex/r5apex_dx12.exe'
BASE = 0x140000000
MOUSE_RVA = 0x9B6E10
MOUSE_SIZE = 0xB730
PAD_RVA = 0x8A5350
PAD_SIZE = 0x2000


def load_sections(path):
    data = open(path, 'rb').read()
    lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    assert data[lfanew:lfanew + 4] == b'PE\0\0'
    count = struct.unpack_from('<H', data, lfanew + 6)[0]
    opt_size = struct.unpack_from('<H', data, lfanew + 20)[0]
    sections = []
    offset = lfanew + 24 + opt_size
    for index in range(count):
        entry = offset + index * 40
        name = data[entry:entry + 8].rstrip(b'\0').decode('latin1')
        virtual_size, virtual_address = struct.unpack_from('<II', data, entry + 8)
        raw_size, raw_pointer = struct.unpack_from('<II', data, entry + 16)
        sections.append((name, virtual_address, virtual_size, raw_pointer, raw_size))
    return data, sections


def read_rva(data, sections, rva, size):
    for name, va, vsize, raw, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            start = raw + (rva - va)
            return data[start:start + size]
    raise SystemExit('rva 0x%X is not inside any section' % rva)


def references(data, sections, rva, size):
    code = read_rva(data, sections, rva, size)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    found = {}
    for insn in md.disasm(code, BASE + rva):
        for operand in insn.operands:
            if operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                target = insn.address + insn.size + operand.mem.disp
                found.setdefault(target, []).append('%s %s %s' % (hex(insn.address), insn.mnemonic, insn.op_str))
    return found


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mouse', default=hex(BASE + MOUSE_RVA))
    parser.add_argument('--pad', default=hex(BASE + PAD_RVA))
    args = parser.parse_args()
    mouse_rva = int(args.mouse, 16) - BASE
    pad_rva = int(args.pad, 16) - BASE
    if mouse_rva < 0 or pad_rva < 0:
        raise SystemExit('addresses must be given as absolute VAs (0x140...)')
    print('mouse VA=%s rva=0x%X / pad VA=%s rva=0x%X' % (args.mouse, mouse_rva, args.pad, pad_rva))

    data, sections = load_sections(IMAGE)
    mouse_refs = references(data, sections, mouse_rva, MOUSE_SIZE)
    pad_refs = references(data, sections, pad_rva, PAD_SIZE)
    print('mouse function: %d 個の RIP 相対参照 (%d bytes 走査)' % (len(mouse_refs), MOUSE_SIZE))
    print('pad   function: %d 個の RIP 相対参照 (%d bytes 走査)' % (len(pad_refs), PAD_SIZE))
    shared = sorted(set(mouse_refs) & set(pad_refs))
    print('=== 共通参照アドレス: %d 個 ===' % len(shared))
    for address in shared:
        print('  %s' % hex(address))
        for entry in mouse_refs[address][:2]:
            print('    mouse: %s' % entry)
        for entry in pad_refs[address][:2]:
            print('    pad  : %s' % entry)
    return 0


if __name__ == '__main__':
    sys.exit(main())
