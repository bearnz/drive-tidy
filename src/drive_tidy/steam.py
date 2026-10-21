"""Steam facts: a library's appmanifest_*.acf files, and the Steam client's
own records (which libraries it knows, when each app was last played)."""
import glob
import os

from . import vdf

# Steam Controller Configs keeps per-game controller layouts under this app id.
CONTROLLER_CONFIGS_APPID = "241100"


class Library:
    def __init__(self, steamapps):
        self.steamapps = steamapps
        self.common = os.path.join(steamapps, "common")
        self.app_ids = set()
        self.installdirs = {}  # lower-case folder name under common\ -> (appid, name)
        for acf in glob.glob(os.path.join(glob.escape(steamapps), "appmanifest_*.acf")):
            appid = os.path.basename(acf)[len("appmanifest_"):-len(".acf")]
            self.app_ids.add(appid)
            try:
                state = vdf.load(acf).get("appstate", {})
            except OSError:
                continue
            if state.get("installdir"):
                self.installdirs[state["installdir"].lower()] = (appid, state.get("name", ""))

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

    def app_of(self, folder):
        """(appid, name) for an installed game folder, else (None, None)."""
        return self.installdirs.get(os.path.basename(folder).lower(), (None, None))


class Client:
    """What the Steam client records. Empty when Steam isn't found."""

    def __init__(self, root=None):
        self.root = find_steam() if root is None else root
        self.libraries = set()   # normcase'd steamapps paths Steam lists
        self.last_played = {}    # appid -> unix time, latest across local accounts
        if not self.root or not os.path.isdir(self.root):
            return
        try:
            folders = vdf.load(os.path.join(self.root, "steamapps", "libraryfolders.vdf"))
        except OSError:
            folders = {}
        for entry in (vdf.get(folders, "libraryfolders") or {}).values():
            if isinstance(entry, dict) and entry.get("path"):
                self.libraries.add(os.path.normcase(os.path.join(entry["path"], "steamapps")))
        for cfg in glob.glob(os.path.join(glob.escape(self.root), "userdata", "*", "config", "localconfig.vdf")):
            try:
                apps = vdf.get(vdf.load(cfg), "userlocalconfigstore", "software", "valve", "steam", "apps")
            except OSError:
                continue
            for appid, info in (apps or {}).items():
                ts = info.get("lastplayed") if isinstance(info, dict) else None
                if ts and ts.isdigit() and int(ts) > self.last_played.get(appid, 0):
                    self.last_played[appid] = int(ts)

    @property
    def found(self):
        return bool(self.libraries or self.last_played)

    def is_registered(self, steamapps):
        return os.path.normcase(steamapps) in self.libraries


def find_steam():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return os.path.normpath(winreg.QueryValueEx(k, "SteamPath")[0])
    except OSError:
        return None
