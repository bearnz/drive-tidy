import csv
import os
import subprocess
import time

import pytest

from drive_tidy import dupes, report, scan

OLD = time.time() - 400 * 86400


def write(path, data=b"x", mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def manifest(steamapps, appid, installdir):
    write(steamapps / f"appmanifest_{appid}.acf",
          f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"installdir"\t\t"{installdir}"\n}}\n'.encode())


def cands(res, category):
    return sorted(os.path.relpath(c["path"], res.root) for c in res.candidates if c["category"] == category)


def kept(res, category):
    return sorted(os.path.relpath(p, res.root) for c, p, _ in res.kept if c == category)


@pytest.fixture
def steam_drive(tmp_path):
    sa = tmp_path / "steam" / "steamapps"
    manifest(sa, "10", "Game A")
    manifest(sa, "20", "game b")                     # case differs from the folder
    common = sa / "common"
    write(common / "Game A" / "game.exe")
    write(common / "Game A" / "output_log.txt")
    write(common / "Game A" / "crash.dmp")
    write(common / "Game A" / "Logs" / "run.log")
    write(common / "Game A" / "Saves" / "debug.log")  # save folder: never touched
    write(common / "Game A" / "_CommonRedist" / "vcredist" / "vc_redist.x64.exe")
    write(common / "Game A" / "_CommonRedist" / "readme.txt")
    write(common / "Game A" / "__Installer" / "redist" / "EAappInstaller.exe")  # run at launch
    write(common / "Game B" / "b.exe")
    write(common / "Old Game" / "data.pak", b"y" * 100)
    write(common / "Old Game" / "error.log")         # covered by the orphan folder
    write(common / "Saved Orphan" / "SaveGames" / "slot1.sav")
    (common / "Empty Orphan").mkdir()
    (sa / "temp" / "99").mkdir(parents=True)
    (sa / "temp" / "10").mkdir()                     # installed app: kept
    (sa / "shadercache" / "77").mkdir(parents=True)
    write(sa / "shadercache" / "78" / "cache.bin")   # not empty: kept
    (sa / "workshop" / "content" / "241100").mkdir(parents=True)  # controller configs
    (sa / "workshop" / "content" / "555").mkdir()
    return tmp_path


def test_steam_orphan_folders(steam_drive):
    res = scan.scan(str(steam_drive), scan.Options(hash_dupes=False))
    base = os.path.join("steam", "steamapps", "common")
    assert cands(res, "steam-orphan-folder") == [os.path.join(base, "Empty Orphan"),
                                                 os.path.join(base, "Old Game")]
    assert kept(res, "steam-orphan-folder") == [os.path.join(base, "Saved Orphan")]
    orphan = next(c for c in res.candidates if c["path"].endswith("Old Game"))
    assert orphan["kind"] == "dir" and orphan["size"] == 101


def test_logs_and_dumps_only_in_installed_games(steam_drive):
    res = scan.scan(str(steam_drive), scan.Options(hash_dupes=False))
    game = os.path.join("steam", "steamapps", "common", "Game A")
    assert cands(res, "game-log-dump") == [os.path.join(game, p) for p in
                                           ("Logs\\run.log", "crash.dmp", "output_log.txt")]
    assert kept(res, "game-log-dump") == [os.path.join(game, "Saves", "debug.log")]


def test_bundled_redist(steam_drive):
    res = scan.scan(str(steam_drive), scan.Options(hash_dupes=False))
    assert cands(res, "bundled-redist") == [
        os.path.join("steam", "steamapps", "common", "Game A", "_CommonRedist", "vcredist", "vc_redist.x64.exe")]


def test_empty_steam_folders(steam_drive):
    res = scan.scan(str(steam_drive), scan.Options(hash_dupes=False))
    sa = os.path.join("steam", "steamapps")
    assert cands(res, "steam-empty-folder") == [
        os.path.join(sa, "shadercache", "77"), os.path.join(sa, "temp", "99"),
        os.path.join(sa, "workshop", "content", "555")]


def test_maven_target_needs_pom(tmp_path):
    write(tmp_path / "ws" / "proj1" / "pom.xml")
    write(tmp_path / "ws" / "proj1" / "target" / "app.jar", b"j" * 10)
    write(tmp_path / "ws" / "proj2" / "target" / "notes.txt")  # no pom.xml
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "maven-target") == [os.path.join("ws", "proj1", "target")]


def test_root_leftovers(tmp_path):
    write(tmp_path / "WINDOWS" / "old.dll")
    write(tmp_path / "MSOCache" / "x.cab")
    (tmp_path / "msdownld.tmp").mkdir()
    write(tmp_path / "eula.1033.txt")
    write(tmp_path / "VC_RED.MSI")
    write(tmp_path / "install.exe")
    write(tmp_path / "keep.txt")
    write(tmp_path / "sub" / "WINDOWS" / "deeper.dll")  # only the scan root counts
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "old-windows-leftover") == sorted(
        ["MSOCache", "VC_RED.MSI", "WINDOWS", "eula.1033.txt", "install.exe", "msdownld.tmp"])


