# drive-tidy

Find clean-up candidates on a Windows drive (read-only scan), then send only the
rows Josh approves in the CSV to the Recycle Bin. Stdlib-only Python 3.10+.

## Running

```
uv run drive-tidy scan E: --out <folder>
uv run drive-tidy recycle <folder>\candidates.csv            # dry run
uv run drive-tidy recycle <folder>\candidates.csv --apply    # Josh's yes first
```

## Testing

```
uv run pytest
```

## Notes

- Never run `recycle --apply` on Josh's drives without his explicit yes for
  that CSV. Never delete permanently; emptying the bin is his job.
- Judgement calls (uninstalling games, recordings, media) stay with Josh.
  Plex media belongs to bearnz/media-tidy.
- Scan output (`drive-tidy-*/`) lists personal files: keep it out of git.
- `reference/` holds the original one-off scripts; not imported anywhere.
- Conventions are in ~/.claude/CLAUDE.md (feature branches -> PR -> main,
  push only on approval, provenance labels).
