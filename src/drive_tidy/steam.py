"""Steam library facts read from a steamapps folder's appmanifest_*.acf files."""
import glob
import os
import re

INSTALLDIR = re.compile(r'"installdir"\s+"([^"]+)"', re.I)
# Steam Controller Configs keeps per-game controller layouts under this app id.
CONTROLLER_CONFIGS_APPID = "241100"


class Library:
    def __init__(self, steamapps):
        self.steamapps = steamapps
        self.common = os.path.join(steamapps, "common")
        self.app_ids = set()
        self.installdirs = set()  # lower-case folder names under common\
        for acf in glob.glob(os.path.join(glob.escape(steamapps), "appmanifest_*.acf")):
            self.app_ids.add(os.path.basename(acf)[len("appmanifest_"):-len(".acf")])
            try:
                with open(acf, encoding="utf-8", errors="replace") as fh:
                    m = INSTALLDIR.search(fh.read())
            except OSError:
                continue
            if m:
                self.installdirs.add(m.group(1).lower())

    def game_folders(self):
        """(path, installed) for each folder directly under common\\."""
        try:
            names = sorted(os.listdir(self.common))
        except OSError:
            return []
        out = []
        for n in names:
            p = os.path.join(self.common, n)
            if os.path.isdir(p):
                out.append((p, n.lower() in self.installdirs))
        return out
