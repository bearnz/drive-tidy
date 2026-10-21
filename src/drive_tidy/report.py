"""Write a scan's report (Markdown) and candidates (CSV)."""
import csv
import os
import time
from collections import defaultdict

from .rules import path_parts

CSV_FIELDS = ["approve", "category", "kind", "size_bytes", "size", "newest", "path", "reason"]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.2f} TB"


def day(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts else "-"


def write_csv(res, path):
    rows = sorted(res.candidates, key=lambda c: (c["category"], -c["size"], c["path"].lower()))
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, CSV_FIELDS)
        w.writeheader()
        for c in rows:
            w.writerow({"approve": "", "category": c["category"], "kind": c["kind"],
                        "size_bytes": c["size"], "size": human(c["size"]),
                        "newest": day(c["newest"]), "path": c["path"], "reason": c["reason"]})


def write_report(res, path, top=25):
    root_t = res.dirs.get(res.root)
    L = []
    add = L.append
    add(f"# drive-tidy scan of {res.root}")
    add("")
    add(f"- Scanned {day(res.started)} {time.strftime('%H:%M', time.localtime(res.started))}, "
        f"took {res.seconds:.0f} s. Read-only: nothing was changed.")
    if root_t:
        add(f"- {root_t.files:,} files, {human(root_t.size)} counted.")
    add(f"- {len(res.errors)} unreadable paths, {len(res.skipped)} skipped folders/links "
        "(System Volume Information, $RECYCLE.BIN, WindowsApps, WpSystem, junctions, symlinks).")
    add("")

    by_cat = defaultdict(list)
    for c in res.candidates:
        by_cat[c["category"]].append(c)
    add("## Clean-up candidates")
    add("")
    add("Each row is in `candidates.csv` with an empty `approve` column. Put `y` in it for "
        "the rows to bin, then run `drive-tidy recycle candidates.csv`.")
    add("")
    if by_cat:
        add("| Category | Items | Size |")
        add("|---|---:|---:|")
        for cat, items in sorted(by_cat.items(), key=lambda kv: -sum(c["size"] for c in kv[1])):
            add(f"| {cat} | {len(items)} | {human(sum(c['size'] for c in items))} |")
        add("")
        for cat, items in sorted(by_cat.items()):
            add(f"### {cat}")
            add("")
            for c in sorted(items, key=lambda c: -c["size"])[:top]:
                add(f"- {human(c['size'])}, newest {day(c['newest'])}: `{c['path']}`")
            if len(items) > top:
                add(f"- ... and {len(items) - top} more in the CSV")
            add("")
    else:
        add("None found.")
        add("")
    if res.kept:
        add("### Matched a category but kept")
        add("")
        for cat, p, why in res.kept[:top * 2]:
            add(f"- {cat}: `{p}` ({why})")
        if len(res.kept) > top * 2:
            add(f"- ... and {len(res.kept) - top * 2} more")
        add("")

    add("## Biggest folders")
    add("")
    base = len(path_parts(res.root))
    for depth in (1, 2, 3):
        rows = [(t.size, d) for d, t in res.dirs.items() if len(path_parts(d)) - base == depth]
        add(f"Depth {depth}:")
        add("")
        for size, d in sorted(rows, reverse=True)[:top]:
            add(f"- {human(size)} `{d}`")
        add("")

    add("## Large files")
    add("")
    for size, mtime, p in sorted(res.big_files, reverse=True)[:top * 2]:
        add(f"- {human(size)}, modified {day(mtime)}: `{p}`")
    add("")
    add("## Old files (not modified for a long time)")
    add("")
    for size, mtime, p in sorted(res.old_files, reverse=True)[:top * 2]:
        add(f"- {human(size)}, modified {day(mtime)}: `{p}`")
    add("")

    wasted = sum(s * (len(ps) - 1) for s, ps in res.dup_groups)
    add(f"## Duplicate files: {len(res.dup_groups)} groups, {human(wasted)} in extra copies")
    add("")
    add("Byte-identical (size, then partial hash, then full hash). Steam libraries, Windows, "
        "Program Files, ProgramData and AppData are left out. Only extra copies inside a "
        "Downloads folder go into the CSV; the rest are listed here for you to judge.")
    add("")
    for size, paths in res.dup_groups[:top]:
        add(f"- {len(paths)} x {human(size)}:")
        for p in paths[:6]:
            add(f"  - `{p}`")
    add("")

    if res.libraries:
        add("## Steam libraries")
        add("")
        add("Uninstalling games is your call, in Steam. Game files are left out of the "
            "large/old file lists above.")
        add("")
        steam = res.steam
        if steam is not None and steam.found:
            add("Last played comes from Steam's `localconfig.vdf`. Steam only records games "
                "started through Steam, so modded games launched another way may show older dates.")
            add("")
        year_ago = res.started - 365 * 86400
        for lib in res.libraries:
            games = [g for g in res.games if g[5] is lib]
            listed = "" if steam is None or not steam.found else (
                ", listed in Steam" if steam.is_registered(lib.steamapps) else ", **not listed in Steam**")
            stale = [g for g in games if g[2] and (g[4] or 0) < year_ago]
            add(f"`{lib.steamapps}`: {len(lib.app_ids)} app manifests{listed}, "
                f"{human(sum(g[0] for g in games))} in {len(games)} game folders. "
                f"Not played for a year or more: {len(stale)} games, {human(sum(g[0] for g in stale))}.")
            add("")
            add("| Size | Game | Last played |")
            add("|---:|---|---|")
            for size, p, ok, name, played, _lib in sorted(games, key=lambda g: -g[0])[:top * 2]:
                label = name or os.path.basename(p)
                when = day(played) if played else ("never" if steam is not None and steam.found else "?")
                add(f"| {human(size)} | {label} | {when if ok else 'no manifest'} |")
            if len(games) > top * 2:
                add(f"| | ... and {len(games) - top * 2} more | |")
            add("")
    if res.errors:
        add("## Unreadable paths")
        add("")
        for e in res.errors[:top]:
            add(f"- {e}")
        if len(res.errors) > top:
            add(f"- ... and {len(res.errors) - top} more")
        add("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
