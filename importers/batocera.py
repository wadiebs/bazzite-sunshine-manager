# importers/batocera.py
# Batocera ROM importer
# Reads gamelist.xml files from Batocera ROM directories and produces Sunshine app entries.

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional

from common.utils import log, slugify, yn
from common.images import sgdb_search_by_name

MIN_IMAGE_SIZE_BYTES = 1000  # minimum bytes for a valid cached image

# Default ROM directory search order (most specific to most generic)
_DEFAULT_ROMS_PATHS = [
    "/userdata/roms",                                          # native Batocera OS
    "/var/home/steam/batocera/share/roms",                    # Bazzite shared-drive layout
    "/var/home/steam/.local/share/batocera/roms",             # Bazzite user-local layout
    "/run/media/batocera/userdata/roms",                      # USB/removable drive
]


def import_batocera(home: str, conf_dir: str, images_dir: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Discover Batocera ROMs via gamelist.xml files and return Sunshine app entries.

    Args:
        home:       user home directory
        conf_dir:   detected Sunshine config directory (kept for symmetry)
        images_dir: directory to store cover images (PNG 600x900)
        settings:   environment snapshot for toggles

    Returns:
        List of Sunshine app dicts.

    Relevant settings keys
    ----------------------
    IMPORT_BATOCERA      0/1   – enable/disable this importer (default: 1)
    BATOCERA_ROMS_DIR    path  – override the ROM root directory
    BATOCERA_RUN_CMD     cmd   – command used to launch a ROM; receives the system name and ROM
                                 path as positional args: <cmd> <system> "<rom>".
                                 Default is "batocera-run" (available natively on Batocera OS and
                                 common Batocera-on-Bazzite container setups).  Adjust this to
                                 match your environment, e.g. "ssh batocera batocera-run" or a
                                 custom wrapper script.
    BATOCERA_SYSTEMS     list  – comma-separated system names to include (empty = all)
    BLACKLIST_NAME_REGEX regex – skip games whose name matches this pattern
    SGDB_ENABLE          0/1   – use SteamGridDB for missing cover art (default: 1)
    SGDB_API_KEY         str   – SteamGridDB API key
    SGDB_TIMEOUT         int   – HTTP timeout in seconds (default: 12)
    """
    import_flag = settings.get("IMPORT_BATOCERA", "1")
    if isinstance(import_flag, str):
        import_flag = import_flag.strip().lower() not in ("0", "false", "no", "off")
    if not import_flag:
        log("Batocera importer disabled.")
        return []

    # Resolve ROMs directory
    roms_dir = str(settings.get("BATOCERA_ROMS_DIR", "")).strip()
    if not roms_dir:
        for candidate in _DEFAULT_ROMS_PATHS:
            if os.path.isdir(candidate):
                roms_dir = candidate
                break
    if not roms_dir or not os.path.isdir(roms_dir):
        log("Batocera ROMs directory not found; skipping Batocera import.")
        return []

    log(f"Batocera: ROMs dir: {roms_dir}")

    # Build launch command (positional: system, rom)
    run_cmd = str(settings.get("BATOCERA_RUN_CMD", "batocera-run")).strip() or "batocera-run"

    # Optional system filter
    systems_filter_raw = str(settings.get("BATOCERA_SYSTEMS", "")).strip()
    systems_filter = {s.strip().lower() for s in systems_filter_raw.split(",") if s.strip()} if systems_filter_raw else set()

    # Name blacklist (shared with other importers)
    blacklist_name_regex = str(settings.get("BLACKLIST_NAME_REGEX", "")).strip()

    os.makedirs(images_dir, exist_ok=True)

    apps: List[Dict[str, Any]] = []
    total_roms = 0

    for system_dir in sorted(Path(roms_dir).iterdir()):
        if not system_dir.is_dir():
            continue
        system = system_dir.name

        # Apply system filter if set
        if systems_filter and system.lower() not in systems_filter:
            continue

        gamelist_path = system_dir / "gamelist.xml"
        if not gamelist_path.is_file():
            continue

        try:
            games = _parse_gamelist(gamelist_path, system_dir)
        except Exception as e:
            log(f"Batocera: failed to parse {gamelist_path}: {e}")
            continue

        for game in games:
            name = game["name"]
            total_roms += 1

            # Name blacklist check
            if blacklist_name_regex:
                try:
                    if re.search(blacklist_name_regex, name, re.I):
                        log(f"Skipping blacklisted (regex) [{system}] {name}")
                        continue
                except re.error:
                    log(f"Warning: invalid BLACKLIST_NAME_REGEX pattern '{blacklist_name_regex}'; falling back to substring match")
                    if blacklist_name_regex.lower() in name.lower():
                        log(f"Skipping blacklisted [{system}] {name}")
                        continue

            rom_path = game["path"]
            source_image = game.get("image", "")

            # Resolve local cover art
            local_image = _resolve_cover(
                name=name,
                system=system,
                source_image=source_image,
                images_dir=images_dir,
                settings=settings,
            )

            cmd = f'{run_cmd} {system} "{rom_path}"'

            apps.append({
                "name": name,
                "cmd": cmd,
                "working-dir": home,
                "image-path": local_image,
                "output": "",
                "detached": False,
                "elevated": False,
                "exit-on-close": True,
            })
            log(f"Found Batocera [{system}] {yn(name)}")

    log(f"Batocera ROMs scanned: {total_roms}")
    return apps


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_gamelist(gamelist_path: Path, system_dir: Path) -> List[Dict[str, Any]]:
    """Parse a Batocera/EmulationStation gamelist.xml into a list of game dicts."""
    games: List[Dict[str, Any]] = []
    tree = ET.parse(str(gamelist_path))
    root = tree.getroot()

    for game_el in root.findall("game"):
        # ROM path (required)
        path_el = game_el.find("path")
        if path_el is None or not path_el.text:
            continue
        rom_path = _resolve_es_path(path_el.text.strip(), system_dir)

        # Display name
        name_el = game_el.find("name")
        if name_el is not None and name_el.text and name_el.text.strip():
            name = name_el.text.strip()
        else:
            name = Path(rom_path).stem

        # Skip games marked hidden
        hidden_el = game_el.find("hidden")
        if hidden_el is not None and hidden_el.text and hidden_el.text.strip().lower() == "true":
            continue

        # Cover image (prefer <image>, fall back to <thumbnail>)
        image = ""
        for tag in ("image", "thumbnail"):
            img_el = game_el.find(tag)
            if img_el is not None and img_el.text and img_el.text.strip():
                candidate = _resolve_es_path(img_el.text.strip(), system_dir)
                if os.path.isfile(candidate):
                    image = candidate
                    break

        games.append({"name": name, "path": rom_path, "image": image})

    return games


def _resolve_es_path(raw: str, base_dir: Path) -> str:
    """Resolve an EmulationStation relative or absolute path to an absolute path."""
    if raw.startswith("./"):
        return str(base_dir / raw[2:])
    if raw.startswith("/"):
        return raw
    return str(base_dir / raw)


def _resolve_cover(
    name: str,
    system: str,
    source_image: str,
    images_dir: str,
    settings: Dict[str, Any],
) -> str:
    """
    Return a local 600x900 PNG path for the cover art.

    Priority:
      1. gamelist.xml image (resize to 600x900 if needed)
      2. SteamGridDB search by name (if SGDB_ENABLE and SGDB_API_KEY are set)
    """
    slug = slugify(f"{system}_{name}")
    dst = os.path.join(images_dir, f"{slug}.png")

    # 1) Already cached
    if os.path.isfile(dst) and os.path.getsize(dst) > MIN_IMAGE_SIZE_BYTES:
        return dst

    # 2) Resize/copy from gamelist.xml image
    if source_image and os.path.isfile(source_image):
        try:
            from common.images import stretch_png_600x900
            result = stretch_png_600x900(source_image, dst)
            if result and os.path.isfile(result):
                return result
        except Exception as e:
            log(f"Batocera: image resize failed for {name}: {e}")

    # 3) SteamGridDB fallback
    sgdb_enable = str(settings.get("SGDB_ENABLE", "1")).strip().lower() not in ("0", "false", "no", "off")
    sgdb_key = str(settings.get("SGDB_API_KEY", "")).strip()
    sgdb_timeout = int(settings.get("SGDB_TIMEOUT", 12))
    if sgdb_enable and sgdb_key:
        try:
            result = sgdb_search_by_name(name, dst, api_key=sgdb_key, timeout=sgdb_timeout)
            if result and os.path.isfile(result):
                return result
        except Exception as e:
            log(f"Batocera: SGDB lookup failed for {name}: {e}")

    return ""
