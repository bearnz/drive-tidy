import csv
import os
import shutil

import pytest

from drive_tidy import recycle, report, scan
from drive_tidy.cli import drive_root


class FakeBin:
    """Stands in for the Recycle Bin: 'recycling' moves the item into a folder."""

    def __init__(self, store, max_bytes=1 << 40, nuke=False, lose=False):
        self.store = store
        self.items = 0
        self.max_bytes = max_bytes
        self.nuke = nuke
        self.lose = lose  # simulate Windows deleting outright instead of recycling
        self.sent = []

    def query(self, drive_root):
        return (self.items, 0)

    def settings(self, drive_root):
        return self.max_bytes, self.nuke

    def send(self, path):
        self.sent.append(path)
        if self.lose:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        else:
            shutil.move(path, os.path.join(self.store, f"{self.items}-{os.path.basename(path)}"))
            self.items += 1
        return 0, False


def write(path, data=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, report.CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in report.CSV_FIELDS})
    return path


def row(path, approve="y", **kw):
    if os.path.isdir(path):
        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)
        kind = "dir"
    else:
        size, kind = os.path.getsize(path), "file"
    return {"approve": approve, "category": "test", "kind": kind, "size_bytes": size,
            "path": str(path), **kw}


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "data"
    store = tmp_path / "bin"
    store.mkdir()
    return data, FakeBin(str(store)), tmp_path


def run(csv_path, binapi, apply=True):
    lines = []
    res = recycle.run(str(csv_path), apply=apply, binapi=binapi, out=lines.append, wait=0.1)
    return {os.path.basename(r["path"]): s for s, r, _d in res}, lines


def test_only_approved_rows_move(env):
    data, fake, tmp = env
    a = write(data / "a.log")
    b = write(data / "b.log")
    folder = data / "old"
    write(folder / "x.dat", b"12345")
    c = make_csv(tmp / "c.csv", [row(a), row(b, approve=""), row(folder, approve="Yes")])
    status, _ = run(c, fake)
    assert status == {"a.log": "OK", "old": "OK"}
    assert not a.exists() and b.exists() and not folder.exists()
    log = (tmp / "c.recycle-log.tsv").read_text(encoding="utf-8").splitlines()
    assert log[0].split("\t") == recycle.LOG_FIELDS
    assert [line.split("\t")[1] for line in log[1:]] == ["OK", "OK"]


def test_dry_run_moves_nothing(env):
    data, fake, tmp = env
    a = write(data / "a.log")
    c = make_csv(tmp / "c.csv", [row(a)])
    status, lines = run(c, fake, apply=False)
    assert status == {"a.log": "WOULD-RECYCLE"}
    assert a.exists() and fake.sent == []
    assert not (tmp / "c.recycle-log.tsv").exists()
    assert "dry run" in lines[0]


def test_changed_and_missing_are_skipped(env):
    data, fake, tmp = env
    grown = data / "grown"
    write(grown / "one.bin", b"1")
    r = row(grown)
    write(grown / "two.bin", b"22")        # a new file arrived after the scan
    gone = write(data / "gone.txt")
    r2 = row(gone)
    gone.unlink()
    c = make_csv(tmp / "c.csv", [r, r2])
    status, _ = run(c, fake)
    assert status == {"grown": "CHANGED", "gone.txt": "MISSING"}
    assert grown.exists() and fake.sent == []


def test_refuses_saves_roots_and_protected(env):
    data, fake, tmp = env
    save_folder = data / "Game"
    write(save_folder / "SaveGames" / "slot.sav")
    sav = write(data / "slot2.sav")
    prot = write(data / "WindowsApps" / "x.exe")
    c = make_csv(tmp / "c.csv", [row(save_folder), row(sav), row(prot),
                                 {"approve": "y", "path": "E:\\", "size_bytes": "0"},
                                 {"approve": "y", "path": "relative\\x.txt", "size_bytes": "0"}])
    status, _ = run(c, fake)
    assert status == {"Game": "REFUSED", "slot2.sav": "REFUSED", "x.exe": "REFUSED",
                      "": "REFUSED", "x.txt": "BAD-ROW"}
    assert fake.sent == []


