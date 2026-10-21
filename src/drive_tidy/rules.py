"""What the scanner never touches, and what counts as a save game."""
import os
import re

# Directory names that are skipped wherever they appear (case-insensitive).
SKIP_DIRS = {"system volume information", "$recycle.bin", "windowsapps", "wpsystem"}

# A path component that looks like a save folder, or a file extension that
# looks like a save. Steam's userdata holds cloud saves and controller configs.
SAVE_DIR = re.compile(
    r"^(saves?|saved|savegames?|saved ?games|savedata|save ?files?|userdata|memcards?|remote)$",
    re.I,
)
SAVE_EXT = {
    ".sav", ".save", ".sv", ".fos", ".ess", ".gun", ".rvdata2",  # PC games
    ".ps2", ".mcd", ".mcr", ".srm", ".state",                    # emulator cards/states
}


def is_skipped_dir(name):
    return name.lower() in SKIP_DIRS


def path_parts(path):
    return [p for p in re.split(r"[\\/]", path) if p]


def is_save_path(path):
    """True if any folder in the path looks like a save folder, or the file
    itself has a save extension."""
    parts = path_parts(path)
    if any(SAVE_DIR.match(p) for p in parts[:-1]):
        return True
    last = parts[-1] if parts else ""
    return bool(SAVE_DIR.match(last)) or os.path.splitext(last)[1].lower() in SAVE_EXT


def is_protected_path(path):
    """True if the path is a drive root or sits under a skipped directory."""
    parts = path_parts(path)
    if len(parts) <= 1:
        return True
    return any(is_skipped_dir(p) for p in parts)
