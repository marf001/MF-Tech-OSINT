"""Licencias firmadas (Ed25519) atadas a la maquina.

El pool de licencias y la clave privada de firma viven SOLO en la maquina
maestra. A cada cliente se le entrega un unico archivo firmado (data/licencia.rel)
+ la clave publica de verificacion. Sin la clave privada (que nunca sale de la
maestra) es imposible forjar o descifrar licencias ajenas.
"""

import ctypes
import hashlib
import json
import os
import platform
import socket
import uuid

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    CRYPTO_OK = True
except Exception:
    ed25519 = None
    CRYPTO_OK = False

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_MASTER_DIR = os.path.join(_DIR, "master")
_PRIV = os.path.join(_MASTER_DIR, "master.key")
_ADMIN = os.path.join(_MASTER_DIR, "admin.bin")
_PUB = os.path.join(_DIR, "license_public.key")
_LIC_FILE = os.path.join(_DIR, "licencia.rel")


def _b64(x):
    return x.hex()


def is_master():
    return os.path.exists(_PRIV) and os.path.exists(_PUB) and os.path.exists(_ADMIN)


def ensure_master(admin_pass):
    """Primer arranque de la maquina maestra: genera par de claves y guarda el hash del admin."""
    if is_master():
        return False
    os.makedirs(_MASTER_DIR, exist_ok=True)
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    with open(_PRIV, "w", encoding="ascii") as f:
        f.write(_b64(private_key.private_bytes_raw()))
    with open(_PUB, "w", encoding="ascii") as f:
        f.write(_b64(public_key.public_bytes_raw()))
    with open(_ADMIN, "w", encoding="utf-8") as f:
        f.write(admin_pass)
    return True


def admin_password():
    if not os.path.exists(_ADMIN):
        return None
    with open(_ADMIN, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_private():
    with open(_PRIV, "r", encoding="ascii") as f:
        raw = bytes.fromhex(f.read().strip())
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def _load_public():
    with open(_PUB, "r", encoding="ascii") as f:
        raw = bytes.fromhex(f.read().strip())
    return ed25519.Ed25519PublicKey.from_public_bytes(raw)


def machine_code():
    """Huella estable de la PC (hostname + MAC + usuario + volumen del disco)."""
    vol = ""
    if platform.system() == "Windows":
        try:
            name = ctypes.create_unicode_buffer(261)
            sysf = ctypes.create_unicode_buffer(261)
            serial = ctypes.c_uint32()
            ok = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p("C:\\"), name, 261, ctypes.byref(serial), None, None, sysf, 261
            )
            if ok:
                vol = "%08X" % serial.value
        except Exception:
            vol = ""
    raw = "%s|%s|%s|%s|%s" % (
        socket.gethostname(),
        platform.node(),
        uuid.getnode(),
        os.path.expanduser("~"),
        vol,
    )
    h = hashlib.sha256(raw.encode("utf-8", "ignore")).hexdigest()[:24].upper()
    return "-".join(h[i:i + 4] for i in range(0, 24, 4))


def _canon(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign_payload(payload):
    if not is_master():
        raise RuntimeError("No hay clave privada de firma en esta maquina (es un build de cliente).")
    return _b64(_load_private().sign(_canon(payload)))


def verify(payload, sig_hex):
    try:
        if not CRYPTO_OK:
            return False
        pub = _load_public()
        pub.verify(bytes.fromhex(sig_hex), _canon(payload))
        return True
    except Exception:
        return False


def check_machine(payload):
    mc = payload.get("maquina")
    if mc:
        return mc.upper() == machine_code()
    return True


def check_expiry(payload):
    exp = payload.get("expira")
    if not exp:
        return True
    try:
        from datetime import date
        return date.today().isoformat() <= str(exp)
    except Exception:
        return True


def _now_iso():
    from datetime import datetime
    return datetime.now().replace(microsecond=0).isoformat()


def make_payload(usuario, version, expira=None, maquina=None):
    return {
        "id": uuid.uuid4().hex[:12],
        "usuario": usuario,
        "version": version,
        "emitida": _now_iso(),
        "expira": expira or None,
        "maquina": maquina.upper() if maquina else None,
    }


def license_write(payload):
    sig = sign_payload(payload)
    doc = {"algo": "ed25519", "payload": payload, "sig": sig}
    os.makedirs(_DIR, exist_ok=True)
    with open(_LIC_FILE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return doc


def license_read():
    if not os.path.exists(_LIC_FILE):
        return None
    try:
        with open(_LIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def license_validate(doc=None):
    """Devuelve (payload, error). payload valido si firma OK, maquina OK y no vencida."""
    if doc is None:
        doc = license_read()
    if not doc:
        return None, "No hay archivo de licencia (data/licencia.rel)."
    if not isinstance(doc, dict) or not doc.get("payload") or not doc.get("sig"):
        return None, "Archivo de licencia corrupto."
    if not verify(doc["payload"], doc["sig"]):
        return None, "Firma de licencia invalida (no fue emitida por el proveedor)."
    if not check_machine(doc["payload"]):
        return None, "Esta licencia fue emitida para otra PC."
    if not check_expiry(doc["payload"]):
        return None, "Licencia vencida."
    return doc["payload"], None


def public_key_hex():
    return _b64(_load_public().public_bytes_raw()) if os.path.exists(_PUB) else None