#!/usr/bin/env python
"""Where does a cvar name exist? Search the exe AND every shipped module.

Usage: python name_exists.py <root_install_dir> <names_file> <out.tsv>
names_file: one name per line.
Searches every .exe/.dll under the install root (size >= 200KB) for
"<name>\0" case-sensitively and case-insensitively.
"""
import sys, os, re

ROOT_DEFAULT = r'C:\Program Files\EA Games\Apex'


def main():
    root = sys.argv[1] if sys.argv[1] != '-' else ROOT_DEFAULT
    names = [l.strip() for l in open(sys.argv[2], encoding='utf-8') if l.strip()]
    out = sys.argv[3]
    mods = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith(('.exe', '.dll')):
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) < 200 * 1024:
                    continue
            except OSError:
                continue
            mods.append(p)
    mods.sort(key=lambda p: -os.path.getsize(p))
    print(f"{len(mods)} modules:", [os.path.basename(m) for m in mods])
    blobs = {}
    for m in mods:
        blobs[m] = open(m, 'rb').read()
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write("# name\tfound_in\tcase_exact\n")
        for n in names:
            nb = n.encode()
            exact, ci = [], []
            for m, b in blobs.items():
                if nb + b'\0' in b:
                    exact.append(os.path.basename(m))
                elif re.search(re.escape(nb), b, re.I):
                    ci.append(os.path.basename(m))
            fh.write(f"{n}\t{','.join(exact) if exact else ('ci:' + ','.join(ci) if ci else '')}\t{int(bool(exact))}\n")
    print('->', out)


if __name__ == '__main__':
    main()
