import os, re, urllib.request, urllib.parse, tempfile, shutil, subprocess
from PIL import Image  # pillow is required
from .utils import have_cmd

def download_temp(url_or_path: str, suffix: str = "") -> str:
    """
    Returns a path to a temporary file containing the referenced content.
    Supports:
      - http(s)://...
      - file:///absolute/path
      - /absolute/path
      - ./relative (will be rejected; keep to absolute for local)
    """
    try:
        if not url_or_path:
            return ""

        # Handle file:// scheme explicitly
        if url_or_path.startswith("file://"):
            parsed = urllib.parse.urlparse(url_or_path)
            local_path = urllib.parse.unquote(parsed.path)
            if os.path.isabs(local_path) and os.path.exists(local_path):
                fd, tmp = tempfile.mkstemp(prefix="sg_", suffix=suffix or os.path.splitext(local_path)[1] or ".img")
                os.close(fd); shutil.copy2(local_path, tmp); return tmp
            return ""

        # HTTP(S)
        if re.match(r"^https?://", url_or_path, re.I):
            ext = os.path.splitext(urllib.parse.urlparse(url_or_path).path)[1] or ".img"
            fd, tmp = tempfile.mkstemp(prefix="sg_", suffix=suffix or ext)
            os.close(fd)
            req = urllib.request.Request(url_or_path, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                with open(tmp, "wb") as f:
                    f.write(resp.read())
            return tmp

        # Direct filesystem path (prefer absolute; skip relative to avoid surprises)
        if os.path.isabs(url_or_path) and os.path.exists(url_or_path):
            fd, tmp = tempfile.mkstemp(prefix="sg_", suffix=suffix or os.path.splitext(url_or_path)[1] or ".img")
            os.close(fd); shutil.copy2(url_or_path, tmp); return tmp

    except Exception:
        return ""
    return ""


def save_bytes_to(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)

def stretch_png_600x900(src_path: str, dst_png: str) -> bool:
    try:
        im = Image.open(src_path)
        if im.mode not in ("RGB", "RGBA"): im = im.convert("RGB")
        im = im.resize((600, 900), resample=Image.BICUBIC)
        im.save(dst_png, format="PNG")
        return True
    except Exception:
        pass
    # ImageMagick
    if have_cmd("convert"):
        try:
            subprocess.run(["convert", src_path, "-resize", "600x900!", dst_png], check=True)
            return True
        except Exception:
            pass
    # ffmpeg
    if have_cmd("ffmpeg"):
        try:
            subprocess.run(["ffmpeg","-y","-loglevel","error","-i",src_path,"-vf","scale=600:900",dst_png], check=True)
            return True
        except Exception:
            pass
    # fallback copy
    try:
        shutil.copy2(src_path, dst_png)
        return True
    except Exception:
        return False

def steam_cdn_to_png(appid: int, images_dir: str, timeout: int = 12) -> str:
    url = f"https://steamcdn-a.akamaihd.net/steam/apps/{appid}/library_600x900.jpg"
    out = os.path.join(images_dir, f"{appid}.png")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if not data or len(data) < 1024: return ""
        fd, tmp = tempfile.mkstemp(prefix="cdn_", suffix=".jpg"); os.close(fd)
        save_bytes_to(tmp, data)
        ok = stretch_png_600x900(tmp, out)
        os.remove(tmp)
        return out if ok else ""
    except Exception:
        return ""

def steam_sgdb_to_png(appid: int, images_dir: str, api_key: str, enable: bool, timeout: int = 12) -> str:
    if not (api_key and enable): return ""
    try:
        def best(url):
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                import json
                return json.load(resp).get("data", [])
        items = best(f"https://www.steamgriddb.com/api/v2/grids/steam/{appid}") or best(f"https://www.steamgriddb.com/api/v2/heroes/steam/{appid}")
        if not items: return ""
        items.sort(key=lambda x: x.get("score", 0), reverse=True)
        url = items[0].get("url", "")
        if not url: return ""
        tmp = download_temp(url)
        if not tmp: return ""
        out = os.path.join(images_dir, f"{appid}.png")
        ok = stretch_png_600x900(tmp, out)
        try: os.remove(tmp)
        except Exception: pass
        return out if ok else ""
    except Exception:
        return ""
