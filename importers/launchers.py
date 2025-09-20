# importers/launchers.py
from __future__ import annotations
import os
from typing import List, Dict, Any
from common.utils import log, have_cmd, yn


def _steam_cmd(home: str) -> tuple[str, str]:
    """
    Return (cmd, working_dir) for Steam if found, else ("","").
    Detect Flatpak or native.
    """
    flatpak_root = f"{home}/.var/app/com.valvesoftware.Steam/.local/share/Steam"
    if os.path.isdir(flatpak_root):
        return ("flatpak run com.valvesoftware.Steam", flatpak_root)
    if have_cmd("steam"):
        # best-effort working dir: user Steam root if present
        for r in (f"{home}/.local/share/Steam", f"{home}/.steam/steam"):
            if os.path.isdir(r):
                return ("steam", r)
        return ("steam", home)
    return ("", "")


def _heroic_cmd(home: str) -> tuple[str, str]:
    """
    Return (cmd, working_dir) for Heroic if found, else ("","").
    Detect Flatpak or native.
    """
    # Known Heroic config roots
    candidates = [
        "/var/home/steam/.var/app/com.heroicgameslauncher.hgl/config/heroic",
        f"{home}/.var/app/com.heroicgameslauncher.hgl/config/heroic",
        f"{home}/.config/heroic",
    ]
    is_flatpak = any(os.path.isdir(p) and "/.var/app/" in p for p in candidates)
    if is_flatpak:
        return ("flatpak run com.heroicgameslauncher.hgl", home)
    # native heroic binary?
    if have_cmd("heroic"):
        return ("heroic", home)
    # sometimes the launcher registers a URL handler; still add if explicitly requested later
    return ("", "")


def import_launchers(home: str, conf_dir: str, images_dir: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create generic launchers (Desktop, Steam, Heroic, Reboot).

    Env toggles:
      - IMPORT_LAUNCHERS=1 (default)
    """
    enabled = str(settings.get("IMPORT_LAUNCHERS", "1")).strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        log("Launchers importer disabled.")
        return []

    apps: List[Dict[str, Any]] = []

    # 1) Desktop launcher (as requested: only name + image-path provided by user)
    #    We keep a minimal Sunshine schema (empty cmd) for consistency.
    desktop_app = {
        "name": "Desktop",
        "output": "",
        "cmd": "",
        "working-dir": home,
        "image-path": "steam.png",  # per user instruction
        "detached": False,
        "elevated": False,
        "exit-on-close": True,
    }
    apps.append(desktop_app)
    log(f"Added {yn('Desktop')} launcher")

    # 2) Steam launcher (only if installed)
    steam_cmd, steam_wd = _steam_cmd(home)
    if steam_cmd:
        apps.append({
            "name": "Steam",
            "output": "",
            "cmd": steam_cmd,
            "working-dir": steam_wd or home,
            "image-path": "steam.png",
            "detached": False,
            "elevated": False,
            "exit-on-close": True,
        })
        log(f"Added {yn('Steam')} launcher")
    else:
        log("Steam not detected; skipping Steam launcher")

    # 3) Heroic launcher (only if installed)
    heroic_cmd, heroic_wd = _heroic_cmd(home)
    if heroic_cmd:
        apps.append({
            "name": "Heroic",
            "output": "",
            "cmd": heroic_cmd,
            "working-dir": heroic_wd or home,
            "image-path": "heroic.png",
            "detached": False,
            "elevated": False,
            "exit-on-close": True,
        })
        log(f"Added {yn('Heroic')} launcher")
    else:
        log("Heroic not detected; skipping Heroic launcher")

    # 4) Reboot launcher (exact block provided)
    apps.append({
        "auto-detach": True,
        "cmd": [],
        "detached": ["systemctl reboot"],
        "exclude-global-prep-cmd": False,
        "exit-timeout": 5,
        "image-path": "/var/home/steam/.config/sunshine/images/Reboot.png",
        "name": "Zz Reboot System",
        "output": "",
        "wait-all": True
    })
    log(f"Added {yn('Zz Reboot System')} launcher")

    return apps
