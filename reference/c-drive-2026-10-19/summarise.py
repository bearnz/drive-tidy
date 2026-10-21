import sys, collections, datetime

path = sys.argv[1]
since = datetime.datetime(2026, 10, 16, 3, 0)  # after the previous C: cleanup
by_dir = {d: collections.Counter() for d in (2, 3, 4, 5)}
recent = collections.Counter()
big_files, recent_files = [], []
total = 0
with open(path, encoding="utf-16", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) < 2:
            continue
        rest, p = parts[-2].strip(), parts[-1]
        try:
            size_s, d, t = rest.split()
            size = int(size_s)
            mtime = datetime.datetime.strptime(d + " " + t, "%Y/%m/%d %H:%M:%S")
        except ValueError:
            continue
        total += size
        segs = p.split("\\")
        for depth in by_dir:
            if len(segs) > depth:
                by_dir[depth]["\\".join(segs[:depth])] += size
        if size > 500 * 2**20:
            big_files.append((size, mtime, p))
        if mtime >= since:
            recent["\\".join(segs[:min(len(segs) - 1, 6)])] += size
            if size > 100 * 2**20:
                recent_files.append((size, mtime, p))

gb = lambda b: f"{b / 2**30:7.2f} GB"
print("TOTAL listed", gb(total))
for depth, n in ((2, 15), (3, 25), (4, 40), (5, 50)):
    print(f"\n== top folders at depth {depth}")
    for k, v in by_dir[depth].most_common(n):
        if v > 300 * 2**20:
            print(gb(v), k)
print("\n== files > 500 MB")
for s, m, p in sorted(big_files, reverse=True)[:50]:
    print(gb(s), m.date(), p)
print("\n== written since 2026-10-16 03:00, by folder")
for k, v in recent.most_common(30):
    print(gb(v), k)
print("\n== recent files > 100 MB")
for s, m, p in sorted(recent_files, reverse=True)[:30]:
    print(gb(s), m, p)
