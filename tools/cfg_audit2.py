#!/usr/bin/env python
"""Final audit: community autoexec.cfg vs the current client (v3.0.1.28).

Inputs (all produced by the other tools in this dir):
  fields.tsv        cvar_fields.py   -> registered descriptors + defaults + flags
  readers2.tsv      cvar_readers2.py-> handle/value xrefs outside the stub
  stubs.tsv         cvar_stubs.py    -> names referenced by a small stub func
  absent.tsv        name_exists.py   -> per-name module hits (exe + shipped dlls)

Outputs into <outdir>:
  autoexec-audit.tsv    per-entry verdict
  missing-candidates.tsv registered cvars absent from the cfg
  fixed-autoexec.cfg    cfg containing only verified entries (commented removals)
  report.md             human summary with counts
"""
import os, sys, os, re, collections

CFG_FILES = [
    os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'local', 'settings.cfg'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'profile', 'profile.cfg'),
    os.path.join(os.environ.get('USERPROFILE', ''), 'Saved Games', 'Respawn', 'Apex', 'local', 'videoconfig.txt'),
]
BIND_RE = re.compile(r'^\s*(bind_?\w*|unbind)\s')
NAME_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_.]*)\s*(.*)$')

FLAGS = {0x1: 'UNREGISTERED', 0x2: 'DEVELOPMENTONLY', 0x4: 'GAMEDLL', 0x8: 'CLIENTDLL',
         0x10: 'HIDDEN', 0x20: 'PROTECTED', 0x40: 'SPONLY', 0x80: 'ARCHIVE',
         0x100: 'NOTIFY', 0x200: 'USERINFO', 0x400: 'PRINTABLEONLY', 0x800: 'UNLOGGED',
         0x1000: 'NEVER_AS_STRING', 0x2000: 'REPLICATED', 0x4000: 'CHEAT',
         0x8000: 'SSCLIENT', 0x10000: 'DEMO', 0x20000: 'DONTRECORD',
         0x40000: 'NOT_CONNECTED', 0x80000: 'ARCHIVE_XBOX', 0x100000: 'ACCESSIBLE_FROM_THREADS',
         0x200000: 'NOT_LOGGED', 0x400000: 'MATERIAL_SYSTEM_THREAD',
         0x800000: 'ALLOWED_IN_MATCHMAKING', 0x1000000: 'SCRIPTS_ONLY',
         0x2000000: 'CLIENTCMD_CAN_EXECUTE', 0x4000000: 'EXEC_ONLY',
         0x8000000: 'SERVER_EXEC', 0x10000000: 'ALLOW_CONNECTED',
         0x20000000: 'ALWAYS_QUERY', 0x40000000: 'NO_MIN_MAX_CHECK'}


def load_tsv(path, key=0):
    out = {}
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        c = line.rstrip('\n').split('\t')
        out[c[key]] = c
    return out


def flag_names(v):
    f = int(v, 16) if v.startswith('0x') else int(v)
    return '|'.join(n for b, n in sorted(FLAGS.items()) if f & b)


