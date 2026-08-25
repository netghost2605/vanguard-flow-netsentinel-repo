#!/usr/bin/env python3
"""
build_assets.py — sync web/*.html back into speedtest_monitor.py

Why this exists
---------------
The app ships as ONE file, so the web pages have to live inside it. But editing
8,000 lines of HTML/CSS/JS inside a Python string literal means no syntax
highlighting, no linting, and a whole class of escaping bugs.

So: the page content lives in web/<name> where you can edit it properly, and
this script writes it back into the marked block in speedtest_monitor.py. The
shipped .py stays completely self-contained — it never reads web/ at runtime.

Usage
-----
    python tools/build_assets.py            # sync web/ -> speedtest_monitor.py
    python tools/build_assets.py --check    # verify they match, change nothing
    python tools/build_assets.py --extract  # re-export .py -> web/ (rarely needed)

After syncing ALWAYS run:  python selftest.py
If the hash for that route changed, the edit changed behaviour. That is either
intentional (re-baseline with --update-ok) or a mistake (revert).

Marker format in speedtest_monitor.py
-------------------------------------
        # >>>ASSET:talkers.html  ...
        return r'''<content>'''
        # <<<ASSET:talkers.html

The literal is RAW (r'''), so backslashes in the JS survive untouched. Content
containing ''' or ending in a backslash cannot be embedded this way; the script
refuses rather than producing a broken file.
"""

import argparse
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "speedtest_monitor.py")
WEBDIR = os.path.join(ROOT, "web")

BEGIN = re.compile(r"^(\s*)# >>>ASSET:(\S+)", re.M)


def find_blocks(src):
    """Yield (name, indent, begin_line_idx, return_line_idx, end_line_idx)."""
    lines = src.split("\n")
    out = []
    for i, line in enumerate(lines):
        m = BEGIN.match(line)
        if not m:
            continue
        indent, name = m.group(1), m.group(2)
        ret = end = None
        for j in range(i + 1, len(lines)):
            # Accept either  return r'''...   or   html = r'''...
            if ret is None and "r'''" in lines[j]:
                ret = j
            if lines[j].strip() == f"# <<<ASSET:{name}":
                end = j
                break
        if ret is None or end is None:
            raise SystemExit(f"malformed asset block for {name} at line {i+1}")
        out.append((name, indent, i, ret, end))
    return lines, out


def literal_value(src, name):
    """The exact string the app will return, taken from the parsed AST."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for b in node.body:
                if isinstance(b, ast.Return) and isinstance(b.value, ast.Constant) \
                        and isinstance(b.value.value, str):
                    src_seg = ast.get_source_segment(src, b) or ""
                    if f"ASSET:{name}" in src[max(0, b.lineno * 0):b.lineno * 0] or True:
                        pass
    return None


def embeddable(content, name):
    if "'''" in content:
        raise SystemExit(f"{name}: contains ''' — cannot embed as a raw triple literal")
    if content.endswith("\\"):
        raise SystemExit(f"{name}: ends with a backslash — invalid in a raw literal")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only, write nothing")
    ap.add_argument("--extract", action="store_true", help="export .py -> web/")
    args = ap.parse_args()

    src = open(TARGET, encoding="utf-8").read()
    lines, blocks = find_blocks(src)
    if not blocks:
        print("no asset blocks found — nothing to do")
        return 0

    changed = mismatched = 0
    for name, indent, i, ret, end in blocks:
        path = os.path.join(WEBDIR, name)
        cur = lines[ret]
        # Everything up to and including  r'''  is the prefix we must preserve,
        # so this works for both `return r'''` and `html = r'''` forms.
        k0 = cur.index("r'''") + 4
        prefix = cur[:k0]
        current = cur[k0:]
        # the literal may span lines; rejoin to the closing delimiter
        k = ret
        while not lines[k].endswith("'''") or (k == ret and len(lines[k]) < len(prefix) + 3):
            k += 1
            current += "\n" + lines[k]
        current = current[: -3]

        if args.extract:
            os.makedirs(WEBDIR, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(current)
            print(f"  extracted  {name:22} {len(current):>7} chars -> web/{name}")
            continue

        if not os.path.exists(path):
            print(f"  MISSING    web/{name} — skipped")
            continue
        disk = open(path, encoding="utf-8", newline="").read()
        if disk == current:
            print(f"  unchanged  {name:22} {len(disk):>7} chars")
            continue
        mismatched += 1
        if args.check:
            print(f"  DIFFERS    {name:22} .py={len(current)} web={len(disk)} chars")
            continue
        embeddable(disk, name)
        new_lines = lines[: ret] + [prefix + disk + "'''"] + lines[k + 1:]
        lines = new_lines
        # re-locate remaining blocks after the edit
        src = "\n".join(lines)
        lines, blocks_after = find_blocks(src)
        changed += 1
        print(f"  synced     {name:22} {len(disk):>7} chars  web/ -> .py")

    if args.check:
        print(f"\n{'OK: in sync' if mismatched == 0 else f'{mismatched} asset(s) differ'}")
        return 0 if mismatched == 0 else 1

    if changed:
        out = "\n".join(lines)
        # never write a file that will not import
        try:
            compile(out, TARGET, "exec")
        except SyntaxError as e:
            raise SystemExit(f"refusing to write — result does not compile: {e}")
        open(TARGET, "w", encoding="utf-8").write(out)
        print(f"\nwrote {os.path.basename(TARGET)} ({changed} asset(s) updated)")
        print("NOW RUN:  python selftest.py")
    elif not args.extract:
        print("\nnothing to do — assets already in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
