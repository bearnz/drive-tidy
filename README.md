# drive-tidy

Find clean-up candidates on a Windows drive, then send only the ones you
approve to the Recycle Bin. Built from the October 2026 one-off clean-ups of
C:, E:, N:, A: and M: (their scripts are in [`reference/`](reference/)).
Python 3.10+, standard library only. Plex media folders are
[media-tidy](https://github.com/bearnz/media-tidy)'s job, not this one's.

The split is the same as in those sessions: the tool finds and checks, you
decide. Uninstalling games, deleting recordings and anything else that needs
judgement stays with you. Nothing is ever deleted permanently: emptying the
Recycle Bin is up to you.

## Running

```
uv run drive-tidy scan E:
```

Read-only. Writes a folder `drive-tidy-E-<date>-<time>\` (or `--out <folder>`) with:

- `report.md`: biggest folders (depth 1-3), large files (1 GB+), old files
  (100 MB+, untouched for 3 years), duplicate groups, Steam games by size with
  last-played dates, and the candidates below.
- `candidates.csv`: one row per candidate, `approve` column empty.

Put `y` in the `approve` column of the rows to bin, then:

```
uv run drive-tidy recycle drive-tidy-E-<date>-<time>\candidates.csv
uv run drive-tidy recycle drive-tidy-E-<date>-<time>\candidates.csv --apply
```

The first is a dry run that prints what would happen. `--apply` sends each
approved row to the Recycle Bin and appends every result to
`candidates.recycle-log.tsv` beside the CSV.

Options: `scan --big-gb 1 --old-years 3 --download-days 180 --no-dupes`,
`recycle --log <file>`. `drive-tidy scan <folder>` scans a folder instead of a
whole drive.

## Candidate categories

| Category | What | From |
|---|---|---|
| `steam-orphan-folder` | folder in `steamapps\common` that no `appmanifest_*.acf` claims (game uninstalled, folder left behind). Never `Steam Controller Configs` or `Steamworks Shared`. | E:, N:, M: |
| `game-log-dump` | `.log`, `.dmp`, `.mdmp`, `output_log*.txt` inside an installed game's folder | E: |
| `bundled-redist` | `.exe`/`.msi`/`.cab` under `_CommonRedist`, `Redist`, `DirectX`, `VCRedist`, ... in a game folder (not EA's `__Installer`, which runs at launch). Steam may put them back when it verifies the game. | E: |
| `old-windows-leftover` | `WINDOWS`, `ProgramData`, `MSOCache`, `msdownld.tmp` and the VC++ 2008 installer files (`eula.*.txt`, `install.*`, `VC_RED.*`, ...) at the top of the scanned drive. Never on the system drive. | E:, N: |
| `steam-empty-folder` | empty folder under `steamapps\temp`, `shadercache` or `workshop\content` for an app not installed in that library (never 241100, Steam Controller Configs) | E: |
| `maven-target` | a `target` folder with a `pom.xml` beside it | A: |
| `old-download` | installer or archive (`.exe .msi .zip .rar .7z .iso .img .tar .gz .cab`) in a drive's `Downloads` or a user's `Users\<name>\Downloads`, older than 180 days. Mod managers' `downloads` folders are not included. | N:, A: |
| `duplicate` | an extra byte-identical copy (size, then partial hash, then full hash) that sits in a `Downloads` folder. The copy outside Downloads, or the one without ` (1)`, is kept. Other duplicate groups are only listed in the report. | N: |
| `extracted-zip` | a `.zip` whose every file is in the folder of the same name beside it, matched by size and CRC-32 in any subfolder. A zip with only some of its files there is listed under "kept" with what's missing. | N: |
| `source-download-cache` | the `download` folder beside a Source game's `gameinfo.txt` (TF2's `tf\download`): maps and sprays from community servers | M: |
| `crash-dump` | files in `AppData\Local\CrashDumps` (Windows Error Reporting) | C: |
| `shader-cache` | `*.ushaderprecache` files, and `ShaderCache` folders in a game's own folder (one or two levels under `AppData\Local` or `Documents\My Games`). Browser and WebView2 profiles (`User Data`, `EBWebView`, ...) are never listed. | C: |
| `installer-temp` | `AppData\Local\SquirrelTemp` | C: |
| `dev-cache` | `.m2\repository` (Maven) and `.p2` (Eclipse bundle pool: only if no Eclipse-based app is installed) | C: |

Cache folders (`shader-cache`, `installer-temp`, `dev-cache`) written to in the
last 7 days are kept rather than listed.

The report's Steam section lists every game folder with its size and when it
was last played, from Steam's own `localconfig.vdf` (all local accounts). It
also says whether Steam still lists each library (`libraryfolders.vdf`).
Uninstalling stays your call, in Steam.

## Safety rules

- **Never touched:** `System Volume Information`, `$RECYCLE.BIN`, `WindowsApps`,
  `WpSystem`, drive roots, and junctions/symlinks (not followed, and a folder
  holding one is never a candidate). Files Windows marks as reparse points,
  such as OneDrive online-only files, are skipped too. Nothing under
  `AppData\Local\Temp` is ever a candidate (in-progress installers, other
  tools' scratch files).
- **Saves are never candidates:** any path under a folder named like `Saves`,
  `SaveGames`, `Saved`, `Saved Games`, `savedata`, `userdata`, `memcards`,
  `remote`, or a file like `*.sav`, `*.ess`, `*.fos`, `*.ps2`, `*.mcd`, `*.srm`,
  `*.state`. A folder candidate that holds one is listed under "Matched a category
  but kept" instead.
- **Duplicates** skip Steam libraries, `Windows`, `Program Files*`,
  `ProgramData`, `AppData`, `node_modules`, `.git`, `.venv` and files under 1 MB.
  Games ship their own copies on purpose.
- **`recycle` re-checks every approved row** against the disk before moving it:
  - `MISSING` if it's gone.
  - `CHANGED` if its size differs from the scan (re-scan first).
  - `REFUSED` for anything protected or save-like, or a folder holding a junction.
  - `LONG-PATH` if a path inside is 260+ characters: the shell may delete such
    items outright instead of recycling them.
  - `TOO-BIG-FOR-BIN` if it won't fit in that drive's Recycle Bin, and `REFUSED`
    if the bin is turned off for the drive.
- **Sending** uses `SHFileOperationW` with `FOF_ALLOWUNDO` (recycle) and
  `FOF_WANTNUKEWARNING`. If Windows would delete an item permanently instead of
  recycling it, it shows a warning you can cancel (logged as `ABORTED`).
- **After each item**, the drive's Recycle Bin must have gained an item
  (`SHQueryRecycleBinW`). If the item is gone but the bin didn't grow, the run
  stops with `NOT-IN-BIN` and exit code 2. This guards against what happened to
  Anypoint Studio on A:, which was deleted outright by a "send to Recycle Bin" call.

Edit the CSV in a text editor, or in Excel saved as "CSV UTF-8". Plain
"CSV (Comma delimited)" is also read (as cp1252), but paths with non-Latin
characters won't match and show as `MISSING`.

## Testing

```
uv run pytest
```

The tests build fake drives (and a fake Steam client) in temp folders and use a
stand-in Recycle Bin, so they never touch the real one or read your Steam data. One opt-in test sends a temp file to the real
Recycle Bin on C: (`DRIVE_TIDY_REAL_BIN=1 uv run pytest`).
