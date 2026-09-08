import os
import re
import json
import threading
import secrets
import subprocess
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
GPS_FILE = os.path.join(DATA_DIR, "gps.json")
TUNNEL_LOG = os.path.join(DATA_DIR, "cloudflared.log")
TUNNEL_INFO = os.path.join(DATA_DIR, "tunel.json")

_cloudflared_bin = None
_tunnel_proc = None
_tunnel_url = None
_tunnel_lock = threading.Lock()
_fallback_base = None


def _persist_tunnel_url(url):
    try:
        with open(TUNNEL_INFO, "w", encoding="utf-8") as f:
            json.dump({
                "url": url,
                "detectado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_persisted_url():
    try:
        with open(TUNNEL_INFO, "r", encoding="utf-8") as f:
            return (json.load(f) or {}).get("url")
    except Exception:
        return None


def set_fallback_base(url):
    global _fallback_base
    _fallback_base = url


def _find_cloudflared():
    global _cloudflared_bin
    if _cloudflared_bin:
        return _cloudflared_bin
    tools = os.path.join(BASE_DIR, "tools")
    for candidate in (
        os.path.join(tools, "cloudflared.exe"),
        os.path.join(tools, "cloudflared"),
    ):
        if os.path.exists(candidate):
            _cloudflared_bin = candidate
            break
    return _cloudflared_bin


def start_tunnel(local_url):
    global _tunnel_proc
    bin_path = _find_cloudflared()
    if not bin_path:
        return False
    if _tunnel_proc and _tunnel_proc.poll() is None:
        return True
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        os.remove(TUNNEL_INFO)
    except OSError:
        pass
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    with open(TUNNEL_LOG, "w", encoding="utf-8") as logf:
        _tunnel_proc = subprocess.Popen(
            [bin_path, "tunnel", "--url", local_url, "--no-autoupdate"],
            stdout=logf,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
    threading.Thread(target=_tunnel_watchdog, args=(local_url,), daemon=True).start()
    return True


def _tunnel_watchdog(local_url):
    global _tunnel_proc, _tunnel_url
    while True:
        try:
            with _tunnel_lock:
                alive = _tunnel_proc is not None and _tunnel_proc.poll() is None
                if not alive:
                    if _tunnel_proc:
                        try:
                            _tunnel_proc.kill()
                        except Exception:
                            pass
                    bin_path = _find_cloudflared()
                    if bin_path:
                        kwargs = {}
                        if os.name == "nt":
                            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                        with open(TUNNEL_LOG, "w", encoding="utf-8") as logf:
                            _tunnel_proc = subprocess.Popen(
                                [bin_path, "tunnel", "--url", local_url, "--no-autoupdate"],
                                stdout=logf,
                                stderr=subprocess.STDOUT,
                                **kwargs,
                            )
                url = _poll_tunnel_url()
                if url:
                    _persist_tunnel_url(url)
                    _tunnel_url = url
        except Exception:
            pass
        threading.Event().wait(25)


def _poll_tunnel_url():
    global _tunnel_url
    try:
        with open(TUNNEL_LOG, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", content)
        if m:
            _tunnel_url = m.group(1)
    except Exception:
        pass
    return _tunnel_url


def get_tunnel_url():
    if _tunnel_url:
        return _tunnel_url
    if _tunnel_proc and _tunnel_proc.poll() is None:
        cur = _poll_tunnel_url()
        if cur:
            return cur
    return _load_persisted_url()


def get_public_base():
    tunnel = get_tunnel_url()
    if tunnel:
        return tunnel
    if _fallback_base:
        return _fallback_base
    return "http://127.0.0.1:8090"


def _load():
    if not os.path.exists(GPS_FILE):
        return []
    try:
        with open(GPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(GPS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def list_links():
    items = _load()
    for r in items:
        if r.get("lat") is not None and r.get("lng") is not None:
            r["maps"] = f"https://www.google.com/maps?q={r['lat']},{r['lng']}"
        else:
            r["maps"] = None
    return list(reversed(items))


def create_link(nota, template_id, texto=""):
    items = _load()
    token = secrets.token_urlsafe(8)
    rec = {
        "id": token,
        "nota": nota,
        "numero": nota,
        "template_id": template_id,
        "texto": texto,
        "path": f"/gps/{token}",
        "estado": "pendiente",
        "creado": _now(),
        "recibido": None,
        "lat": None,
        "lng": None,
        "accuracy": None,
    }
    items.append(rec)
    _save(items)
    base = get_public_base()
    full = f"{base}{rec['path']}"
    rec["url"] = full
    return rec


def report_location(token, lat, lng, accuracy):
    items = _load()
    for r in items:
        if r.get("id") == token:
            r["estado"] = "recibida"
            r["lat"] = lat
            r["lng"] = lng
            r["accuracy"] = accuracy
            r["recibido"] = _now()
            r["maps"] = f"https://www.google.com/maps?q={lat},{lng}"
            _save(items)
            return True
    return False


def delete_link(token):
    items = _load()
    kept = [r for r in items if r.get("id") != token]
    if len(kept) == len(items):
        return False
    _save(kept)
    return True