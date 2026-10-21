"""Send approved candidates to the Recycle Bin. Never deletes permanently.

Every approved row is re-checked against the disk first. After each send the
drive's Recycle Bin must have gained an item; if it hasn't, the item may have
been deleted outright, so the run stops there.
"""
import csv
import ctypes
import os
import sys
import time
from ctypes import wintypes

from . import rules, scan

APPROVED = {"y", "yes", "x", "1", "true"}
MAX_PATH = 260
LOG_FIELDS = ["time", "status", "category", "size_bytes", "path", "detail"]

# shellapi.h (Windows SDK 10.0.20348.0)
FO_DELETE = 0x0003
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMMKDIR = 0x0200
FOF_NOERRORUI = 0x0400
FOF_WANTNUKEWARNING = 0x4000
# Recycle, no "are you sure", but warn (and let Josh cancel) if Windows would
# permanently delete instead of recycling.
SEND_FLAGS = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_WANTNUKEWARNING | FOF_SILENT | FOF_NOCONFIRMMKDIR

BITBUCKET = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume"


class SHFILEOPSTRUCTW(ctypes.Structure):
    if sys.maxsize <= 2**32:
        _pack_ = 1
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.WORD), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID), ("lpszProgressTitle", wintypes.LPCWSTR)]


class SHQUERYRBINFO(ctypes.Structure):
    if sys.maxsize <= 2**32:
        _pack_ = 1
    _fields_ = [("cbSize", wintypes.DWORD), ("i64Size", ctypes.c_longlong),
                ("i64NumItems", ctypes.c_longlong)]


class WindowsBin:
    """The real Recycle Bin, through shell32."""

    def query(self, drive_root):
        """(items, bytes) in that drive's bin, or None if it has none."""
        info = SHQUERYRBINFO(cbSize=ctypes.sizeof(SHQUERYRBINFO))
        rc = ctypes.windll.shell32.SHQueryRecycleBinW(drive_root, ctypes.byref(info))
        return None if rc != 0 else (info.i64NumItems, info.i64Size)

    def settings(self, drive_root):
        """(max_bytes, nuke_on_delete) from the registry, or (None, None)."""
        import winreg
        buf = ctypes.create_unicode_buffer(64)
        if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive_root, buf, 64):
            return None, None
        guid = buf.value[buf.value.find("{"):buf.value.find("}") + 1]
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BITBUCKET + "\\" + guid) as k:
                mb = winreg.QueryValueEx(k, "MaxCapacity")[0]
                try:
                    nuke = winreg.QueryValueEx(k, "NukeOnDelete")[0]
                except OSError:
                    nuke = 0
        except OSError:
            return None, None
        return mb * (1 << 20), bool(nuke)

    def send(self, path):
        """(return code, aborted). The caller verifies the result."""
        src = ctypes.create_unicode_buffer(path + "\0")  # buffer adds the second null
        op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=ctypes.cast(src, wintypes.LPCWSTR),
                             fFlags=SEND_FLAGS)
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return rc, bool(op.fAnyOperationsAborted)


def read_rows(csv_path):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(csv_path, newline="", encoding=enc) as fh:
                return list(csv.DictReader(fh)), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"cannot read {csv_path} as UTF-8 or cp1252")


def is_approved(row):
    return (row.get("approve") or "").strip().lower() in APPROVED


def measure(path):
    """Re-read an item from disk: (size, files, problems, longest path)."""
    if os.path.isfile(path):
        return os.path.getsize(path), 1, [], len(path)
    res = scan.Result(root=path, started=0)
    size = files = saves = reparse = 0
    longest = len(path)
    for d, fs, _subdirs, rp in scan.walk(path, res):
        reparse += rp
        dir_is_save = rules.is_save_path(os.path.join(d, "x"))
        for name, s, _m in fs:
            size += s
            files += 1
            longest = max(longest, len(d) + 1 + len(name))
            if dir_is_save or rules.is_save_path(name):
                saves += 1
    problems = []
    if saves:
        problems.append(f"holds {saves} save-like file(s)")
    if reparse:
        problems.append("holds a junction or symlink")
    if any(why == "skipped folder" for _p, why in res.skipped):
        problems.append("holds a protected folder")
    if res.errors:
        problems.append(f"{len(res.errors)} unreadable path(s) inside")
    return size, files, problems, longest


