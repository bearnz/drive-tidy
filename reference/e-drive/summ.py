import json, sys, time
d = json.load(open(sys.argv[1]))
G = lambda b: f"{b/1024**3:.2f}GB"
print("secs", d["seconds"], "errors", d["errors"])
print("== dirs")
for k, v in d["dir_size"]:
    depth = k.count("\\")
    if depth == 0 or (v >= 0.5 * 1024**3 and depth <= 2) or k.startswith(("$RECYCLE", "WINDOWS", "ProgramData", "MSOCache", "msdownld", "Vortex", "Steamtool", "Games")):
        print(G(v), k)
print("== ext")
for k, v in d["ext_size"][:15]:
    print(G(v), k)
print("== candidates")
for s, p, m in d["candidates"][:40]:
    print(G(s), time.strftime("%Y-%m-%d", time.localtime(m)), p)
tot = sum(x["wasted"] for x in d["dupes"])
print("== dupes groups", len(d["dupes"]), "wasted", G(tot))
for x in d["dupes"][:40]:
    print(G(x["wasted"]), len(x["paths"]), "x", G(x["size"]))
    for p in x["paths"][:4]:
        print("   ", p)
