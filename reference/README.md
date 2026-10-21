# reference/

The throwaway scripts from the October 2026 drive clean-up sessions that
`drive-tidy` was built from. They are kept as found (paths and all) and are
not used by the package. Several have one-off paths hard-coded and should not be
re-run as they are.

| Folder | Session | Scripts |
|---|---|---|
| `c-drive-2026-10-15/` | first C: pass (also listed A:, E:, M:, N:) | `sizes.ps1`, `list.ps1` (robocopy /L listing), `analyze.ps1`, `analyze.py` |
| `e-drive/` | E: clean-up, 2026-10-19 | `scan.py` (sizes + duplicates), `summ.py`, `junk.py` (saves and junk tally), `cleanup.ps1` (approved list + `-Apply`) |
| `n-drive/` | N: clean-up, 2026-10-19 | `walk.py` (SQLite index), `dups.py` (partial then full hash), `build.py` (approved list), `recycle.ps1` |
| `a-drive/` | A: clean-up, 2026-10-20 | `compare_iso.ps1` (mount an ISO read-only, compare with extracted files), `copy_verify.ps1` (copy, SHA-256 check, then bin the source) |
| `c-drive-2026-10-19/` | second C: pass | `drill.py`, `summarise.py`, `recycle.ps1` (stops if the bin doesn't grow by the item's size) |

The scan outputs, recycle lists and logs those sessions produced are not in
the repo: they list personal files and are only useful as history.
