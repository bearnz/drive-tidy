"""Is a zip already extracted? Every member must be in the folder beside it
(same name as the zip) with the same size and CRC-32, in any subfolder."""
import os
import zipfile
import zlib
from collections import defaultdict


def _crc(path):
    crc = 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 << 20), b""):
            crc = zlib.crc32(block, crc)
    return crc


def check(zip_path, folder):
    """(found, total, missing names). total is 0 if the zip can't be read."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
    except (OSError, zipfile.BadZipFile, NotImplementedError, ValueError):
        return 0, 0, []
    from .scan import Result, walk  # scan imports this module
    by_size = defaultdict(list)
    for d, files, _subdirs, _reparse in walk(folder, Result(root=folder, started=0)):
        for name, size, _mtime in files:
            by_size[size].append(os.path.join(d, name))
    crcs = {}
    found, missing = 0, []
    for m in members:
        ok = False
        for p in by_size.get(m.file_size, []):
            try:
                if p not in crcs:
                    crcs[p] = _crc(p)
            except OSError:
                continue
            if crcs[p] == m.CRC:
                ok = True
                break
        if ok:
            found += 1
        else:
            missing.append(m.filename)
    return found, len(members), missing
