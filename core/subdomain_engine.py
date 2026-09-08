import requests
import re
import contextlib
import io


def _from_crtsh(domain):
    subs = set()
    try:
        resp = requests.get(
            f"https://crt.sh/?q=%25.{domain}&output=json",
            headers={"User-Agent": "MF-Tech-Osint/1.0"},
            timeout=30,
        )
        if resp.ok:
            try:
                data = resp.json()
                for entry in data:
                    name = entry.get("name_value", "")
                    for raw in name.replace("\r", " ").split():
                        n = raw.strip().rstrip(".").lstrip("*.")
                        if not n:
                            continue
                        if n.lower().endswith("." + domain.lower()):
                            subs.add(n.lower())
            except Exception:
                pass
    except Exception:
        pass
    return subs


def _from_sublist3r(domain):
    subs = set()
    try:
        import sublist3r
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            found = sublist3r.main(
                domain,
                threads=20,
                savefile=None,
                ports=None,
                silent=True,
                verbose=False,
                enable_bruteforce=False,
                engines=None,
            )
        if found:
            subs.update(found)
    except Exception as e:
        return None, str(e)
    return subs, None


def search_subdomains(domain):
    results = {"domain": domain, "subdomains": [], "error": None, "source": {}}

    domain = domain.strip().lower()
    if not re.match(r"^[a-z0-9\-\.]+\.[a-z]{2,}$", domain):
        results["error"] = "Dominio no válido. Ej: ejemplo.com"
        return results

    crt = _from_crtsh(domain)
    results["source"]["crt.sh"] = sorted(crt)

    sublist3r_subs, sublist_err = _from_sublist3r(domain)
    if sublist3r_subs is not None:
        results["source"]["sublist3r"] = sorted(sublist3r_subs)
    else:
        results["source"]["sublist3r"] = []
        if sublist_err:
            results["warning_sublist3r"] = sublist_err

    all_subs = crt | (sublist3r_subs or set())
    results["subdomains"] = sorted(all_subs)

    if not all_subs and not results.get("warning_sublist3r"):
        results["warning"] = "No se encontraron subdominios. Los buscadores pueden bloquear consultas frecuentes."
    return results