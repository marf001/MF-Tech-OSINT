import socket


def _sanitize(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return str(value)


def search_whois(domain):
    results = {"domain": domain, "whois": None, "raw_text": None, "dns": None, "error": None}

    try:
        import whois
        w = whois.whois(domain)
        fields = {}
        raw_text = None
        for key in dir(w):
            if key.startswith("_"):
                continue
            try:
                val = getattr(w, key)
                if callable(val):
                    continue
                if val is None:
                    continue
                if key == "text":
                    raw_text = str(val)
                    continue
                fields[key] = _sanitize(val)
            except Exception:
                continue
        results["whois"] = fields
        results["raw_text"] = raw_text
    except ImportError as e:
        results["error"] = f"python-whois no está instalado: {e}"
    except Exception as e:
        results["error"] = str(e)

    try:
        ip = socket.gethostbyname(domain)
        results["dns"] = {"ip": ip}
    except Exception:
        results["dns"] = {"ip": "No se pudo resolver"}

    return results