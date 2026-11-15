#!/usr/bin/env python3
"""tidy: find duplicate files by content, route files by rules, undo via manifest.

  python tidy.py ~/Downloads ~/Desktop --dest ~/Tidy --rules rules.toml           # dry run
  python tidy.py ~/Downloads ~/Desktop --dest ~/Tidy --rules rules.toml --apply
  python tidy.py --undo ~/Tidy/tidy-manifest-20261115-120000.json

Nothing is ever deleted: duplicates go to <dest>/_duplicates so --undo can restore them.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import tomllib
from collections import defaultdict
from pathlib import Path

MANIFEST_PREFIX = "tidy-manifest-"


def walk(roots, skip_dir):
    for root in roots:
        for dirpath, _, names in os.walk(root):
            d = Path(dirpath)
            if d == skip_dir or skip_dir in d.parents:
                continue
            for n in names:
                p = d / n
                if n.startswith(MANIFEST_PREFIX) or p.is_symlink():
                    continue
                try:
                    yield p, p.stat()
                except OSError as e:
                    print(f"skip {p}: {e}", file=sys.stderr)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_dupes(files):
    """files: [(path, stat)]. Returns groups of identical files, oldest first (the one kept)."""
    by_size = defaultdict(list)
    for p, st in files:
        if st.st_size:  # empty files all "match"; they're placeholders, not duplicates
            by_size[st.st_size].append((p, st))
    groups = []
    for same_size in by_size.values():
        if len(same_size) < 2:
            continue  # unique size => can't be a duplicate, never hashed
        by_hash = defaultdict(list)
        for p, st in same_size:
            try:
                by_hash[sha256(p)].append((p, st))
            except OSError as e:
                print(f"skip {p}: {e}", file=sys.stderr)
        for g in by_hash.values():
            if len(g) > 1:
                groups.append([p for p, st in sorted(g, key=lambda x: (x[1].st_mtime, len(str(x[0]))))])
    return groups


def load_rules(path):
    with open(path, "rb") as f:
        rules = tomllib.load(f).get("rule", [])
    for r in rules:
        if "dest" not in r:
            raise SystemExit(f"rule missing 'dest': {r}")
    return rules


def matches(rule, p):
    # shortcut: "contains" checks the filename, not file contents; add a PDF text extractor if needed
    exts = [e.lower() for e in rule.get("ext", [])]
    words = [w.lower() for w in rule.get("contains", [])]
    name = p.name.lower()
    return (not exts or p.suffix.lower() in exts) and (not words or any(w in name for w in words))


def plan(roots, dest, rules):
    dup_dir = dest / "_duplicates"
    files = list(walk(roots, dup_dir))
    taken = set()

    def free_target(p, folder):
        t, i = folder / p.name, 1
        while t.exists() or t in taken:
            t, i = folder / f"{p.stem} ({i}){p.suffix}", i + 1
        taken.add(t)
        return t

    moves, dupes = [], set()
    for group in find_dupes(files):
        for p in group[1:]:
            dupes.add(p)
            moves.append(("DUP", p, free_target(p, dup_dir)))
    for p, _ in files:
        if p in dupes:
            continue
        rule = next((r for r in rules if matches(r, p)), None)
        if rule:
            folder = (dest / rule["dest"]).resolve()
            if p.parent != folder:
                moves.append(("MOVE", p, free_target(p, folder)))
    return moves


def apply(moves, manifest):
    # manifest is written before anything moves, so a crash mid-run is still undoable
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps([{"src": str(s), "dst": str(d)} for _, s, d in moves], indent=2))
    for _, s, d in moves:
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(s, d)
        except OSError as e:
            raise SystemExit(f"failed moving {s}: {e}\nrestore with: python tidy.py --undo \"{manifest}\"")


def undo(manifest):
    restored = 0
    for e in reversed(json.loads(Path(manifest).read_text())):
        s, d = Path(e["src"]), Path(e["dst"])
        if not d.exists():
            print(f"not found, skipping: {d}")
        elif s.exists():
            print(f"original spot taken, skipping: {s}")
        else:
            s.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(d, s)
            restored += 1
    print(f"restored {restored} file(s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*", help="folders to scan")
    ap.add_argument("--dest", help="where organized files and _duplicates go")
    ap.add_argument("--rules", help="rules.toml routing file")
    ap.add_argument("--apply", action="store_true", help="actually move files (default: dry run)")
    ap.add_argument("--undo", metavar="MANIFEST", help="restore every file listed in a manifest")
    a = ap.parse_args(argv)

    if a.undo:
        return undo(Path(a.undo).expanduser())
    if not a.roots or not a.dest:
        ap.error("roots and --dest are required (or use --undo)")

    roots = [Path(r).expanduser().resolve() for r in a.roots]
    dest = Path(a.dest).expanduser().resolve()
    moves = plan(roots, dest, load_rules(a.rules) if a.rules else [])
    for kind, s, d in moves:
        print(f"{kind:4} {s} -> {d}")
    n_dup = sum(k == "DUP" for k, _, _ in moves)
    print(f"\n{n_dup} duplicate(s), {len(moves) - n_dup} rule move(s)")
    if not moves:
        return
    if a.apply:
        manifest = dest / f"{MANIFEST_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}.json"
        apply(moves, manifest)
        print(f"done. undo with: python tidy.py --undo \"{manifest}\"")
    else:
        print("dry run: nothing moved. add --apply to do it.")


if __name__ == "__main__":
    main()