def test_root_leftovers_never_on_system_drive(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(scan, "_cand", lambda *a, **k: seen.append(a[2]))
    res = scan.Result(root="C:\\", started=0)
    monkeypatch.setenv("SystemDrive", "C:")
    scan._root_leftovers(res, "C:\\")
    assert seen == []


def test_old_downloads(tmp_path):
    write(tmp_path / "Downloads" / "setup.exe", mtime=OLD)
    write(tmp_path / "Downloads" / "pack.zip", mtime=OLD)
    write(tmp_path / "Downloads" / "new.zip")                 # too new
    write(tmp_path / "Downloads" / "photo.jpg", mtime=OLD)    # not an installer/archive
    write(tmp_path / "Other" / "old.zip", mtime=OLD)          # not in Downloads
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "old-download") == [os.path.join("Downloads", "pack.zip"),
                                          os.path.join("Downloads", "setup.exe")]


def test_duplicates_full_hash_and_keeper(tmp_path):
    mib = 1 << 20
    data = os.urandom(2 * mib)
    write(tmp_path / "Media" / "film.mkv", data)
    write(tmp_path / "Downloads" / "film.mkv", data)
    write(tmp_path / "Downloads" / "film (1).mkv", data)
    write(tmp_path / "Elsewhere" / "film-copy.mkv", data)
    # same size and same first/middle/last MiB, different in between
    a = bytearray(os.urandom(4 * mib))
    b = bytearray(a)
    b[mib + mib // 2] ^= 0xFF
    write(tmp_path / "Downloads" / "a.bin", bytes(a))
    write(tmp_path / "Downloads" / "b.bin", bytes(b))
    assert dupes.partial_hash(str(tmp_path / "Downloads" / "a.bin"), len(a)) == \
        dupes.partial_hash(str(tmp_path / "Downloads" / "b.bin"), len(b))
    res = scan.scan(str(tmp_path))
    assert len(res.dup_groups) == 1 and len(res.dup_groups[0][1]) == 4
    # the copy outside Downloads is kept; only Downloads copies are candidates
    assert cands(res, "duplicate") == [os.path.join("Downloads", "film (1).mkv"),
                                       os.path.join("Downloads", "film.mkv")]
    assert "Media" in next(c for c in res.candidates if c["category"] == "duplicate")["reason"]


def test_duplicates_skip_steam_and_small_files(tmp_path):
    data = os.urandom(1 << 20)
    write(tmp_path / "steamapps" / "common" / "G" / "a.pak", data)
    write(tmp_path / "steamapps" / "common" / "G" / "b.pak", data)
    write(tmp_path / "x" / "small1.txt", b"same")
    write(tmp_path / "x" / "small2.txt", b"same")
    assert scan.scan(str(tmp_path)).dup_groups == []


def test_skipped_folders_and_junctions_not_entered(tmp_path):
    write(tmp_path / "System Volume Information" / "big.bin", b"z" * 50)
    write(tmp_path / "$RECYCLE.BIN" / "S-1" / "$R1.txt", b"z" * 50)
    write(tmp_path / "WindowsApps" / "app.exe", b"z" * 50)
    write(tmp_path / "WpSystem" / "x.dat", b"z" * 50)
    write(tmp_path / "Target" / "real.bin", b"r" * 7)
    write(tmp_path / "Holder" / "own.txt", b"o")
    rc = subprocess.run(["cmd", "/c", "mklink", "/J", str(tmp_path / "Holder" / "link"),
                         str(tmp_path / "Target")], capture_output=True).returncode
    assert rc == 0
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert res.dirs[str(tmp_path)].size == 8           # Target counted once, nothing else
    assert res.dirs[str(tmp_path / "Holder")].reparse == 1
    reasons = {os.path.basename(p): why for p, why in res.skipped}
    assert reasons["link"].startswith("junction")
    assert {"System Volume Information", "$RECYCLE.BIN", "WindowsApps", "WpSystem"} <= set(reasons)


def test_big_and_old_files(tmp_path):
    write(tmp_path / "big.bin", b"b" * 2000)
    write(tmp_path / "old.bin", b"o" * 500, mtime=OLD)
    write(tmp_path / "new.bin", b"n" * 500)
    write(tmp_path / "steamapps" / "common" / "G" / "huge.pak", b"g" * 2000)  # sized per game
    res = scan.scan(str(tmp_path), scan.Options(big=1000, old_min=400, old_days=365, hash_dupes=False))
    assert [os.path.basename(p) for _s, _m, p in res.big_files] == ["big.bin"]
    assert [os.path.basename(p) for _s, _m, p in res.old_files] == ["old.bin"]


def test_report_and_csv(steam_drive, tmp_path_factory):
    res = scan.scan(str(steam_drive))
    out = tmp_path_factory.mktemp("out")
    report.write_report(res, out / "report.md")
    report.write_csv(res, out / "candidates.csv")
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "steam-orphan-folder" in text and "Saved Orphan" in text
    with open(out / "candidates.csv", newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(res.candidates)
    assert all(r["approve"] == "" for r in rows)
    assert {r["category"] for r in rows} >= {"steam-orphan-folder", "game-log-dump"}
