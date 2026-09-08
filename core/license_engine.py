import os
import json
import secrets
import datetime

from core import lic_sig

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LICENSE_FILE = os.path.join(DATA_DIR, "licenses.json")
CERT_FILE = os.path.join(DATA_DIR, "master", "certificados.json")
POOL_SIZE = 100


def _load():
    if not os.path.exists(LICENSE_FILE):
        return []
    try:
        with open(LICENSE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(items):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_key():
    raw = secrets.token_hex(8).upper()
    return "-".join([raw[i:i + 4] for i in range(0, 16, 4)])


def _new_record(ts):
    return {
        "id": secrets.token_hex(6),
        "clave": new_key(),
        "usuario": "",
        "email": "",
        "version": "",
        "estado": "disponible",
        "fecha_creacion": ts,
        "fecha_asignacion": None,
        "notas": "",
        "historicos": [],
    }


def init_pool(total=POOL_SIZE):
    if _load():
        return False
    ts = _now()
    _save([_new_record(ts) for _ in range(total)])
    return True


def get_stats():
    items = _load()

    def c(est):
        return sum(1 for r in items if r.get("estado") == est)

    return {
        "total": len(items),
        "disponibles": c("disponible"),
        "asignadas": c("asignada"),
        "revocadas": c("revocada"),
    }


def list_licenses():
    return list(reversed(_load()))


def create_license(version="", notas=""):
    ts = _now()
    rec = _new_record(ts)
    rec["version"] = (version or "").strip()
    rec["notas"] = (notas or "").strip()
    items = _load()
    items.append(rec)
    _save(items)
    return rec


def find_license(rid):
    for r in _load():
        if r.get("id") == rid:
            return r
    return None


def assign_license(rid, usuario, email, version):
    items = _load()
    for r in items:
        if r.get("id") == rid:
            if r.get("estado") != "disponible":
                return None, "La licencia no está disponible (estado: %s)." % r.get("estado")
            r["usuario"] = (usuario or "").strip()
            r["email"] = (email or "").strip()
            r["version"] = (version or r.get("version") or "").strip()
            r["estado"] = "asignada"
            r["fecha_asignacion"] = _now()
            r["historicos"].append({"evento": "asignada", "usuario": r["usuario"], "fecha": _now()})
            _save(items)
            return r, None
    return None, "Licencia no encontrada."


def revoke_license(rid):
    items = _load()
    for r in items:
        if r.get("id") == rid:
            r["estado"] = "revocada"
            r["historicos"].append({"evento": "revocada", "fecha": _now()})
            _save(items)
            return r, None
    return None, "Licencia no encontrada."


def _cert_log():
    if not os.path.exists(CERT_FILE):
        return []
    try:
        with open(CERT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def emit_client_license(rid, maquina=None, expira=None):
    """Firma el archivo data/licencia.rel a partir de una licencia ASIGNADA del pool.

    Este archivo es lo unico que recibe el cliente, junto con la clave publica.
    Devuelve (doc, error). El registro queda en data/master/certificados.json.
    """
    rec = find_license(rid)
    if not rec:
        return None, "Licencia no encontrada."
    if rec.get("estado") != "asignada":
        return None, "La licencia debe estar asignada para emitir su archivo firmado."
    try:
        payload = lic_sig.make_payload(
            rec.get("usuario") or "",
            rec.get("version") or "",
            expira=expira or None,
            maquina=maquina or None,
        )
        payload["pool_id"] = rec.get("id")
        payload["email"] = rec.get("email") or ""
        doc = lic_sig.license_write(payload)
    except Exception as e:
        return None, "No se pudo firmar la licencia: %s" % e

    certs = _cert_log()
    certs.append({
        "pool_id": rec.get("id"),
        "usuario": rec.get("usuario"),
        "lic_id": payload.get("id"),
        "maquina": payload.get("maquina"),
        "expira": payload.get("expira"),
        "emision": payload.get("emitida"),
        "archivo": "data/licencia.rel",
    })
    os.makedirs(os.path.dirname(CERT_FILE), exist_ok=True)
    with open(CERT_FILE, "w", encoding="utf-8") as f:
        json.dump(certs, f, ensure_ascii=False, indent=2)

    items = _load()
    for r in items:
        if r.get("id") == rid:
            r["historicos"].append({
                "evento": "certificado firmado emitido",
                "maquina": payload.get("maquina") or "libre",
                "expira": payload.get("expira") or "sin vencimiento",
                "fecha": _now(),
            })
            break
    _save(items)
    return doc, None


def check_key(clave):
    clave = (clave or "").strip().upper()
    for r in _load():
        if r.get("clave") == clave:
            if r.get("estado") == "asignada":
                return {"ok": True, "usuario": r.get("usuario"), "version": r.get("version")}
            return {"ok": False, "error": "Licencia %s." % r.get("estado")}
    return {"ok": False, "error": "Clave inválida."}


def check_login(usuario, clave):
    usuario = (usuario or "").strip().lower()
    clave = (clave or "").strip().upper()
    for r in _load():
        if r.get("estado") == "asignada" and clave == r.get("clave"):
            if (r.get("usuario") or "").strip().lower() == usuario:
                return {"ok": True, "usuario": r.get("usuario"), "version": r.get("version")}
    return {"ok": False, "error": "Usuario o clave de licencia inválidos."}