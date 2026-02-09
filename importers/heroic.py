# importers/heroic.py
# Heroic (Epic/GOG/Sideload) importer
# Ports the logic from the monolithic sunshine-import.py into the split architecture.

import os
import re
import json
import glob
from pathlib import Path
from typing import List, Dict, Any

from common.utils import log, read_json, slugify, yn
from common.images import download_temp, stretch_png_600x900, sgdb_search_by_name


def import_heroic(home: str, conf_dir: str, images_dir: str, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Discover Epic/GOG (via Heroic) and Sideload apps and return Sunshine app entries.

    Args:
        home: user home directory
        conf_dir: detected Sunshine config directory (unused here, kept for symmetry)
        images_dir: directory to store Heroic covers (PNG; 600x900)
        settings: environment snapshot for toggles (IMPORT_HEROIC, INCLUDE_SOURCES, BLACKLIST_NAME_REGEX, ...)

    Returns:
        List of Sunshine app dicts.
    """
    IMPORT_HEROIC = settings.get("IMPORT_HEROIC", True)
    if isinstance(IMPORT_HEROIC, str):
        IMPORT_HEROIC = IMPORT_HEROIC == "1"
    if not IMPORT_HEROIC:
        log("Heroic import disabled.")
        return []

    include_sources = str(settings.get("INCLUDE_SOURCES", "epic,gog")).lower().split(",")
    blacklist_name_regex = str(settings.get("BLACKLIST_NAME_REGEX", ""))

    # Ensure target image dirs exist. Also keep a sibling "sideload" dir like the monolith.
    os.makedirs(images_dir, exist_ok=True)
    images_dir_sideload = os.path.join(os.path.dirname(images_dir), "sideload")
    os.makedirs(images_dir_sideload, exist_ok=True)

    # Heroic config root detection (prefer Steam user path used by Bazzite)
    preferred = "/var/home/steam/.var/app/com.heroicgameslauncher.hgl/config/heroic"
    fallbacks = [
        preferred,
        f"{home}/.var/app/com.heroicgameslauncher.hgl/config/heroic",
        f"{home}/.config/heroic",
    ]
    hero_conf_root = next((p for p in fallbacks if os.path.isdir(p)), "")
    if not hero_conf_root:
        log("Heroic config root not found; skipping Heroic import.")
        return []

    # Launch prefix and mode
    if "/.var/app/" in hero_conf_root:
        heroic_kind = "flatpak"
        heroic_prefix = "flatpak run com.heroicgameslauncher.hgl "
        add_silent_param = True   # matches the monolith behavior
    else:
        heroic_kind = "native"
        heroic_prefix = "xdg-open "
        add_silent_param = False

    log(f"Heroic: {heroic_kind} | conf: {hero_conf_root}")

    legendary_installed = os.path.join(hero_conf_root, "legendaryConfig", "legendary", "installed.json")
    gog_installed       = os.path.join(hero_conf_root, "gog_store", "installed.json")
    games_cfg_dir       = os.path.join(hero_conf_root, "GamesConfig")
    sideload_library    = os.path.join(hero_conf_root, "sideload_apps", "library.json")

    # ---------------------- helpers for Heroic/GOG ----------------------
    def first_non_empty(*vals) -> str:
        for v in vals:
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    def load_json_if(path):
        try:
            if os.path.isfile(path):
                return read_json(path, {})
        except Exception as e:
            log(f"Warn: failed loading JSON {path}: {e}")
        return {}

    def humanize_slug(s: str) -> str:
        s = re.sub(r"[_\\-]+", " ", s or "")
        s = re.sub(r"\\s+", " ", s).strip()
        return s.title()

    def scan_gamescfg_for_title(gid: str, install_path: str) -> str:
        if not os.path.isdir(games_cfg_dir):
            return ""
        try:
            for cfg_path in glob.glob(os.path.join(games_cfg_dir, "*.json")):
                cfg = load_json_if(cfg_path)
                if not isinstance(cfg, dict):
                    continue
                appname = str(cfg.get("appName") or cfg.get("app_name") or cfg.get("id") or "")
                ipath   = str(cfg.get("installPath") or cfg.get("install_path") or "")
                # match by id or install path
                if (gid and appname == str(gid)) or (install_path and ipath and os.path.normpath(ipath) == os.path.normpath(install_path)):
                    t = first_non_empty(
                        cfg.get("title"),
                        cfg.get("appTitle"),
                        cfg.get("gameTitle"),
                        (cfg.get("productInfo") or {}).get("title") if isinstance(cfg.get("productInfo"), dict) else ""
                    )
                    if t:
                        return t
        except Exception as e:
            log(f"Warn: scan GamesConfig failed: {e}")
        return ""

    def resolve_gog_title(it: dict, gid: str, install_path: str, hero_conf_root: str) -> str:
        # 1) direct fields from installed.json entry
        t = first_non_empty(it.get("title"), it.get("gameTitle"), it.get("appTitle"))
        if t:
            return t

        # nested game blob
        g = it.get("game") if isinstance(it.get("game"), dict) else {}
        t = first_non_empty(g.get("title"), g.get("name"))
        if t:
            return t

        # 2) GamesConfig/<gid>.json exact
        cfg_exact = os.path.join(games_cfg_dir, f"{gid}.json")
        cfg = load_json_if(cfg_exact)
        if cfg:
            t = first_non_empty(
                cfg.get("title"), cfg.get("appTitle"), cfg.get("gameTitle"),
                (cfg.get("productInfo") or {}).get("title") if isinstance(cfg.get("productInfo"), dict) else ""
            )
            if t:
                return t

        # 3) Scan GamesConfig/*.json by id or installPath
        t = scan_gamescfg_for_title(gid, install_path)
        if t:
            return t

        # 4) gog_store/library.json (match by id or installPath)
        lib_json = load_json_if(os.path.join(hero_conf_root, "gog_store", "library.json"))
        if lib_json:
            candidates = []
            if isinstance(lib_json, dict):
                for key in ("library", "games", "items"):
                    if isinstance(lib_json.get(key), list):
                        candidates.extend(lib_json[key])
                if not candidates and all(isinstance(v, dict) for v in lib_json.values()):
                    candidates.extend(lib_json.values())
            elif isinstance(lib_json, list):
                candidates = lib_json

            def id_of(o):
                return first_non_empty(str(o.get("appName") or ""), str(o.get("app_name") or ""), str(o.get("id") or ""))

            for o in candidates:
                if not isinstance(o, dict):
                    continue
                ipath = str(o.get("installPath") or o.get("install_path") or "")
                if id_of(o) == str(gid) or (install_path and ipath and os.path.normpath(ipath) == os.path.normpath(install_path)):
                    t = first_non_empty(
                        o.get("title"),
                        (o.get("game") or {}).get("title") if isinstance(o.get("game"), dict) else "",
                        o.get("gameTitle"),
                        o.get("appTitle")
                    )
                    if t:
                        return t
                    break

        # 5) per-game details caches
        for sub in ("gamedetails", "details"):
            details_path = os.path.join(hero_conf_root, "gog_store", sub, f"{gid}.json")
            det = load_json_if(details_path)
            t = first_non_empty(
                det.get("title"),
                (det.get("game") or {}).get("title") if isinstance(det.get("game"), dict) else ""
            )
            if t:
                return t

        # 6) Install folder name ? title
        if install_path:
            folder = os.path.basename(os.path.normpath(install_path))
            if folder and folder.strip("/."):
                return humanize_slug(folder)

        # 7) slug/id ? human
        slug = first_non_empty(it.get("slug"), it.get("appName"), it.get("app_name"))
        if slug and not str(slug).isdigit():
            return humanize_slug(str(slug))

        # Fallback
        return f"GOG {gid}"

    # ====== Heroic cached image resolver (for Epic/GOG) ======
    _JSON_URL_RX = re.compile(r"https?://[^\s\"'<>]+", re.I)

    # Keys that can contain the *exact* game id
    _ID_KEYS = {
        "appName","app_name","appname","app-id","appId","app_id",
        "productId","productID","product_id","id","gameId","game_id",
        "titleId","title_id","catalogItemId","catalog_item_id","slug","productSlug"
    }

    # Epic image "type" preferences seen in catalog / assets
    _EPIC_TYPE_PREFER = (
        "DieselGameBoxTall","VaultBoxArtTall","OfferImageTall","DieselGameBox",
        "ProductPromoArt","KeyArt","ComingSoonBoxArt","StoreTall"
    )

    # Prefer “cover-ish”, de-prioritize non-cover art across both platforms
    _URL_PREFER = ("cover","boxart","poster","portrait","front","artwork","keyart","hero","tall","vertical")
    _URL_DEPRIO = ("screenshot","logo","icon","background","wallpaper","banner","landscape","wide","placeholder","default")

    # Keys frequently carrying cover-ish URLs in GOG/Epic JSONs
    _COVER_KEYS = {
        "art_cover","cover","coverUrl","coverURL","gridCover","verticalCover","portrait","vertical",
        "imageUrl","imageURL","heroImage","hero_image","boxArt","poster","tile","thumb","grid","banner","logo_square"
    }

    def _walk_json(node, path=()):
        yield path, node
        if isinstance(node, dict):
            for k, v in node.items():
                yield from _walk_json(v, path+(k,))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from _walk_json(v, path+(i,))

    def _node_has_exact_gid(node, gid: str) -> bool:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _ID_KEYS and str(v) == gid:
                    return True
        return False

    def _node_mentions_gid(node, gid: str) -> bool:
        for _, v in _walk_json(node):
            if isinstance(v, str) and gid in v:
                return True
            if not isinstance(v, (dict, list)) and str(v) == gid:
                return True
        return False

    def _extract_urls_from_node(node) -> list[tuple[str,int,int,int,int]]:
        """
        Return list of tuples: (url, epic_type_rank, cover_key_hit, has_img_ext, prefer_score, -deprio_score)
        so we can sort deterministically.
        """
        out: list[tuple[str,int,int,int,int]] = []

        def push(u: str, epic_type_rank: int = 0, cover_key_hit: int = 0):
            us = u.lower()
            has_ext = int(any(us.split("?",1)[0].endswith(ext) for ext in (".png",".jpg",".jpeg",".webp",".avif")))
            prefer = sum(1 for s in _URL_PREFER if s in us)
            deprio = sum(1 for s in _URL_DEPRIO if s in us)
            # discard obvious placeholders early
            if "placeholder" in us or "default" in us:
                return
            out.append((u, epic_type_rank, cover_key_hit, has_ext, prefer, -deprio))

        # 1) Dedicated cover-ish fields (dictionary keys)
        if isinstance(node, dict):
            for k in list(node.keys()):
                if k in _COVER_KEYS:
                    val = node.get(k)
                    if isinstance(val, str) and _JSON_URL_RX.match(val):
                        push(val, cover_key_hit=1)

        # 2) Epic-style image arrays: [{"type":"DieselGameBoxTall","url": "..."}]
        def grab_from_img_obj(obj):
            if not isinstance(obj, dict):
                return
            url = obj.get("url") or obj.get("src") or obj.get("image") or obj.get("ImageUrl") or obj.get("imageUrl")
            if isinstance(url, str) and _JSON_URL_RX.match(url):
                t = str(obj.get("type",""))
                epic_rank = 2 if t in _EPIC_TYPE_PREFER else (1 if ("Tall" in t or "Vertical" in t or "BoxArt" in t) else 0)
                push(url, epic_type_rank=epic_rank)

        if isinstance(node, dict):
            for key in ("images","image","media","assets","imageList","imagesList","keyImages"):
                val = node.get(key)
                if isinstance(val, list):
                    for item in val:
                        grab_from_img_obj(item)
                elif isinstance(val, dict):
                    for item in val.values():
                        grab_from_img_obj(item)

        # 3) Any URL-looking string anywhere in the node (last resort)
        for _, v in _walk_json(node):
            if isinstance(v, str):
                for m in _JSON_URL_RX.findall(v):
                    push(m)

        return out

    def heroic_find_image_url_for_gid(hero_conf_root: str, gid: str) -> str:
        """
        Strict mode: only harvest from objects where an ID key equals gid.
        Fallback: objects that merely *mention* gid.
        Return best-scoring URL or "".
        """
        root = Path(hero_conf_root)
        if not root.is_dir():
            return ""

        # Stage 0: collect JSONs that contain gid (fast prefilter)
        json_files: list[Path] = []
        for jf in root.rglob("*.json"):
            try:
                txt = jf.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if gid in txt:
                json_files.append(jf)

        if not json_files:
            return ""

        exact_hits = []
        fuzzy_hits = []

        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for _, node in _walk_json(data):
                if isinstance(node, (dict, list)):
                    if _node_has_exact_gid(node, gid):
                        exact_hits.append(node)
                    elif _node_mentions_gid(node, gid):
                        fuzzy_hits.append(node)

        ranked: list[tuple[str,int,int,int,int]] = []

        # Prefer URLs from exact-id nodes
        for node in exact_hits or []:
            ranked.extend(_extract_urls_from_node(node))

        # If no exact matches yielded any URL, fall back to fuzzy nodes
        if not ranked:
            for node in fuzzy_hits or []:
                ranked.extend(_extract_urls_from_node(node))

        if not ranked:
            return ""

        # Sort: epic_type_rank, cover_key_hit, has_img_ext, prefer_score, -deprio_score, then shorter URLs
        ranked.sort(key=lambda t: (t[1], t[2], t[3], t[4], t[5], -len(t[0])), reverse=True)

        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for u, *_ in ranked:
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        return ordered[0] if ordered else ""

    def heroic_cover_png_from_json(hero_conf_root: str, gid: str, images_dir: str) -> str:
        """
        JSON-only discovery to get a cover URL (strict gid-anchored), download, stretch 600x900 PNG.
        """
        url = heroic_find_image_url_for_gid(hero_conf_root, gid)
        if not url:
            return ""
        tmp = download_temp(url)
        if not tmp:
            return ""
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", f"heroic_{gid}").strip("_") or f"heroic_{gid}"
        dst = os.path.join(images_dir, f"{safe}.png")
        ok = stretch_png_600x900(tmp, dst)
        try:
            os.remove(tmp)
        except Exception:
            pass
        return dst if ok and os.path.isfile(dst) else ""

    heroic_apps: List[Dict[str, Any]] = []

    def add_heroic(title, gid, install_path, src, image_path=""):
        # Name blacklist by regex
        if blacklist_name_regex:
            for pat in blacklist_name_regex.split("|"):
                if pat and re.search(pat, str(title or ""), re.I):
                    log(f"Skip {src} {title} ({gid}) [blacklist]")
                    return

        # JSON-only discovery of a cover URL (Epic/GOG)
        if (not image_path) and src in ("Epic", "GOG"):
            try:
                png = heroic_cover_png_from_json(hero_conf_root, str(gid), images_dir)
                if png:
                    image_path = png
            except Exception as e:
                log(f"Heroic JSON cover lookup failed for {gid}: {e}")
        
        # Fallback to SteamGridDB search by name if no image found
        if not image_path:
            try:
                api_key = str(settings.get("SGDB_API_KEY", ""))
                enable = bool(int(settings.get("SGDB_ENABLE", 1)))
                timeout = int(settings.get("SGDB_TIMEOUT", 12))
                if api_key and enable:
                    # Use game title for search, clean filename for storage
                    search_name = title or gid
                    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", f"heroic_{gid}").strip("_") or f"heroic_{gid}"
                    sgdb_png = sgdb_search_by_name(search_name, images_dir, safe_filename, api_key, enable, timeout)
                    if sgdb_png:
                        image_path = sgdb_png
                        log(f"Downloaded SteamGridDB cover for {search_name}")
            except Exception as e:
                log(f"SteamGridDB lookup failed for {title or gid}: {e}")

        runner = "sideload" if src == "Sideload" else src.lower()
        base = f"heroic://launch?appName={gid}&runner={runner}"
        if add_silent_param:
            base += "&silent=true"

        cmd = f"{heroic_prefix}{base}"
        heroic_apps.append({
            "name": f"{title or gid} ({src})",
            "output": "",
            "cmd": cmd,
            "working-dir": install_path or home,
            "image-path": image_path or "",
            "detached": False,
            "elevated": False,
            "exit-on-close": True
        })
        log(f"Found {src}  {yn(title or gid)}")

    # --------------------- EPIC (Legendary) ---------------------
    if "epic" in include_sources:
        if os.path.isfile(legendary_installed):
            try:
                raw = read_json(legendary_installed, {})
                for gid, val in (raw or {}).items():
                    install_path = (val or {}).get("install_path")
                    if not install_path:
                        continue
                    title = (val or {}).get("title") or (val or {}).get("app_title") or gid
                    add_heroic(title, gid, install_path, "Epic")
            except Exception as e:
                log(f"Failed to parse Epic installed.json: {e}")
        else:
            log(f"No Legendary installed.json at {legendary_installed}")

    # --------------------- GOG ---------------------
    if "gog" in include_sources:
        if os.path.isfile(gog_installed):
            data = read_json(gog_installed, {})
            items = data.get("installed", data if isinstance(data, list) else [])
            for it in items:
                if not isinstance(it, dict):
                    continue
                gid = it.get("appName") or it.get("app_name") or it.get("id")
                if not gid:
                    continue
                install_path = it.get("installPath") or it.get("install_path") or ""
                title = resolve_gog_title(it, str(gid), install_path, hero_conf_root)
                add_heroic(title, str(gid), install_path, "GOG")
        else:
            log(f"No GOG installed.json at {gog_installed}")

    # --------------------- SIDELOAD ---------------------
    if os.path.isfile(sideload_library):
        try:
            raw = read_json(sideload_library, {})
            if isinstance(raw, list):
                items = raw
            elif isinstance(raw, dict):
                for key in ("apps", "library", "entries", "games"):
                    if key in raw and isinstance(raw[key], list):
                        items = raw[key]
                        break
                else:
                    items = list(raw.values())
            else:
                items = []

            count = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                sid = it.get("appName") or it.get("app_name") or it.get("slug") or it.get("id")
                title = it.get("title") or it.get("name") or it.get("displayName") or sid
                exe   = it.get("executable") or it.get("exe") or it.get("bin") or ""
                workd = it.get("workingDir") or it.get("workDir") or (os.path.dirname(exe) if exe else home)
                cover_url = it.get("art_cover") or it.get("imageUrl") or it.get("imagePath") or ""
                out_cover = ""
                if cover_url:
                    tmp_src = download_temp(cover_url)
                    if tmp_src:
                        base = slugify(sid or title or "sideload")
                        dst = os.path.join(images_dir_sideload, f"{base}.png")
                        if stretch_png_600x900(tmp_src, dst):
                            out_cover = dst
                        else:
                            try:
                                # fallback direct copy
                                import shutil as _sh
                                _sh.copy2(tmp_src, dst)
                                out_cover = dst
                            except Exception:
                                out_cover = ""
                        try:
                            os.remove(tmp_src)
                        except Exception:
                            pass
                add_heroic(title or sid, sid, workd, "Sideload", image_path=out_cover)
                count += 1
            log(f"Sideload parsed: {count} entries")
        except Exception as e:
            log(f"Failed to parse sideload library: {e}")
    else:
        log(f"No sideload library.json at {sideload_library}")

    return heroic_apps
