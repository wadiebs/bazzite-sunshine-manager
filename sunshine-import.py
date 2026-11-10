#!/usr/bin/env python3
"""
Bazzite Sunshine Manager

Author: wadiebs
Date: January 2026
Version: 2.0

Description:
Automated importer and manager for Sunshine streaming app configurations.
This tool creates and updates Sunshine applications through its localhost API.

Features:
- Automatic detection of Sunshine configuration directory (Flatpak + native)
- Imports applications from multiple sources (Steam, Heroic Launcher, custom launchers)
- Blacklist support for filtering unwanted applications
- Modular architecture for easy extension of import sources
- Support for poster/thumbnail artwork organization
"""

import sys
import os
import argparse
import getpass
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# Safe to import local modules now
from common.utils import log  # noqa: E402
from common.sunshine_api import SunshineAPI, SunshineAPIError
from importers.steam import import_steam  # noqa: E402
from importers.heroic import import_heroic  # noqa: E402
from importers.launchers import import_launchers

FLATPAK_IDS = ["dev.lizardbyte.app.Sunshine", "dev.lizardbyte.Sunshine"]
NATIVE_SERVICES = ["sunshine-kms.service", "sunshine.service"]


def _run_ok(cmd: List[str]) -> Optional[subprocess.CompletedProcess]:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None


def _native_config_dir(home: str) -> str:
    base = os.getenv("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "sunshine")


def _flatpak_config_dir(home: str, app_id: str) -> str:
    return os.path.join(home, ".var", "app", app_id, "config", "sunshine")


def _running_flatpak_id() -> Optional[str]:
    res = _run_ok(["flatpak", "ps", "--columns=application"])
    if res is None or res.returncode != 0:
        return None
    running = {line.strip() for line in res.stdout.splitlines()}
    return next((fid for fid in FLATPAK_IDS if fid in running), None)


def _native_running() -> bool:
    for unit in NATIVE_SERVICES:
        res = _run_ok(["systemctl", "--user", "is-active", "--quiet", unit])
        if res is not None and res.returncode == 0:
            return True
    res = _run_ok(["pgrep", "-x", "sunshine"])
    return res is not None and res.returncode == 0


def detect_sunshine_config_dir(home: str) -> str:
    """Pick the config dir of the Sunshine instance in use (override > running instance > newest apps.json)."""
    override = os.getenv("SUNSHINE_CONF_DIR")
    if override:
        log(f"Config dir from SUNSHINE_CONF_DIR: {override}")
        return override

    fid = _running_flatpak_id()
    if fid:
        log(f"Detected running Flatpak Sunshine ({fid})")
        return _flatpak_config_dir(home, fid)

    native = _native_config_dir(home)
    if _native_running():
        log("Detected running native Sunshine")
        return native

    # Sunshine not running: prefer the config that was used most recently.
    candidates = [native] + [_flatpak_config_dir(home, f) for f in FLATPAK_IDS]
    existing = [d for d in candidates if os.path.isfile(os.path.join(d, "apps.json"))]
    if existing:
        chosen = max(existing, key=lambda d: os.path.getmtime(os.path.join(d, "apps.json")))
        log(f"Sunshine not running; using most recently modified config: {chosen}")
        return chosen
    return native


def getenv_flag(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Import applications using the localhost Sunshine API.")
    parser.add_argument("--sunshine-user", default=os.getenv("SUNSHINE_USERNAME"))
    parser.add_argument("--sunshine-port", type=int, default=os.getenv("SUNSHINE_PORT", "47990"))
    parser.add_argument("--verify-tls", action="store_true", default=getenv_flag("SUNSHINE_VERIFY_TLS", False))
    args = parser.parse_args(argv[1:])
    username = args.sunshine_user
    password = os.getenv("SUNSHINE_PASSWORD")
    if sys.stdin.isatty():
        try:
            username = username or input("Sunshine username: ")
            password = password or getpass.getpass("Sunshine password: ")
        except (EOFError, KeyboardInterrupt):
            log("Authentication cancelled.")
            return 1
    try:
        api = SunshineAPI(username, password, args.sunshine_port, args.verify_tls)
        api.list_apps()
    except SunshineAPIError as exc:
        log(str(exc))
        return 1

    home = str(Path.home())
    conf_dir = detect_sunshine_config_dir(home)
    os.makedirs(conf_dir, exist_ok=True)

    # Paths
    images_root = os.path.join(conf_dir, "images")
    images_dir_steam = os.path.join(images_root, "steam")
    images_dir_heroic = os.path.join(images_root, "heroic")
    images_dir_sideload = os.path.join(images_root, "sideload")
    for d in (images_dir_steam, images_dir_heroic, images_dir_sideload):
        os.makedirs(d, exist_ok=True)

    log(f"Sunshine config: {conf_dir}")
    log(f"Images root:     {images_root}")

    # Read toggles from environment
    IMPORT_STEAM = getenv_flag("IMPORT_STEAM", True)
    IMPORT_HEROIC = getenv_flag("IMPORT_HEROIC", True)

    enabled_importers = []
    if IMPORT_STEAM:
        enabled_importers.append("steam")
    if IMPORT_HEROIC:
        enabled_importers.append("heroic")

    settings: Dict[str, Any] = dict(os.environ)

    # Collect apps from enabled importers
    apps = []
    if IMPORT_STEAM:
        apps += import_steam(home, conf_dir, images_dir_steam, settings)
    else:
        log("Steam importer disabled.")
    if IMPORT_HEROIC:
        apps += import_heroic(home, conf_dir, images_dir_heroic, settings)
    else:
        log("Heroic importer disabled.")

    apps += import_launchers(home, conf_dir, os.path.join(conf_dir, "images", "launchers"), settings)

    saved = 0
    try:
        for app in apps:
            action = api.upsert_app(app)
            saved += 1
            log(f"{action}: {app['name']}")
    except SunshineAPIError as exc:
        log(f"Import stopped after {saved}/{len(apps)} saves: {exc}")
        return 1
    log(f"Saved {saved} apps through the Sunshine API.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
