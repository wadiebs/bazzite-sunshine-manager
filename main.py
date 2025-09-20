import os, json, pathlib, shutil
from pathlib import Path
from common.utils import log, ensure_obj_with_apps, read_json, write_json
from importers.steam import import_steam
from importers.heroic import import_heroic

home = str(pathlib.Path.home())

# Sunshine config dir (flatpak or native)
sunshine_flatpak_ids = ["dev.lizardbyte.app.Sunshine","dev.lizardbyte.Sunshine"]
conf_dir = None
for fid in sunshine_flatpak_ids:
    fp_dir = f"{home}/.var/app/{fid}/config/sunshine"
    if os.path.isdir(fp_dir):
        conf_dir = fp_dir; break
if not conf_dir:
    conf_dir = f"{home}/.config/sunshine"

APPS_JSON = f"{conf_dir}/apps.json"
APPS_JSON_BAK = f"{APPS_JSON}.bak"

# Image roots
IMAGES_ROOT = "/var/home/steam/.config/sunshine/images"
IMAGES_DIR_STEAM   = os.path.join(IMAGES_ROOT, "steam")
IMAGES_DIR_HEROIC  = os.path.join(IMAGES_ROOT, "heroic")
IMAGES_DIR_SIDELOAD= os.path.join(IMAGES_ROOT, "sideload")
os.makedirs(conf_dir, exist_ok=True)
os.makedirs(IMAGES_DIR_STEAM, exist_ok=True)
os.makedirs(IMAGES_DIR_HEROIC, exist_ok=True)
os.makedirs(IMAGES_DIR_SIDELOAD, exist_ok=True)
log(f"Images root: {IMAGES_ROOT}")

# Backup apps.json once per run
if os.path.exists(APPS_JSON): shutil.copy2(APPS_JSON, APPS_JSON_BAK)
else: write_json(APPS_JSON, {"apps": []})

existing = ensure_obj_with_apps(read_json(APPS_JSON, {"apps": []}))

# Settings snapshot from environment
settings = dict(os.environ)

# Importers
steam_apps  = import_steam(home, conf_dir, IMAGES_DIR_STEAM, settings)
heroic_apps = import_heroic(home, conf_dir, IMAGES_DIR_HEROIC, settings)

merged = list(existing["apps"]) + steam_apps + heroic_apps

write_json(APPS_JSON, {"apps": merged})
log(f"Done. Total apps: {len(merged)}")
