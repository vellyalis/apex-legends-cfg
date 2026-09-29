#!/usr/bin/env python
"""dump_extract.py - minidump から任意の仮想アドレスの値を取り出す（Apex 実行時メモリ抽出用）

使い方:
  dump_extract.py <dump> --apex                 # Apex の既知アドレスをレポート
  dump_extract.py <dump> --read 0x140000000:16  # 生読み（hexdump）
"""
import os
import struct
import sys


class Dump:
    def __init__(self, path):
        with open(path, 'rb') as handle:
            self.data = handle.read()
        if self.data[:4] != b'MDMP':
            raise SystemExit('minidump ではありません: %s' % path)
        streams = struct.unpack_from('<I', self.data, 8)[0]
        directory = struct.unpack_from('<I', self.data, 12)[0]
        self.ranges = []
        self.modules = {}
        for index in range(streams):
            stream_type, _size, rva = struct.unpack_from('<III', self.data, directory + index * 12)
            if stream_type == 9:
                count, base = struct.unpack_from('<QQ', self.data, rva)
                cursor = base
                for j in range(count):
                    start, length = struct.unpack_from('<QQ', self.data, rva + 16 + j * 16)
                    self.ranges.append((start, length, cursor))
                    cursor += length
            elif stream_type == 5:
                count = struct.unpack_from('<I', self.data, rva)[0]
                for j in range(count):
                    start, size, data_rva = struct.unpack_from('<QII', self.data, rva + 4 + j * 16)
                    self.ranges.append((start, size, data_rva))
            elif stream_type == 4:
                count = struct.unpack_from('<I', self.data, rva)[0]
                for j in range(count):
                    entry = rva + 4 + j * 108
                    base, _size = struct.unpack_from('<QI', self.data, entry)
                    name_rva = struct.unpack_from('<I', self.data, entry + 20)[0]
                    name_len = struct.unpack_from('<I', self.data, name_rva)[0]
                    name = self.data[name_rva + 4:name_rva + 4 + name_len].decode('utf-16-le', 'replace')
                    self.modules[os.path.basename(name).lower()] = base

    def find(self, va):
        for start, length, offset in self.ranges:
            if start <= va < start + length:
                return offset + (va - start)
        return None

    def read(self, va, size):
        offset = self.find(va)
        return None if offset is None else self.data[offset:offset + size]

    def qword(self, va):
        raw = self.read(va, 8)
        return None if raw is None else struct.unpack('<Q', raw)[0]

    def dword(self, va):
        raw = self.read(va, 4)
        return None if raw is None else struct.unpack('<I', raw)[0]

    def flt(self, va):
        raw = self.read(va, 4)
        return None if raw is None else struct.unpack('<f', raw)[0]

    def module_base(self, name):
        return self.modules.get(name.lower())


def apex_report(dump):
    base = dump.module_base('r5apex_dx12.exe')
    print('モジュール基数 r5apex_dx12.exe = %s' % (hex(base) if base else '不明'))
    if not base:
        return 1
    def va(rva):
        return base + (rva - 0x140000000)
    print('共有定数 0x1419C79F4 =', dump.flt(va(0x1419C79F4)))
    print('クランプ定数 0x145418CD8 (maxss の下限) =', dump.flt(va(0x145418CD8)))
    for label, rva in (('共有ゲートobj', 0x1426BDFF8), ('スカラー源A', 0x142530A48),
                       ('スカラー源B', 0x142530AD8)):
        pointer = dump.qword(va(rva))
        if pointer:
            print('%s: ptr=%s  [+0x5C]=%s' % (label, hex(pointer), dump.dword(pointer + 0x5C)))
    for label, rva in (('GetRawInputData', 0x143364358), ('RegisterRawInputDevices', 0x143364360),
                       ('XInput系1', 0x143364368), ('XInput系2', 0x143364370),
                       ('GetRawInputBuffer', 0x143364378)):
        print('解決済みAPI %-24s = %s' % (label, hex(dump.qword(va(rva)) or 0)))
    print('感度2段テーブル 0x142530AA0 (先頭 9 qword):')
    for k in range(9):
        entry = dump.qword(va(0x142530AA0) + k * 8)
        print('   [%d] 0x%X' % (k, entry or 0))
    return 0


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    dump = Dump(sys.argv[1])
    if sys.argv[2] == '--apex':
        return apex_report(dump)
    if sys.argv[2] == '--read':
        address, _, size = sys.argv[3].partition(':')
        raw = dump.read(int(address, 0), int(size or '16', 0))
        print('None' if raw is None else raw.hex())
        return 0
    raise SystemExit(__doc__)


if __name__ == '__main__':
    sys.exit(main())
