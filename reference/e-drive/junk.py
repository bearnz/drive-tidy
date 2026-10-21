"""Read-only: tally save files and junk categories on a drive."""
import os, re, sys
from collections import defaultdict

ROOT = sys.argv[1]
SAVE_DIR = re.compile(r"^(saves?|savegames?|savedata|save ?files?|userdata)$", re.I)
SAVE_EXT = {".sav", ".fos", ".ess", ".gun", ".rvdata2", ".save", ".sv"}
CATS = {
    "crash dumps": lambda n, p: n.endswith((".dmp", ".mdmp")),
    "log files": lambda n, p: n.endswith((".log", "output_log.txt", "output_log_clean.txt")) or "\\log\\" in p or "\\logs\\" in p,
    "bundled redist installers": lambda n, p: ("\\_commonredist\\" in p or "\\redistributables\\" in p or "\\redist\\" in p or "\\prerequisites\\" in p or "\\directx\\" in p) and n.endswith((".exe", ".msi", ".cab")),
}
saves = defaultdict(lambda: [0, 0])
junk = defaultdict(lambda: defaultdict(lambda: [0, 0]))

def game_of(p):
    parts = p.split(os.sep)
    low = [x.lower() for x in parts]
    if "common" in low:
        i = low.index("common")
        return os.sep.join(parts[: i + 2])
    return os.sep.join(parts[:3])

for dp, dns, fns in os.walk(ROOT):
    if "System Volume Information" in dp or "$RECYCLE.BIN" in dp:
        dns[:] = []
        continue
    in_save_dir = any(SAVE_DIR.match(x) for x in dp.split(os.sep))
    for f in fns:
        p = os.path.join(dp, f)
        try:
            s = os.path.getsize(p)
        except OSError:
            continue
        n, lp = f.lower(), p.lower()
        if in_save_dir or os.path.splitext(n)[1] in SAVE_EXT:
            g = game_of(p)
            saves[g][0] += s; saves[g][1] += 1
        for c, test in CATS.items():
            if test(n, lp):
                g = game_of(p)
                junk[c][g][0] += s; junk[c][g][1] += 1
                break

print("== saves")
for g, (s, c) in sorted(saves.items(), key=lambda kv: -kv[1][0]):
    print(f"{s/1024**2:10.1f} MB {c:5d} files  {g}")
for cat, d in junk.items():
    tot = sum(v[0] for v in d.values())
    print(f"== {cat}: {tot/1024**2:.1f} MB")
    for g, (s, c) in sorted(d.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"{s/1024**2:10.1f} MB {c:5d} files  {g}")