def test_refuses_folder_holding_a_junction(env):
    import subprocess
    data, fake, tmp = env
    target = data / "target"
    write(target / "keep.txt")
    holder = data / "holder"
    holder.mkdir(parents=True)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(holder / "j"), str(target)],
                   check=True, capture_output=True)
    c = make_csv(tmp / "c.csv", [row(holder, size_bytes=0)])
    status, _ = run(c, fake)
    assert status == {"holder": "REFUSED"}
    assert (target / "keep.txt").exists()


def test_bin_capacity_and_nuke_setting(env):
    data, fake, tmp = env
    a = write(data / "a.bin", b"x" * 100)
    c = make_csv(tmp / "c.csv", [row(a)])
    fake.max_bytes = 50
    assert run(c, fake)[0] == {"a.bin": "TOO-BIG-FOR-BIN"}
    fake.max_bytes, fake.nuke = 1 << 40, True
    assert run(c, fake)[0] == {"a.bin": "REFUSED"}
    assert a.exists()


def test_long_paths_refused(env):
    data, fake, tmp = env
    deep = data / "deep"
    p = deep
    while len(str(p)) < 235:  # folders stay under MAX_PATH, the file goes over it
        p = p / ("d" * 20)
    long_file = "\\\\?\\" + str(p / "file-with-a-long-name-that-goes-over.txt")
    os.makedirs("\\\\?\\" + str(p), exist_ok=True)
    with open(long_file, "wb") as fh:
        fh.write(b"x")
    c = make_csv(tmp / "c.csv", [{"approve": "y", "kind": "dir", "size_bytes": 1, "path": str(deep)}])
    assert run(c, fake)[0] == {"deep": "LONG-PATH"}
    shutil.rmtree("\\\\?\\" + str(deep))


def test_stops_when_bin_does_not_grow(env):
    data, fake, tmp = env
    a = write(data / "a.log")
    b = write(data / "b.log")
    fake.lose = True
    c = make_csv(tmp / "c.csv", [row(a), row(b)])
    status, lines = run(c, fake)
    assert status == {"a.log": "NOT-IN-BIN"}
    assert b.exists() and fake.sent == [str(a)]


def test_scan_csv_round_trip(env):
    """A scan's own CSV, approved as-is, recycles exactly its candidates."""
    data, fake, tmp = env
    write(data / "ws" / "p" / "pom.xml")
    write(data / "ws" / "p" / "target" / "app.jar", b"j" * 10)
    res = scan.scan(str(data), scan.Options(hash_dupes=False))
    c = tmp / "candidates.csv"
    report.write_csv(res, c)
    with open(c, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["approve"] = "y"
    make_csv(c, rows)
    assert run(c, fake)[0] == {"target": "OK"}
    assert (data / "ws" / "p" / "pom.xml").exists()


def test_cp1252_csv_is_read(env):
    data, fake, tmp = env
    a = write(data / "a.log")
    c = tmp / "c.csv"  # as Excel's plain "CSV (Comma delimited)" saves it
    c.write_bytes(f"approve,kind,size_bytes,path,reason\ny,file,1,{a},café\n".encode("cp1252"))
    status, lines = run(c, fake, apply=False)
    assert status["a.log"] == "WOULD-RECYCLE"
    assert any("cp1252" in line for line in lines)


@pytest.mark.parametrize("arg", ["E", "e:", "E:\\", "E:/"])
def test_drive_root(arg):
    assert drive_root(arg) == "E:\\"


@pytest.mark.skipif(os.environ.get("DRIVE_TIDY_REAL_BIN") != "1",
                    reason="sends a temp file to the real Recycle Bin; set DRIVE_TIDY_REAL_BIN=1")
def test_real_recycle_bin(tmp_path):
    f = write(tmp_path / "drive-tidy-test-file.txt", b"drive-tidy real bin test")
    c = make_csv(tmp_path / "c.csv", [row(f)])
    res = recycle.run(str(c), apply=True, out=lambda *_: None)
    assert [s for s, _r, _d in res] == ["OK"]
    assert not f.exists()
