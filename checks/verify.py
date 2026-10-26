# -*- coding: utf-8 -*-
"""Check every file in this repository against MANIFEST.sha256.

Usage:
    python checks/verify.py            # verify
    python checks/verify.py --table    # verify, then print the product table

MANIFEST.sha256 holds one line per file:

    <64 hex>  <size in bytes>  <path relative to the repository root>

The article quotes the first sixteen hex digits of the same SHA-256, so the
short form printed here is the identifier to look for in the article's Data
availability statement.

Exit code is 0 only when every file is present and unchanged.
"""
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MANIFEST = os.path.join(ROOT, "MANIFEST.sha256")


def load():
    entries = []
    with io.open(MANIFEST, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            full, size, path = line.split(None, 2)
            entries.append((full, int(size), path.strip()))
    return entries


def main():
    entries = load()
    bad = 0
    rows = []
    for full, size, path in entries:
        p = os.path.join(ROOT, path)
        if not os.path.exists(p):
            print("MISSING  %s" % path)
            bad += 1
            continue
        b = io.open(p, "rb").read()
        got = hashlib.sha256(b).hexdigest()
        if got != full or len(b) != size:
            print("CHANGED  %s  manifest %s (%d B)  actual %s (%d B)"
                  % (path, full[:16], size, got[:16], len(b)))
            bad += 1
            continue
        rows.append((path, len(b), got[:16]))
    print("%d files, %d mismatched" % (len(entries), bad))
    if "--table" in sys.argv:
        for path, n, short in rows:
            print("| `%s` | %s | `%s` |" % (os.path.basename(path),
                                            "{:,}".format(n), short))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
