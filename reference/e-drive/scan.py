"""Read-only scan of a drive: folder sizes, duplicate files, cleanup candidates."""
import hashlib, json, os, sys, time
from collections import defaultdict

ROOT = sys.argv[1]
OUT = sys.argv[2]
MIN_DUP = 1024 * 1024  # only bother with dupes >= 1 MB
SKIP = {"System Volume Information"}

dir_size = defaultdict(int)      # depth-1 and depth-2 dirs
by_size = defaultdict(list)
ext_size = defaultdict(int)
big_files = []
old_ext = {".iso", ".zip", ".rar", ".7z", ".exe", ".msi", ".dmp", ".tmp", ".log", ".bak", ".old"}
candidates = []
errors = 0
t0 = time.time()

for dirpath, dirnames, filenames in os.walk(ROOT, onerror=lambda e: None):
    rel = os.path.relpath(dirpath, ROOT)
    parts = [] if rel == "." else rel.split(os.sep)
    if not parts:
        dirnames[:] = [d for d in dirnames if d not in SKIP]
    for f in filenames:
        p = os.path.join(dirpath, f)
        try:
            st = os.stat(p, follow_symlinks=False)
        except OSError:
            errors += 1
            continue
        s = st.st_size
        if parts:
            dir_size[parts[0]] += s
            if len(parts) > 1:
                dir_size[os.path.join(parts[0], parts[1])] += s
            if len(parts) > 2:
                dir_size[os.path.join(parts[0], parts[1], parts[2])] += s
        ext = os.path.splitext(f)[1].lower()
        ext_size[ext] += s
        if s >= MIN_DUP:
            by_size[s].append(p)
        if s >= 1024**3:
            big_files.append((s, p, st.st_mtime))
        if ext in old_ext and s >= 50 * 1024**2:
            candidates.append((s, p, st.st_mtime))


def h(path, limit=None):
    m = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as fh:
        if limit:
            m.update(fh.read(limit))
            fh.seek(max(0, os.path.getsize(path) - limit))
            m.update(fh.read(limit))
        else:
            for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
                m.update(chunk)
    return m.hexdigest()

dupes = []
for s, paths in by_size.items():
    if len(paths) < 2:
        continue
    quick = defaultdict(list)
    for p in paths:
        try:
            quick[h(p, 256 * 1024)].append(p)
        except OSError:
            pass
    for qp in quick.values():
        if len(qp) < 2:
            continue
        full = defaultdict(list)
        for p in qp:
            try:
                full[h(p)].append(p)
            except OSError:
                pass
        for fp in full.values():
            if len(fp) > 1:
                dupes.append({"size": s, "paths": sorted(fp), "wasted": s * (len(fp) - 1)})

dupes.sort(key=lambda d: -d["wasted"])
json.dump({
    "seconds": round(time.time() - t0),
    "errors": errors,
    "dir_size": sorted(dir_size.items(), key=lambda kv: -kv[1]),
    "ext_size": sorted(ext_size.items(), key=lambda kv: -kv[1])[:30],
    "big_files": sorted(big_files, reverse=True),
    "candidates": sorted(candidates, reverse=True),
    "dupes": dupes,
}, open(OUT, "w"), indent=1)
print("done", round(time.time() - t0), "s;", len(dupes), "dupe groups")