def main():
    cfg = sys.argv[1]
    fields = load_tsv(sys.argv[2])
    readers = load_tsv(sys.argv[3])
    stubs = load_tsv(sys.argv[4])
    modules = load_tsv(sys.argv[5])
    outdir = sys.argv[6]
    os.makedirs(outdir, exist_ok=True)

    user = {}
    for f in CFG_FILES:
        if os.path.exists(f):
            for line in open(f, encoding='utf-8', errors='replace'):
                m = NAME_RE.match(line)
                if m:
                    user.setdefault(m.group(1), os.path.basename(f))

    entries = []
    for i, raw in enumerate(open(cfg, encoding='utf-8', errors='replace'), 1):
        line = raw.strip()
        if not line:
            continue
        body, _, comment = line.partition('//')
        body, comment = body.strip(), comment.strip()
        if not body:
            entries.append(dict(line=i, kind='comment', raw=line, comment=comment))
            continue
        if BIND_RE.match(body):
            entries.append(dict(line=i, kind='bind', raw=body, comment=comment))
            continue
        m = NAME_RE.match(body)
        name = m.group(1) if m else body
        val = m.group(2).strip().strip('"') if m else ''
        kind = 'cvar'
        if not re.match(r'^[-+]?[0-9.]+$', val or 'x') and name not in fields:
            kind = 'command'
        entries.append(dict(line=i, kind=kind, name=name, value=val, raw=body, comment=comment))

    counts = collections.Counter()
    rows = []
    seen_cvars = collections.Counter()
    for e in entries:
        if e['kind'] in ('comment', 'bind'):
            continue
        n = e['name']
        seen_cvars[n] += 1
        f = fields.get(n)
        r = readers.get(n)
        mod = modules.get(n)
        read = False
        if r:
            read = (int(r[6]) > 0) or (int(r[7]) > 0)
        if f:
            verdict = 'registered'
            if f[3] and (int(f[3], 16) & 0x4000):
                verdict = 'cheat-flagged'
        elif n in stubs:
            verdict = 'registered-nofields'
        elif mod and mod[1]:
            verdict = 'string-only'
        else:
            verdict = 'absent'
        if verdict == 'registered' and not read:
            verdict = 'registered-unread'
        counts[verdict] += 1
        rows.append((e, f, r, mod, read, verdict))

    with open(os.path.join(outdir, 'autoexec-audit.tsv'), 'w', encoding='utf-8') as fh:
        fh.write("# line\tname\tvalue\tverdict\tdefault\tflags\tflags_decoded\tread\thandle_xrefs\tvalue_xrefs\tstub\tin_user_cfg\tin_modules\tdups\tcomment\n")
        for e, f, r, mod, read, verdict in rows:
            fh.write('\t'.join([
                str(e['line']), e['name'], e['value'], verdict,
                f[5] if f else '', f[3] if f else '', flag_names(f[3]) if f and f[3] else '',
                str(int(read)), r[6] if r else '', r[7] if r else '', f[1] if f else '',
                user.get(e['name'], ''), mod[1] if mod else '', str(seen_cvars[e['name']]),
                e['comment'][:70]]) + '\n')

    # fixed cfg + removals
    fixed = os.path.join(outdir, 'fixed-autoexec.cfg')
    removed = []
    with open(fixed, 'w', encoding='utf-8') as fh:
        fh.write('// autoexec.cfg for Apex Legends v3.0.1.28 (build R5pc_r5-301_J28_CL11570498)\n'
                 '// generated by cfg_audit.py: every kept line is a cvar that exists in THIS build\n'
                 '// removable: name absent from the binary / cheat-flagged / nothing reads it\n')
        for e, f, r, mod, read, verdict in rows:
            if verdict == 'registered-nofields':
                verdict = 'registered'
            if verdict in ('registered', 'registered-unread'):
                note = e['comment'][:58]
                if verdict == 'registered-unread':
                    note = ('[no direct reader found] ' + note)[:70]
                fh.write(f'{e["name"]} "{e["value"]}"'.ljust(52) + f'// {note}\n')
            else:
                removed.append((e, verdict, f, read))
        fh.write('\n// ---- removed (kept for reference) ----\n')
        for e, verdict, f, read in removed:
            why = {'absent': 'name not found anywhere in this build',
                   'string-only': 'string exists but cvar is not registered',
                   'cheat-flagged': 'FCVAR_CHEAT (0x4000): blocked unless sv_cheats',
                   'registered-unread': 'registered but no code reads it',
                   }.get(verdict, verdict)
            fh.write(f'// {e["name"]} "{e["value"]}"'.ljust(52) + f'// {verdict}: {why}\n')

    # missing candidates among registered cvars
    has = {e['name'] for e in entries if e['kind'] in ('cvar', 'command')}
    miss = os.path.join(outdir, 'missing-candidates.tsv')
    with open(miss, 'w', encoding='utf-8') as fh:
        fh.write("# cvar\tdefault\tflags\tflags_decoded\tread\thandle_xrefs\tvalue_xrefs\tin_user_cfg\n")
        for n, f in sorted(fields.items()):
            if n in has:
                continue
            r = readers.get(n)
            rd = (int(r[6]) > 0 or int(r[7]) > 0) if r else False
            fh.write('\t'.join([n, f[5], f[3], flag_names(f[3]) if f[3] else '',
                                str(int(rd)), r[6] if r else '0', r[7] if r else '0',
                                user.get(n, '')]) + '\n')

    with open(os.path.join(outdir, 'report.md'), 'w', encoding='utf-8') as fh:
        fh.write('# autoexec.cfg audit vs r5apex_dx12.exe (v3.0.1.28)\n\n')
        fh.write(f'entries parsed: {len(rows)}   binds/comments: {len(entries)-len(rows)}\n\n')
        for k, v in counts.most_common():
            fh.write(f'- {k}: {v}\n')
        fh.write(f'\nduplicate cvar definitions: '
                 f'{sum(1 for n, c in seen_cvars.items() if c > 1)} names '
                 f'({", ".join(n for n, c in seen_cvars.items() if c > 1)})\n')
    print('counts:', dict(counts))
    print('dups:', [n for n, c in seen_cvars.items() if c > 1])
    print('->', outdir)


if __name__ == '__main__':
    main()
