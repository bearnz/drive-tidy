import argparse
import os
import re
import sys
import time

from . import recycle, report, scan


def drive_root(arg):
    """'E', 'E:' and 'E:\\' all mean the root of E:. Other paths are used as given."""
    if re.fullmatch(r"[A-Za-z]:?[\\/]?", arg):
        return arg[0].upper() + ":\\"
    return os.path.abspath(arg)


def cmd_scan(a):
    root = drive_root(a.drive)
    if not os.path.isdir(root):
        sys.exit(f"not a folder: {root}")
    label = re.sub(r"[^A-Za-z0-9]+", "-", root).strip("-") or "root"
    out = a.out or f"drive-tidy-{label}-{time.strftime('%Y%m%d-%H%M')}"
    os.makedirs(out, exist_ok=True)
    opts = scan.Options(big=int(a.big_gb * scan.GiB), old_days=int(a.old_years * 365),
                        download_days=a.download_days, hash_dupes=not a.no_dupes)
    print(f"scanning {root} (read-only)")
    res = scan.scan(root, opts, progress=lambda m: print("  " + m, flush=True))
    report.write_report(res, os.path.join(out, "report.md"))
    report.write_csv(res, os.path.join(out, "candidates.csv"))
    total = sum(c["size"] for c in res.candidates)
    print(f"done in {res.seconds:.0f} s: {len(res.candidates)} candidates ({report.human(total)}), "
          f"{len(res.dup_groups)} duplicate groups, {len(res.errors)} unreadable paths")
    print(f"report:     {os.path.join(out, 'report.md')}")
    print(f"candidates: {os.path.join(out, 'candidates.csv')}")


def cmd_recycle(a):
    results = recycle.run(a.csv, apply=a.apply, log_path=a.log)
    if any(s == "NOT-IN-BIN" for s, _r, _d in results):
        sys.exit(2)


def main(argv=None):
    p = argparse.ArgumentParser(prog="drive-tidy", description="Find clean-up candidates on a drive "
                                "and send the ones you approve to the Recycle Bin.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="read-only scan; writes report.md and candidates.csv")
    s.add_argument("drive", help="drive letter (E, E:, E:\\) or a folder")
    s.add_argument("--out", help="output folder (default: drive-tidy-<drive>-<time> here)")
    s.add_argument("--big-gb", type=float, default=1.0, help="report files at least this big (default 1)")
    s.add_argument("--old-years", type=float, default=3.0,
                   help="report files of 100 MB+ untouched for this long (default 3)")
    s.add_argument("--download-days", type=int, default=180,
                   help="installers/archives in Downloads older than this are candidates (default 180)")
    s.add_argument("--no-dupes", action="store_true", help="skip the duplicate-file hashing")
    s.set_defaults(func=cmd_scan)
    r = sub.add_parser("recycle", help="send rows marked approve=y to the Recycle Bin")
    r.add_argument("csv", help="candidates.csv from a scan, with approve filled in")
    r.add_argument("--apply", action="store_true",
                   help="actually send to the Recycle Bin (without it: dry run)")
    r.add_argument("--log", help="log file (default: <csv>.recycle-log.tsv)")
    r.set_defaults(func=cmd_recycle)
    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
