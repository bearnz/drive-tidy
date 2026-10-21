import sys, re, os
from collections import defaultdict

GB = 1024**3
SEP = '\\'
CACHE = re.compile(r'(?i)^(.*?\\(?:node_modules|\$RECYCLE\.BIN|\.venv|venv|__pycache__|\.gradle|Library\\ShaderCache|Library\\Bee|Temp|Logs|obj|\.godot|crashdumps|shadercache))\\')

for f in sys.argv[1:]:
    l1, l2, l3, ext, cache = (defaultdict(float) for _ in range(5))
    big = []
    total = 0
    with open(f, encoding='utf-8-sig', errors='replace') as fh:
        for line in fh:
            b, _, p = line.rstrip('\r\n').partition('|')
            if not p or not b.isdigit():
                continue
            b = float(b)
            total += b
            parts = p.split(SEP)
            for depth, d in ((2, l1), (3, l2), (4, l3)):
                if len(parts) > depth:
                    d[SEP.join(parts[:depth])] += b
            ext[os.path.splitext(p)[1].lower()] += b
            if b > 2 * GB:
                big.append((b, p))
            m = CACHE.match(p)
            if m:
                cache[m.group(1)] += b

    def top(d, n, mn):
        for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]:
            if v >= mn * GB:
                print(f"{v / GB:9.1f} GB  {k}")

    print(f"================ {os.path.basename(f)}  total {total / GB:,.0f} GB")
    print("--- Top-level"); top(l1, 25, 1)
    print("--- Level 2"); top(l2, 30, 5)
    print("--- Level 3"); top(l3, 30, 10)
    print("--- Biggest files >2GB")
    for b, p in sorted(big, reverse=True)[:25]:
        print(f"{b / GB:9.1f} GB  {p}")
    print("--- Extensions"); top(ext, 15, 5)
    print("--- Cache/build/recycle folders"); top(cache, 25, 0.3)
