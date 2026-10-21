"""Read-only drive scan. Nothing in this module writes to the scanned drive."""
import os
import re
import stat
import time
from collections import defaultdict
from dataclasses import dataclass, field

from . import dupes, rules
from .steam import CONTROLLER_CONFIGS_APPID, Library

MiB = 1 << 20
GiB = 1 << 30
DAY = 86400

LOG_EXT = {".log", ".dmp", ".mdmp"}
REDIST_DIR = re.compile(
    r"^(_commonredist|redist|redistributables?|prerequisites|directx|vcredist)$", re.I
)
REDIST_EXT = {".exe", ".msi", ".cab"}
ARCHIVE_EXT = {".exe", ".msi", ".zip", ".rar", ".7z", ".iso", ".img", ".tar", ".gz", ".cab"}
# Folders and files that old Windows installs and installers leave at a drive root.
ROOT_LEFTOVER_DIRS = {"windows", "programdata", "msocache", "msdownld.tmp"}
ROOT_LEFTOVER_FILE = re.compile(
    r"^(eula\.\d+\.txt|install\.(exe|ini)|install\.res\.\d+\.dll|globdata\.ini|vcredist\.bmp|vc_red\.(cab|msi))$",
    re.I,
)
# Areas where duplicate files are expected (games and installed software ship
# their own copies), so they are left out of the duplicate search.
NO_DUP_DIRS = {"steamapps", "windows", "program files", "program files (x86)", "programdata",
               "appdata", "node_modules", ".git", ".venv", "site-packages"}
REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


@dataclass
class Options:
    big: int = 1 * GiB              # report files at least this big
    old_min: int = 100 * MiB        # report old files at least this big ...
    old_days: int = 3 * 365         # ... not modified in this many days
    dup_min: int = 1 * MiB          # smallest file worth a duplicate check
    download_days: int = 180        # Downloads installers/archives older than this
    hash_dupes: bool = True


@dataclass
class Totals:
    size: int = 0
    files: int = 0
    newest: float = 0.0
    saves: int = 0
    reparse: int = 0

    def add(self, other):
        self.size += other.size
        self.files += other.files
        self.newest = max(self.newest, other.newest)
        self.saves += other.saves
        self.reparse += other.reparse


@dataclass
class Result:
    root: str
    started: float
    seconds: float = 0.0
    errors: list = field(default_factory=list)
    skipped: list = field(default_factory=list)    # skipped dirs and reparse points
    dirs: dict = field(default_factory=dict)        # path -> Totals (whole subtree)
    big_files: list = field(default_factory=list)   # (size, mtime, path)
    old_files: list = field(default_factory=list)
    dup_groups: list = field(default_factory=list)  # (size, [paths])
    candidates: list = field(default_factory=list)  # dicts, see _cand
    kept: list = field(default_factory=list)        # (category, path, why)
    libraries: list = field(default_factory=list)


def _is_reparse(entry):
    try:
        return bool(entry.stat(follow_symlinks=False).st_file_attributes & REPARSE)
    except (OSError, AttributeError):
        return entry.is_symlink()


def walk(root, res):
    """Yield (dirpath, [(name, size, mtime)], [subdir names], reparse count)
    without following junctions or symlinks and without entering skipped folders."""
    stack = [root]
    while stack:
        d = stack.pop()
        files, subdirs, reparse = [], [], 0
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except OSError as e:
            res.errors.append(f"{d}: {e.strerror or e}")
            continue
        for e in entries:
            try:
                if _is_reparse(e):
                    res.skipped.append((e.path, "junction/symlink, not followed"))
                    reparse += 1
                elif e.is_dir():
                    if rules.is_skipped_dir(e.name):
                        res.skipped.append((e.path, "skipped folder"))
                    else:
                        subdirs.append(e.name)
                else:
                    st = e.stat(follow_symlinks=False)
                    files.append((e.name, st.st_size, st.st_mtime))
            except OSError as err:
                res.errors.append(f"{e.path}: {err.strerror or err}")
        yield d, files, subdirs, reparse
        stack.extend(os.path.join(d, s) for s in reversed(subdirs))


def _cand(res, category, path, reason, kind=None):
    t = res.dirs.get(path)
    if kind is None:
        kind = "dir" if t is not None else "file"
    if kind == "dir":
        size, newest = t.size, t.newest
        if t.saves:
            res.kept.append((category, path, f"holds {t.saves} save-like file(s)"))
            return
        if t.reparse:
            res.kept.append((category, path, "holds a junction or symlink"))
            return
    else:
        try:
            st = os.stat(path, follow_symlinks=False)
        except OSError as e:
            res.errors.append(f"{path}: {e.strerror or e}")
            return
        size, newest = st.st_size, st.st_mtime
    if rules.is_save_path(path):
        res.kept.append((category, path, "looks like a save"))
        return
    res.candidates.append({"category": category, "path": path, "kind": kind,
                           "size": size, "newest": newest, "reason": reason})


def _under(path, folder):
    return path.lower().startswith(folder.lower().rstrip("\\/") + os.sep)


