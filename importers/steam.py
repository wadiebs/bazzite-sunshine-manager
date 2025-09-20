import os, re, glob, json, pathlib
from typing import List, Dict, Any
from common.utils import log, yn, read_json
from common.images import steam_cdn_to_png, steam_sgdb_to_png

def import_steam(home: str, conf_dir: str, images_dir: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    IMPORT_STEAM = settings.get("IMPORT_STEAM", True)
    if not IMPORT_STEAM:
        log("Steam import disabled."); return []

    steam_root = None; steam_mode = None
    flatpak_root = f"{home}/.var/app/com.valvesoftware.Steam/.local/share/Steam"
    native_roots = [f"{home}/.local/share/Steam", f"{home}/.steam/steam"]
    if os.path.isdir(flatpak_root): steam_root = flatpak_root; steam_mode = "flatpak"
    else:
        for r in native_roots:
            if os.path.isdir(r): steam_root = r; steam_mode = "native"; break

    if not steam_root or not os.path.isdir(os.path.join(steam_root, "steamapps")):
        log("Steam not found; skipping Steam import."); return []

    log(f"Steam: {steam_mode} at {steam_root}")

    # library dirs
    lib_dirs = []
    lib_vdf = os.path.join(steam_root,"steamapps","libraryfolders.vdf")
    if os.path.isfile(lib_vdf):
        for line in open(lib_vdf,"r",encoding="utf-8",errors="ignore"):
            m = re.search(r'"path"\s*"([^"]+)"', line)
            if m:
                p = os.path.join(m.group(1),"steamapps")
                if os.path.isdir(p): lib_dirs.append(p)
    lib_dirs.append(os.path.join(steam_root,"steamapps"))
    seen=set(); lib_dirs=[d for d in lib_dirs if not (d in seen or seen.add(d))]

    # blacklist
    bl_ids=set(); bl_patterns=[]
    if settings.get("USE_DEFAULT_BLACKLIST", True):
        bl_patterns += [
            r"Steamworks Common Redistributables", r"Proton",
            r"SteamVR|OpenVR|Valve Index", r"Soundtrack",
            r"Dedicated Server|Server", r"SDK|Editor|Mod Tools|Tools?",
            r"Demo", r"Benchmark|Test",
            r"Runtime", r"Workshop", r"Big Picture", r"Source",
            r"Linux Runtime", r"Redistributables", r"Desktop Mode",
        ]
    if str(settings.get("BLACKLIST_IDS","")).strip():
        for tok in re.split(r"[,\s]+", str(settings.get("BLACKLIST_IDS")).strip()):
            if tok.isdigit(): bl_ids.add(int(tok))
    bl_path = settings.get("BLACKLIST_FILE") or os.path.join(conf_dir,"steam-import.blacklist")
    if os.path.isfile(bl_path):
        for line in open(bl_path,"r",encoding="utf-8",errors="ignore"):
            line=line.split("#",1)[0].strip()
            if not line: continue
            if line.isdigit(): bl_ids.add(int(line))
            else: bl_patterns.append(line)
    if str(settings.get("BLACKLIST_NAME_REGEX","")).strip():
        bl_patterns += [p for p in str(settings.get("BLACKLIST_NAME_REGEX")).split("|") if p]

    def blacklisted(appid, name):
        if appid in bl_ids: return True
        for pat in bl_patterns:
            try:
                if re.search(pat, name, re.I): return True
            except re.error:
                if pat.lower() in name.lower(): return True
        return False

    apps=[]
    app_count=0
    for sd in lib_dirs:
        for path in glob.glob(os.path.join(sd,"appmanifest_*.acf")):
            try: txt=open(path,"r",encoding="utf-8",errors="ignore").read()
            except Exception: continue
            m_id=re.search(r'"appid"\s*"(\d+)"',txt)
            m_name=re.search(r'"name"\s*"([^"]+)"',txt)
            if not (m_id and m_name): continue
            appid=int(m_id.group(1)); name=m_name.group(1); app_count+=1
            if blacklisted(appid,name):
                log(f"Skipping blacklisted [{appid}] {yn(name)}"); continue

            if steam_mode=="flatpak":
                cmd=f'flatpak-spawn --host flatpak run com.valvesoftware.Steam steam -applaunch {appid}'
                workdir=f"{home}/.var/app/com.valvesoftware.Steam/.local/share/Steam"
            else:
                cmd=f'steam -applaunch {appid}'
                workdir=steam_root

            image_path = steam_cdn_to_png(appid, images_dir, timeout=int(settings.get("SGDB_TIMEOUT",12)))                              or steam_sgdb_to_png(appid, images_dir, api_key=str(settings.get("SGDB_API_KEY","")),
                                              enable=bool(int(settings.get("SGDB_ENABLE",1))),
                                              timeout=int(settings.get("SGDB_TIMEOUT",12)))

            apps.append({
                "name": name, "output": "", "cmd": cmd, "working-dir": workdir,
                "image-path": image_path or "", "detached": False, "elevated": False, "exit-on-close": True
            })
            log(f"Found Steam  [{appid}] {yn(name)}")
    log(f"Steam installed scanned: {app_count}")
    return apps
