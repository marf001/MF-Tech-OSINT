import os
import json
import smtplib
import datetime
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "notificaciones.json")

DEFAULTS = {
    "enabled": False,
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "smtp_from": "MF Tech OSINT <no-reply@mfttech.local>",
    "to": "martinf@mftechar.com",
}


def _load_config():
    notify = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            notify = cfg.get("notify") or {}
        except Exception:
            notify = {}
    d = dict(DEFAULTS)
    d.update({k: v for k, v in notify.items() if v is not None})
    return d


def save_config(cfg):
    full = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                full = json.load(f)
        except Exception:
            full = {}
    full["notify"] = {
        "enabled": bool(cfg.get("enabled")),
        "smtp_host": (cfg.get("smtp_host") or "").strip(),
        "smtp_port": int(cfg.get("smtp_port") or 587),
        "smtp_user": (cfg.get("smtp_user") or "").strip(),
        "smtp_pass": cfg.get("smtp_pass") or "",
        "smtp_from": (cfg.get("smtp_from") or "").strip(),
        "to": (cfg.get("to") or "").strip() or DEFAULTS["to"],
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    return full["notify"]


def _log(kind, subject, destino, detalle, ok, error=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    items = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []
    items.append({
        "fecha": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": kind,
        "asunto": subject,
        "destino": destino,
        "detalle": detalle,
        "ok": ok,
        "error": error,
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def send_email(subject, body, kind="aviso", destinos=None):
    cfg = _load_config()
    destinos = destinos or [cfg.get("to")]
    destinos = [d for d in destinos if d and str(d).strip()]
    result = {"ok": False, "enviados": [], "destino": ", ".join(destinos), "error": None}

    enabled = cfg.get("enabled")
    if enabled and destinos:
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = cfg.get("smtp_from") or DEFAULTS["smtp_from"]
            msg["To"] = ", ".join(destinos)
            srv = smtplib.SMTP(cfg.get("smtp_host"), int(cfg.get("smtp_port") or 587), timeout=20)
            srv.ehlo()
            srv.starttls()
            srv.login(cfg.get("smtp_user"), cfg.get("smtp_pass"))
            srv.sendmail(cfg.get("smtp_from"), destinos, msg.as_string())
            srv.quit()
            result["ok"] = True
            result["enviados"] = destinos
        except Exception as e:
            result["error"] = "%s: %s" % (type(e).__name__, str(e))
    else:
        result["error"] = "SMTP deshabilitado o sin destino (solo se registró)."

    _log(kind, subject, result["destino"], body, result["ok"], result["error"])
    return result


def get_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return list(reversed(json.load(f)))
    except Exception:
        return []