def scan(root, opts=None, progress=None):
    opts = opts or Options()
    root = os.path.abspath(root)
    now = time.time()
    res = Result(root=root, started=now)
    own = {}                   # dir -> Totals for files directly in it
    by_size = defaultdict(list)
    log_hits, redist_hits, download_hits = [], [], []
    pom_dirs, target_dirs, steamapps = set(), [], []
    nfiles = 0
    root_depth = len(rules.path_parts(root))

    next_report = 20000
    for d, files, subdirs, reparse in walk(root, res):
        t = own[d] = Totals(reparse=reparse)
        parts_low = [p.lower() for p in rules.path_parts(d)]
        rel_low = parts_low[root_depth:]  # below the scan root
        no_dup = any(p in NO_DUP_DIRS for p in rel_low)
        in_steam = "steamapps" in rel_low  # game data: sized per game instead
        dl = "downloads" in parts_low
        # EA games run __Installer at launch, so its installers stay.
        redist_dir = any(REDIST_DIR.match(p) for p in rel_low) and "__installer" not in rel_low
        save_dir = rules.is_save_path(os.path.join(d, "x"))
        for s in subdirs:
            if s.lower() == "steamapps":
                steamapps.append(os.path.join(d, s))
            elif s.lower() == "target":
                target_dirs.append(os.path.join(d, s))
        for name, size, mtime in files:
            p = os.path.join(d, name)
            low = name.lower()
            ext = os.path.splitext(low)[1]
            t.size += size
            t.files += 1
            t.newest = max(t.newest, mtime)
            if save_dir or ext in rules.SAVE_EXT:
                t.saves += 1
            if low == "pom.xml":
                pom_dirs.add(d.lower())
            if size >= opts.big and not in_steam:
                res.big_files.append((size, mtime, p))
            elif size >= opts.old_min and not in_steam and now - mtime > opts.old_days * DAY:
                res.old_files.append((size, mtime, p))
            if size >= opts.dup_min and not no_dup:
                by_size[size].append(p)
            if ext in LOG_EXT or (low.startswith("output_log") and ext == ".txt"):
                log_hits.append(p)
            if redist_dir and ext in REDIST_EXT:
                redist_hits.append(p)
            if dl and ext in ARCHIVE_EXT and now - mtime > opts.download_days * DAY:
                download_hits.append((p, mtime))
        nfiles += len(files)
        if progress and nfiles >= next_report:
            progress(f"{nfiles:,} files, at {d}")
            next_report += 20000

    # Roll each folder's own totals up into its parents.
    res.dirs = {d: Totals(t.size, t.files, t.newest, t.saves, t.reparse) for d, t in own.items()}
    for d in sorted(own, key=lambda p: -p.count(os.sep)):
        parent = os.path.dirname(d)
        if d != root and parent in res.dirs:
            res.dirs[parent].add(res.dirs[d])

    _steam(res, steamapps, log_hits, redist_hits)
    _root_leftovers(res, root)
    for t in target_dirs:
        if os.path.dirname(t).lower() in pom_dirs:
            _cand(res, "maven-target", t, "Maven build output beside a pom.xml; a rebuild recreates it")
    for p, mtime in download_hits:
        age = int((now - mtime) // DAY)
        _cand(res, "old-download", p, f"installer/archive in Downloads, {age} days old")

    if opts.hash_dupes:
        if progress:
            progress(f"hashing {sum(len(v) for v in by_size.values() if len(v) > 1):,} same-size files")
        res.dup_groups = dupes.find_groups(by_size)
        for size, paths in res.dup_groups:
            keep, *extra = sorted(paths, key=dupes.keep_rank)
            for p in extra:
                if dupes.in_downloads(p):
                    _cand(res, "duplicate", p, f"byte-identical (full hash) to {keep}", kind="file")

    res.seconds = time.time() - now
    return res


def _steam(res, steamapps, log_hits, redist_hits):
    installed = []
    for sa in steamapps:
        lib = Library(sa)
        res.libraries.append(lib)
        for folder, ok in lib.game_folders():
            if ok:
                installed.append(folder)
            else:
                _cand(res, "steam-orphan-folder", folder,
                      "in steamapps\\common but no appmanifest claims it (game uninstalled)")
        for sub in ("temp", "shadercache", os.path.join("workshop", "content")):
            base = os.path.join(sa, sub)
            try:
                names = os.listdir(base)
            except OSError:
                continue
            for n in names:
                p = os.path.join(base, n)
                t = res.dirs.get(p)
                if t is None or t.files or t.reparse:
                    continue
                if n in lib.app_ids or n == CONTROLLER_CONFIGS_APPID:
                    continue
                _cand(res, "steam-empty-folder", p, f"empty, and app {n} is not installed here")

    def game_of(p):
        return next((g for g in installed if _under(p, g)), None)

    for p in log_hits:
        g = game_of(p)
        if g:
            _cand(res, "game-log-dump", p, f"log/crash dump in {os.path.basename(g)}", kind="file")
    for p in redist_hits:
        g = game_of(p)
        if g:
            _cand(res, "bundled-redist", p,
                  f"redist installer bundled with {os.path.basename(g)}; Steam may restore it on verify",
                  kind="file")


def _root_leftovers(res, root):
    drive, tail = os.path.splitdrive(root)
    system = os.environ.get("SystemDrive", "C:").rstrip("\\").lower()
    if tail.strip("\\/") == "" and drive.lower() == system:
        return  # these names are live on the system drive
    try:
        names = os.listdir(root)
    except OSError:
        return
    for n in names:
        p = os.path.join(root, n)
        if n.lower() in ROOT_LEFTOVER_DIRS and p in res.dirs:
            _cand(res, "old-windows-leftover", p, "left at the drive root by an old Windows install")
        elif ROOT_LEFTOVER_FILE.match(n) and os.path.isfile(p):
            _cand(res, "old-windows-leftover", p, "Visual C++ 2008 installer file extracted to the drive root")
