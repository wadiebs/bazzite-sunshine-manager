#!/usr/bin/env python3
"""
Bazzite Sunshine Manager 

- Auto-installs requirements if missing (no virtualenv needed)
- Imports Steam/Heroic entries and merges them into Sunshine's apps.json
"""

import sys
import os
import shutil
import pathlib
import json
from pathlib import Path
from typing import Dict, Any


# -----------------------------
# Bootstrap: ensure requirements
# -----------------------------
def ensure_requirements():
    """
    Install Python requirements if they are not already available.
    Uses --user to avoid needing admin rights.
    """
    try:
        import PIL  # noqa: F401
        return
    except Exception:
        pass

    import subprocess
    req = pathlib.Path(__file__).with_name("requirements.txt")
    if not req.exists():
        print("No requirements.txt found; continuing without auto-install...", file=sys.stderr)
        return

    cmd = [sys.executable, "-m", "pip", "install", "--user", "-r", str(req)]
    print(f"Installing requirements: {' '.join(cmd)}", file=sys.stderr)
    try:
        subprocess.check_call(cmd)
        # Re-verify import after install (handles new PATH requirements for site.USER_BASE)
        import importlib
        import site
        # Ensure user site-packages is on sys.path in this process
        user_sp = site.getusersitepackages()
        if user_sp not in sys.path:
            sys.path.append(user_sp)
        importlib.invalidate_caches()
        import PIL  # noqa: F401
    except Exception as e:
        print(f"[ERROR] Failed to install requirements: {e}", file=sys.stderr)
        print("Tip: try running the install manually (with admin rights if needed):", file=sys.stderr)
        print(f"  {sys.executable} -m pip install -r {req}", file=sys.stderr)
        sys.exit(1)


ensure_requirements()

# Now safe to import local modules that may depend on installed packages
from common.utils import log, ensure_obj_with_apps, read_json, write_json  # noqa: E402
from importers.steam import import_steam  # noqa: E402
from importers.heroic import import_heroic  # noqa: E402


def detect_sunshine_config_dir(home: str) -> str:
    """Detect Sunshine config directory (handles Flatpak + native)."""
    flatpak_ids = ["dev.lizardbyte.app.Sunshine", "dev.lizardbyte.Sunshine"]
    for fid in flatpak_ids:
        fp_dir = os.path.join(home, ".var", "app", fid, "config", "sunshine")
        if os.path.isdir(fp_dir):
            return fp_dir
    # Fallback to native
    return os.path.join(home, ".config", "sunshine")


def main(argv: list[str]) -> int:
    home = str(Path.home())
    conf_dir = detect_sunshine_config_dir(home)
    os.makedirs(conf_dir, exist_ok=True)

    # Paths
    apps_json = os.path.join(conf_dir, "apps.json")
    apps_json_bak = f"{apps_json}.bak"

    # Put images alongside Sunshine config (portable/safe)
    images_root = os.path.join(conf_dir, "images")
    images_dir_steam = os.path.join(images_root, "steam")
    images_dir_heroic = os.path.join(images_root, "heroic")
    images_dir_sideload = os.path.join(images_root, "sideload")
    os.makedirs(images_dir_steam, exist_ok=True)
    os.makedirs(images_dir_heroic, exist_ok=True)
    os.makedirs(images_dir_sideload, exist_ok=True)
    log(f"Sunshine config: {conf_dir}")
    log(f"Images root:     {images_root}")

    # Backup apps.json (one per run)
    if os.path.exists(apps_json):
        try:
            shutil.copy2(apps_json, apps_json_bak)
            log(f"Backup created: {apps_json_bak}")
        except Exception as e:
            log(f"Warning: failed to backup apps.json: {e}")
    else:
        write_json(apps_json, {"apps": []})
        log("Initialized new apps.json")

    # Load existing
    existing = ensure_obj_with_apps(read_json(apps_json, {"apps": []}))

    # Settings snapshot from environment (importers look up flags from env)
    settings: Dict[str, Any] = dict(os.environ)

    # Run importers
    steam_apps = import_steam(home, conf_dir, images_dir_steam, settings)
    heroic_apps = import_heroic(home, conf_dir, images_dir_heroic, settings)

    merged = list(existing["apps"]) + steam_apps + heroic_apps
    write_json(apps_json, {"apps": merged})

    log(f"Imported: Steam={len(steam_apps)} Heroic={len(heroic_apps)} | Total apps now: {len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
