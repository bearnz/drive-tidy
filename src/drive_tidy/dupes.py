"""Duplicate files: group by size, then a partial hash, then a full hash."""
import hashlib
import os
import re
from collections import defaultdict

CHUNK = 1 << 20


def partial_hash(path, size):
    """Hash of the first, middle and last MiB."""
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as fh:
        for off in (0, size // 2, max(0, size - CHUNK)):
            fh.seek(off)
            h.update(fh.read(CHUNK))
    return h.hexdigest()


def full_hash(path):
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 * CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _split(paths, key):
    groups = defaultdict(list)
    for p in paths:
        try:
            groups[key(p)].append(p)
        except OSError:
            pass
    return [g for g in groups.values() if len(g) > 1]


def find_groups(by_size):
    """by_size: {size: [paths]}. Returns [(size, [paths])] of byte-identical
    files, every group confirmed by a full hash."""
    out = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for quick in _split(paths, lambda p: partial_hash(p, size)):
            for same in _split(quick, full_hash):
                out.append((size, sorted(same)))
    out.sort(key=lambda g: -g[0] * (len(g[1]) - 1))
    return out


def in_downloads(path):
    return any(p.lower() == "downloads" for p in re.split(r"[\\/]", os.path.dirname(path)))


def keep_rank(path):
    """Lower sorts first and is the copy to keep: not in Downloads, not a
    partial download, not a "name (1).ext" repeat, then the shortest name."""
    name = os.path.basename(path)
    return (
        in_downloads(path),
        name.lower().endswith(".crdownload"),
        bool(re.search(r" \(\d+\)(\.[^.]+)?$", name)),
        len(name),
        len(path),
        path.lower(),
    )
