"""Steam last-played dates, C: caches, Source download caches, extracted zips."""
import os
import time
import zipfile

from drive_tidy import report, scan, vdf
from test_scan import OLD, cands, kept, manifest, write


def test_vdf_reader():
    d = vdf.loads('"Root"\n{\n\t"Valve" { "key" "a \\"q\\" b" // comment\n "path" "C:\\\\x" }\n}\n')
    assert vdf.get(d, "root", "valve", "key") == 'a "q" b'
    assert vdf.get(d, "ROOT", "Valve", "path") == "C:\\x"
    assert vdf.get(d, "root", "missing", "key") is None


def fake_steam(tmp_path, libraries, last_played):
    root = tmp_path / "SteamClient"
    entries = "".join(f'"{i}" {{ "path" "{str(p).replace(chr(92), chr(92) * 2)}" }}\n'
                      for i, p in enumerate(libraries))
    write(root / "steamapps" / "libraryfolders.vdf", f'"libraryfolders"\n{{\n{entries}}}\n'.encode())
    apps = "".join(f'"{a}" {{ "LastPlayed" "{t}" }}\n' for a, t in last_played.items())
    cfg = ('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {\n'
           + apps + "} } } } }\n")
    write(root / "userdata" / "123" / "config" / "localconfig.vdf", cfg.encode())
    write(root / "userdata" / "456" / "config" / "localconfig.vdf",
          '"UserLocalConfigStore" { "Software" { "valve" { "Steam" { "apps" { "10" { "LastPlayed" "5" } } } } } }'.encode())
    return str(root)


def test_last_played_and_unlisted_library(tmp_path):
    drive = tmp_path / "drive"
    listed = drive / "Steam" / "steamapps"
    unlisted = drive / "OldLibrary" / "steamapps"
    manifest(listed, "10", "Game A")
    manifest(listed, "20", "Game B")
    write(listed / "common" / "Game A" / "a.pak", b"a" * 30)
    write(listed / "common" / "Game B" / "b.pak", b"b" * 10)
    write(unlisted / "common" / "Leftover" / "x.pak")
    played = int(time.time()) - 10 * 86400
    root = fake_steam(tmp_path, [drive / "Steam"], {"10": played})
    res = scan.scan(str(drive), scan.Options(hash_dupes=False, steam_root=root))
    games = {os.path.basename(p): (ok, when) for _s, p, ok, _n, when, _l in res.games}
    assert games == {"Game A": (True, played), "Game B": (True, None), "Leftover": (False, None)}
    leftover = next(c for c in res.candidates if c["path"].endswith("Leftover"))
    assert "doesn't list this library" in leftover["reason"]
    out = tmp_path / "report.md"
    report.write_report(res, out)
    text = out.read_text(encoding="utf-8")
    assert "**not listed in Steam**" in text and "| never |" in text
    assert time.strftime("%Y-%m-%d", time.localtime(played)) in text


def test_steam_tool_folders_are_not_orphans(tmp_path):
    sa = tmp_path / "Steam" / "steamapps"
    write(sa / "common" / "Steam Controller Configs" / "1" / "config.vdf")
    write(sa / "common" / "Steamworks Shared" / "_CommonRedist" / "x.txt")
    write(sa / "common" / "Gone Game" / "x.pak")
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "steam-orphan-folder") == [os.path.join("Steam", "steamapps", "common", "Gone Game")]


def test_old_downloads_only_in_real_downloads_folders(tmp_path):
    write(tmp_path / "Users" / "Josh" / "Downloads" / "setup.exe", mtime=OLD)
    write(tmp_path / "Modding" / "Fallout4" / "downloads" / "mod-v1.7z", mtime=OLD)  # mod manager archive
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "old-download") == [os.path.join("Users", "Josh", "Downloads", "setup.exe")]


def test_no_steam_client_means_no_listing_claims(tmp_path):
    sa = tmp_path / "Lib" / "steamapps"
    write(sa / "common" / "Leftover" / "x.pak")
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert "doesn't list" not in res.candidates[0]["reason"]


def test_source_download_cache(tmp_path):
    sa = tmp_path / "steamapps"
    manifest(sa, "440", "Team Fortress 2")
    tf = sa / "common" / "Team Fortress 2" / "tf"
    write(tf / "gameinfo.txt")
    write(tf / "download" / "maps" / "koth_custom.bsp", b"m" * 20)
    write(tf / "maps" / "ctf_2fort.bsp")                   # official maps stay
    write(sa / "common" / "Other" / "mod" / "gameinfo.txt")  # orphan: covered by its folder
    write(sa / "common" / "Other" / "mod" / "download" / "x.bsp")
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "source-download-cache") == [
        os.path.join("steamapps", "common", "Team Fortress 2", "tf", "download")]