def check(row, binapi):
    """Return (status, detail, size). status 'READY' means safe to send."""
    path = (row.get("path") or "").strip()
    try:
        expected = int(float(row.get("size_bytes") or "-1"))
    except ValueError:
        expected = -1
    if not path or not os.path.isabs(path):
        return "BAD-ROW", "path is empty or not absolute", 0
    if rules.is_protected_path(path):
        return "REFUSED", "drive root or protected folder", 0
    if rules.is_save_path(path):
        return "REFUSED", "looks like a save game", 0
    if not os.path.lexists(path):
        return "MISSING", "not on disk any more", 0
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        attrs = 0
    if attrs & scan.REPARSE or os.path.islink(path):
        return "REFUSED", "is a junction or symlink", 0
    kind = "dir" if os.path.isdir(path) else "file"
    if row.get("kind") and row["kind"] != kind:
        return "CHANGED", f"was a {row['kind']}, now a {kind}", 0
    size, _files, problems, longest = measure(path)
    if problems:
        return "REFUSED", "; ".join(problems), size
    if size != expected:
        return "CHANGED", f"size was {expected} at scan, now {size}; re-scan first", size
    if longest >= MAX_PATH:
        return "LONG-PATH", f"a path inside is {longest} chars; the shell may delete it instead of recycling", size
    drive = os.path.splitdrive(path)[0] + "\\"
    q = binapi.query(drive)
    if q is None:
        return "REFUSED", f"no Recycle Bin on {drive}", size
    max_bytes, nuke = binapi.settings(drive)
    if nuke:
        return "REFUSED", f"Recycle Bin is turned off on {drive}", size
    if max_bytes is not None and q[1] + size > max_bytes:
        return "TOO-BIG-FOR-BIN", f"{drive} bin holds at most {max_bytes >> 20} MB", size
    return "READY", "", size


def _wait_for_bin(binapi, drive, before, timeout=5.0):
    end = time.time() + timeout
    while True:
        q = binapi.query(drive)
        if q and q[0] > before:
            return True
        if time.time() >= end:
            return False
        time.sleep(0.25)


def run(csv_path, apply=False, log_path=None, binapi=None, out=print, wait=5.0):
    """Recycle the approved rows of csv_path. Returns the list of
    (status, row, detail). Without apply it only reports what would happen."""
    binapi = binapi or WindowsBin()
    rows, enc = read_rows(csv_path)
    if enc != "utf-8-sig":
        out(f"note: read {csv_path} as {enc}; paths with non-Latin characters may not match")
    approved = [r for r in rows if is_approved(r)]
    out(f"{len(approved)} of {len(rows)} rows approved" + ("" if apply else " (dry run: nothing will move)"))
    log_path = log_path or os.path.splitext(csv_path)[0] + ".recycle-log.tsv"
    results = []
    log = None
    if apply:
        new = not os.path.exists(log_path)
        log = open(log_path, "a", newline="", encoding="utf-8")
        writer = csv.DictWriter(log, LOG_FIELDS, delimiter="\t")
        if new:
            writer.writeheader()

    def record(status, row, detail, size):
        results.append((status, row, detail))
        out(f"{status:15} {row.get('path', '')}" + (f"  ({detail})" if detail else ""))
        if log:
            writer.writerow({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "status": status,
                             "category": row.get("category", ""), "size_bytes": size,
                             "path": row.get("path", ""), "detail": detail})
            log.flush()

    try:
        for row in approved:
            status, detail, size = check(row, binapi)
            if status != "READY":
                record(status, row, detail, size)
                continue
            if not apply:
                record("WOULD-RECYCLE", row, "", size)
                continue
            path = row["path"].strip()
            drive = os.path.splitdrive(path)[0] + "\\"
            before = binapi.query(drive)[0]
            rc, aborted = binapi.send(path)
            if aborted:
                record("ABORTED", row, "cancelled (for example at a permanent-delete warning)", size)
            elif rc != 0:
                record("FAILED", row, f"SHFileOperation returned 0x{rc:x}", size)
            elif os.path.lexists(path):
                record("STILL-THERE", row, "send reported success but the item is still there", size)
            elif not _wait_for_bin(binapi, drive, before, wait):
                record("NOT-IN-BIN", row, "gone, but the Recycle Bin did not gain an item; stopping", size)
                break
            else:
                record("OK", row, "in the Recycle Bin", size)
    finally:
        if log:
            log.close()
    counts = {}
    for s, _r, _d in results:
        counts[s] = counts.get(s, 0) + 1
    out("summary: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) if counts else "summary: nothing to do")
    if apply:
        out(f"log: {log_path}")
    return results
