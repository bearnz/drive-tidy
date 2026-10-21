import sys, collections
path, prefix, depth = sys.argv[1], sys.argv[2].lower(), int(sys.argv[3])
c = collections.Counter(); n = collections.Counter()
with open(path, encoding="utf-16", errors="replace") as f:
    for line in f:
        parts = line.rstrip("\r\n").split("\t")
        if len(parts) < 2 or not parts[-1].lower().startswith(prefix): continue
        try: size = int(parts[-2].split()[0])
        except (ValueError, IndexError): continue
        segs = parts[-1].split("\\")
        k = "\\".join(segs[:depth]) if len(segs) > depth else parts[-1]
        c[k] += size; n[k] += 1
for k, v in c.most_common(int(sys.argv[4]) if len(sys.argv) > 4 else 30):
    if v > 150 * 2**20: print(f"{v/2**30:6.2f} GB {n[k]:>7} files  {k}")