def test_c_drive_caches(tmp_path):
    local = tmp_path / "Users" / "Josh" / "AppData" / "Local"
    write(local / "CrashDumps" / "witcher3.exe.1234.dmp", b"d" * 5)
    write(local / "SquirrelTemp" / "Setup.exe", mtime=OLD)
    write(local / "Borderlands 3" / "ShaderCache" / "d3d12.bin", mtime=OLD)
    write(local / "NewApp" / "ShaderCache" / "fresh.bin")    # written today: kept
    write(tmp_path / "ProgramData" / "Hogwarts Legacy" / "D3DGraphics_V1.ushaderprecache", mtime=OLD)
    home = tmp_path / "Users" / "Josh"
    write(home / ".m2" / "repository" / "org" / "x.jar", mtime=OLD)
    write(home / ".m2" / "settings.xml", mtime=OLD)          # config, not cache
    write(home / ".p2" / "pool" / "plugins" / "y.jar", mtime=OLD)
    write(home / "Saved Games" / "ShaderCache" / "keep.bin", mtime=OLD)  # under a save folder
    write(home / "Documents" / "My Games" / "Outlaws" / "ShaderCache" / "s.bin", mtime=OLD)
    # browser and WebView2 profiles keep a ShaderCache of their own: never listed
    write(local / "Google" / "Chrome" / "User Data" / "ShaderCache" / "c.bin", mtime=OLD)
    write(local / "SomeApp" / "EBWebView" / "ShaderCache" / "w.bin", mtime=OLD)
    write(local / "Ubisoft Game Launcher" / "cache" / "http2" / "ShaderCache" / "u.bin", mtime=OLD)
    # anything under AppData\Local\Temp is left alone
    write(local / "Temp" / "CrashDumps" / "x.dmp")
    write(local / "Temp" / "pytest-of-Josh" / "ws" / "pom.xml")
    write(local / "Temp" / "pytest-of-Josh" / "ws" / "target" / "a.jar")
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    rel = lambda *p: os.path.join(*p)
    assert cands(res, "crash-dump") == [rel("Users", "Josh", "AppData", "Local", "CrashDumps", "witcher3.exe.1234.dmp")]
    assert cands(res, "installer-temp") == [rel("Users", "Josh", "AppData", "Local", "SquirrelTemp")]
    assert cands(res, "shader-cache") == sorted([
        rel("ProgramData", "Hogwarts Legacy", "D3DGraphics_V1.ushaderprecache"),
        rel("Users", "Josh", "AppData", "Local", "Borderlands 3", "ShaderCache"),
        rel("Users", "Josh", "Documents", "My Games", "Outlaws", "ShaderCache")])
    assert cands(res, "maven-target") == []
    assert cands(res, "dev-cache") == [rel("Users", "Josh", ".m2", "repository"), rel("Users", "Josh", ".p2")]
    assert rel("Users", "Josh", "AppData", "Local", "NewApp", "ShaderCache") in kept(res, "shader-cache")
    assert not any("Saved Games" in c["path"] for c in res.candidates)


def make_zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)


def test_extracted_zip(tmp_path):
    dl = tmp_path / "Downloads"
    members = {"photos/a.jpg": b"A" * 300, "photos/b.jpg": b"B" * 200, "readme.txt": b"hi"}
    make_zip(dl / "photos.zip", members)
    # extracted into different subfolders: still counts
    write(dl / "photos" / "a.jpg", members["photos/a.jpg"])
    write(dl / "photos" / "nested" / "b.jpg", members["photos/b.jpg"])
    write(dl / "photos" / "readme.txt", b"hi")
    # one file missing
    make_zip(dl / "album.zip", {"1.mp3": b"1" * 50, "note.txt": b"download complete"})
    write(dl / "album" / "1.mp3", b"1" * 50)
    # same size, different content
    make_zip(dl / "edited.zip", {"doc.txt": b"original"})
    write(dl / "edited" / "doc.txt", b"changed!")
    make_zip(dl / "lonely.zip", {"x": b"x"})                  # no folder beside it
    res = scan.scan(str(tmp_path), scan.Options(hash_dupes=False))
    assert cands(res, "extracted-zip") == [os.path.join("Downloads", "photos.zip")]
    assert kept(res, "extracted-zip") == [os.path.join("Downloads", "album.zip")]
    why = next(w for c, p, w in res.kept if c == "extracted-zip")
    assert "1 of 2" in why and "note.txt" in why
