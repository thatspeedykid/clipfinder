#!/usr/bin/env python3
"""Single source of truth for the ClipFinder release version.

The git tag (vX.Y.Z or vX.Y.Z.W) is the release version.  Everything that ends up
inside a build must carry the same number, and this tool makes a mismatch a hard
error instead of a silently shipped wrong version:

    clipfinder.py   APP_VERSION = "X.Y.Z.W"
    ClipFinder.nsi  !define APP_VERSION "X.Y.Z.W"   (installer title/welcome text,
                                                      DisplayVersion, EXE properties)
    README.md       version badge  (badge/version-X.Y.Z.W-orange)
    git tag         vX.Y.Z[.W]     (only when --tag is given)

Usage (run from anywhere, paths resolve relative to the repo root):

    python tools/release_version.py get                  # print APP_VERSION of clipfinder.py
    python tools/release_version.py check [--tag v1.4.0.0]
    python tools/release_version.py set 1.4.0.0          # rewrite all files, all-or-nothing
    python tools/release_version.py selftest

3-part versions are normalised to 4 parts (v1.4.0 -> 1.4.0.0).  Files always hold the
4-part form because the Windows version resources (NSIS VIProductVersion, PyInstaller
version file) need exactly four numbers.

Exit codes: 0 ok, 1 version problem / failed check, 2 usage error.
Stdlib only, Python 3.12+.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Each component of a Windows version resource is a 16-bit number.
_COMPONENT = r'(?:0|[1-9]\d{0,4})'
_VERSION_3_OR_4 = re.compile(rf'^{_COMPONENT}\.{_COMPONENT}\.{_COMPONENT}(?:\.{_COMPONENT})?$')
_VERSION_4 = re.compile(rf'^{_COMPONENT}\.{_COMPONENT}\.{_COMPONENT}\.{_COMPONENT}$')


class ReleaseError(Exception):
    """A version problem that must fail the build."""


def normalize(raw: str, *, what: str = 'version') -> str:
    """'v1.4.0' -> '1.4.0.0'; '1.4.0.0' -> '1.4.0.0'.  Anything else is an error."""
    s = raw.strip()
    if s[:1] in ('v', 'V'):
        s = s[1:]
    if not _VERSION_3_OR_4.match(s):
        raise ReleaseError(f'{what} {raw!r} is not X.Y.Z or X.Y.Z.W (numbers only, no leading zeros)')
    parts = s.split('.')
    if any(int(p) > 65535 for p in parts):
        raise ReleaseError(f'{what} {raw!r}: every part must be <= 65535 (Windows version resource limit)')
    if len(parts) == 3:
        parts.append('0')
    return '.'.join(parts)


@dataclass(frozen=True)
class Target:
    """One place that carries the version.

    `pattern` must define the named groups pre / ver / post and must match EXACTLY
    once in the file - zero matches (the old double-space nsi bug) or several are errors.
    """
    label: str            # shown in messages
    path: str             # relative to the repo root
    what: str             # human description of the line being matched
    pattern: re.Pattern


TARGETS: tuple[Target, ...] = (
    Target('clipfinder.py', 'clipfinder.py', 'APP_VERSION = "..." line',
           re.compile(r'''(?P<pre>^APP_VERSION[ \t]*=[ \t]*(?P<q>["']))(?P<ver>[^"'\r\n]*)(?P<post>(?P=q))''',
                      re.MULTILINE)),
    # [ \t]+ : any amount of spaces/tabs between the tokens (the old regex broke on a double space).
    Target('ClipFinder.nsi', 'ClipFinder.nsi', '!define APP_VERSION "..." line',
           re.compile(r'''(?P<pre>^[ \t]*!define[ \t]+APP_VERSION[ \t]+")(?P<ver>[^"\r\n]*)(?P<post>")''',
                      re.MULTILINE)),
    Target('README.md badge', 'README.md', 'shields.io version badge',
           re.compile(r'''(?P<pre>img\.shields\.io/badge/version-)(?P<ver>\d+(?:\.\d+)*)(?P<post>-[A-Za-z0-9]+\))''')),
)


# -- file access ---------------------------------------------------------------
def _read(root: Path, rel: str) -> str:
    p = root / rel
    try:
        return p.read_bytes().decode('utf-8')
    except FileNotFoundError:
        raise ReleaseError(f'{rel}: file not found under {root}') from None
    except UnicodeDecodeError as e:
        raise ReleaseError(f'{rel}: not valid UTF-8 ({e})') from None


def _write(root: Path, rel: str, text: str) -> None:
    # bytes in / bytes out: line endings and BOM of the original file are preserved
    (root / rel).write_bytes(text.encode('utf-8'))


def _find_one(t: Target, text: str) -> re.Match:
    hits = list(t.pattern.finditer(text))
    if len(hits) != 1:
        raise ReleaseError(f'{t.path}: expected exactly 1 {t.what}, found {len(hits)}')
    return hits[0]


def read_version(root: Path, target: Target) -> str:
    """The raw version string stored in one file (not normalised)."""
    return _find_one(target, _read(root, target.path)).group('ver')


def read_app_version(root: Path = REPO_ROOT) -> str:
    """APP_VERSION of clipfinder.py, validated as a canonical X.Y.Z.W string.
    (build_launcher.py uses this so the launcher EXE gets the same number.)"""
    raw = read_version(root, TARGETS[0])
    if not _VERSION_4.match(raw):
        raise ReleaseError(f'clipfinder.py: APP_VERSION {raw!r} is not X.Y.Z.W')
    return normalize(raw)


# -- commands ------------------------------------------------------------------
def check(root: Path, tag: str | None = None) -> list[tuple[str, str]]:
    """Return [(label, version)] when every source agrees; raise ReleaseError listing ALL problems."""
    problems: list[str] = []
    found: list[tuple[str, str]] = []
    for t in TARGETS:
        try:
            raw = read_version(root, t)
        except ReleaseError as e:
            problems.append(str(e))
            continue
        if not _VERSION_4.match(raw):
            problems.append(f'{t.path}: version {raw!r} must be 4-part X.Y.Z.W')
            continue
        found.append((t.label, raw))

    try:
        nsi_text = _read(root, 'ClipFinder.nsi')
        bad = next(((n, l) for n, l in enumerate(nsi_text.splitlines(), 1) if not l.isascii()), None)
        if bad:
            problems.append(f'ClipFinder.nsi line {bad[0]} contains non-ASCII characters '
                            f'(NSIS reads this file as ANSI -> mojibake); keep it pure ASCII')
    except ReleaseError:
        pass  # already reported above

    if tag is not None:
        try:
            found.append((f'git tag {tag}', normalize(tag, what='tag')))
        except ReleaseError as e:
            problems.append(str(e))

    if len({v for _, v in found}) > 1:
        width = max(len(l) for l, _ in found)
        problems.append('versions disagree:\n' + '\n'.join(f'      {l:<{width}}  {v}' for l, v in found))

    if problems:
        raise ReleaseError('\n  - '.join(['version check FAILED'] + problems))
    return found


def set_version(root: Path, raw: str) -> str:
    """Rewrite every target to `raw` (normalised).  All-or-nothing; every substitution is
    asserted to have happened exactly once and is re-read to prove it."""
    ver = normalize(raw)
    staged: list[tuple[Target, str]] = []
    for t in TARGETS:
        text = _read(root, t.path)
        _find_one(t, text)  # explicit: fail (0 or >1 matches) before we change anything
        new_text, n = t.pattern.subn(lambda m: m.group('pre') + ver + m.group('post'), text)
        if n != 1:
            raise ReleaseError(f'{t.path}: substitution replaced {n} places, expected exactly 1')
        if t.path.endswith('.nsi') and not new_text.isascii():
            raise ReleaseError('ClipFinder.nsi must stay pure ASCII')
        staged.append((t, new_text))
    for t, new_text in staged:
        _write(root, t.path, new_text)
    for t in TARGETS:  # read-back proof: never trust the write
        got = read_version(root, t)
        if got != ver:
            raise ReleaseError(f'{t.path}: after writing, found {got!r} instead of {ver!r}')
    return ver


# -- selftest ------------------------------------------------------------------
def selftest() -> int:
    """Runs against temp COPIES of the real files, so it also proves the real files still
    match the strict patterns.  Never touches the working tree."""
    n_checks = 0

    def ok(cond: bool, msg: str) -> None:
        nonlocal n_checks
        n_checks += 1
        if not cond:
            raise AssertionError(msg)

    def raises(fn, needle: str, msg: str) -> None:
        nonlocal n_checks
        n_checks += 1
        try:
            fn()
        except ReleaseError as e:
            if needle not in str(e):
                raise AssertionError(f'{msg}: wrong error: {e}') from None
            return
        raise AssertionError(f'{msg}: expected ReleaseError')

    # locates the real define line in the fixture (comments that merely mention it start with ';')
    nsi_define_line = re.compile(r'(?m)^[ \t]*!define[ \t]+APP_VERSION\b.*$')

    with tempfile.TemporaryDirectory(prefix='cf_relver_') as td:
        root = Path(td)
        for t in TARGETS:
            shutil.copyfile(REPO_ROOT / t.path, root / t.path)

        # normalisation
        ok(normalize('v1.4.0') == '1.4.0.0', 'v1.4.0 -> 1.4.0.0')
        ok(normalize('1.4.0.7') == '1.4.0.7', '4-part unchanged')
        for bad in ('1.4', '1', '1.2.3.4.5', 'v', '', '01.2.3', '1.2.x', '1.2.3-rc1', '70000.0.0'):
            raises(lambda b=bad: normalize(b), 'not X.Y.Z' if bad != '70000.0.0' else '65535', f'reject {bad!r}')

        # set / read-back on the real formats
        ok(set_version(root, '9.8.7.6') == '9.8.7.6', 'set 4-part')
        ok([read_version(root, t) for t in TARGETS] == ['9.8.7.6'] * 3, 'all targets rewritten')
        ok(len(check(root, 'v9.8.7.6')) == 4, 'check passes with tag')
        ok(set_version(root, 'v2.3.4') == '2.3.4.0', 'set normalises 3-part')
        ok(check(root, 'v2.3.4')[-1][1] == '2.3.4.0', '3-part tag compares equal to 4-part files')
        ok(read_app_version(root) == '2.3.4.0', 'read_app_version')

        # the historic bug: nsi define spacing variants must ALL work
        forms = {
            'single space': '!define APP_VERSION "{v}"',
            'double space (the 1.3.8.2 bug)': '!define APP_VERSION  "{v}"',
            'wide alignment': '!define APP_VERSION      "{v}"',
            'tabs': '!define\tAPP_VERSION\t"{v}"',
            'indented + trailing comment': '  !define APP_VERSION   "{v}"   ; patched by tools/release_version.py',
        }
        nsi = root / 'ClipFinder.nsi'
        for i, (name, form) in enumerate(forms.items()):
            new = f'3.4.5.{i}'
            nsi.write_bytes(nsi_define_line.sub(lambda m: form.format(v='1.1.1.1'),
                                                nsi.read_bytes().decode('utf-8'), count=1).encode('utf-8'))
            ok(read_version(root, TARGETS[1]) == '1.1.1.1', f'read nsi form: {name}')
            set_version(root, new)
            line = next(l for l in nsi.read_text('utf-8').splitlines() if nsi_define_line.match(l))
            ok(f'"{new}"' in line, f'set nsi form: {name} -> {line!r}')
            ok(form.format(v='X').split('X')[0] == line.split(new)[0], f'spacing preserved: {name}')
            check(root, f'v{new}')

        # every disagreement is caught, and reported together
        set_version(root, '5.5.5.5')
        (root / 'README.md').write_text(
            (root / 'README.md').read_text('utf-8').replace('version-5.5.5.5-', 'version-5.5.5.4-'), 'utf-8')
        raises(lambda: check(root), 'versions disagree', 'badge mismatch')
        set_version(root, '5.5.5.5')
        raises(lambda: check(root, 'v5.5.5.6'), 'versions disagree', 'tag mismatch')
        raises(lambda: check(root, 'vfoo'), "tag 'vfoo'", 'bad tag')
        check(root, 'v5.5.5.5')

        # non-ASCII in the nsi (em dash mojibake once) is rejected
        good = nsi.read_bytes()
        nsi.write_bytes(good + '; caf\u00e9 \u2014 dash\n'.encode('utf-8'))  # e-acute + em dash
        raises(lambda: check(root), 'non-ASCII', 'non-ASCII nsi')
        nsi.write_bytes(good)

        # a define that is missing / duplicated must be an error, never a silent no-op
        nsi.write_bytes(nsi_define_line.sub('; (removed)', good.decode('utf-8'), count=1).encode('utf-8'))
        raises(lambda: set_version(root, '6.6.6.6'), 'found 0', 'set with no define')
        raises(lambda: check(root), 'found 0', 'check with no define')
        nsi.write_bytes(good + b'\n!define APP_VERSION "9.9.9.9"\n')
        raises(lambda: set_version(root, '6.6.6.6'), 'found 2', 'set with duplicate define')
        nsi.write_bytes(good.replace(b'"5.5.5.5"', b'"5.5.5"', 1))
        raises(lambda: check(root), 'must be 4-part', 'nsi holding a 3-part version')

        # all-or-nothing: a failing target must leave the other files untouched
        before = (root / 'clipfinder.py').read_bytes()
        nsi.write_bytes(nsi_define_line.sub('; (removed)', good.decode('utf-8'), count=1).encode('utf-8'))
        raises(lambda: set_version(root, '7.7.7.7'), 'found 0', 'set aborts')
        ok((root / 'clipfinder.py').read_bytes() == before, 'failed set left clipfinder.py untouched')
        nsi.write_bytes(good)

    print(f'selftest OK ({n_checks} assertions)')
    return 0


# -- CLI -----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', type=Path, default=REPO_ROOT, help='repo root (default: the repo this tool lives in)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('get', help='print APP_VERSION from clipfinder.py')
    c = sub.add_parser('check', help='fail unless clipfinder.py, ClipFinder.nsi, README badge (and --tag) agree')
    c.add_argument('--tag', help='git tag to compare, e.g. v1.4.0.0 (3-part tags are normalised)')
    s = sub.add_parser('set', help='rewrite the version in every file')
    s.add_argument('version', help='X.Y.Z or X.Y.Z.W (a leading v is accepted)')
    sub.add_parser('selftest', help='run the built-in tests against temp copies')
    args = ap.parse_args(argv)
    root = args.root.resolve()

    try:
        if args.cmd == 'get':
            print(read_app_version(root))
        elif args.cmd == 'check':
            found = check(root, args.tag)
            width = max(len(l) for l, _ in found)
            for label, ver in found:
                print(f'  {label:<{width}}  {ver}')
            print(f'OK: all {len(found)} sources agree on {found[0][1]}')
        elif args.cmd == 'set':
            ver = set_version(root, args.version)
            for t in TARGETS:
                print(f'  {t.label:<16} -> {ver}')
            print(f'OK: version set to {ver}. Now write RELEASE_NOTES_v{ver}.md, commit, tag v{ver}.')
        elif args.cmd == 'selftest':
            return selftest()
    except ReleaseError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
