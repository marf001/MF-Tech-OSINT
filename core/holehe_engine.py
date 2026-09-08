import subprocess
import shutil
import re
import os
import sys

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text):
    return ANSI_RE.sub("", text)


def _find_bin(name):
    p = shutil.which(name)
    if p:
        return p
    for candidate in (
        os.path.join(sys.prefix, "Scripts", name + ".exe"),
        os.path.join(sys.prefix, "bin", name),
        os.path.join(os.path.dirname(sys.executable), "Scripts", name + ".exe"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _parse_holehe_output(output):
    sites = []
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[([+x\-])\]\s*(.+)$", line)
        if not m:
            continue
        marker = m.group(1)
        site = m.group(2).strip()
        if not site:
            continue
        if marker == "+":
            exists, rate = True, False
        elif marker == "x":
            exists, rate = False, True
        else:
            exists, rate = False, False
        sites.append({
            "name": site,
            "exists": exists,
            "rate_limit": rate,
            "message": "Email utilizado" if exists else ("Rate limit" if rate else "Email no utilizado"),
        })
    return sites


def search_email(email):
    results = {"email": email, "found": [], "error": None}

    bin_path = _find_bin("holehe")
    if not bin_path:
        results["error"] = (
            "La herramienta 'holehe' no está instalada. Ejecuta: pip install -r requirements.txt"
        )
        return results

    try:
        proc = subprocess.run(
            [bin_path, "--no-color", email],
            capture_output=True,
            text=True,
            timeout=180,
        )
        output = proc.stdout or ""
        if not output:
            output = proc.stderr or ""
        parsed = _parse_holehe_output(_strip_ansi(output))
        if parsed:
            results["checked"] = parsed
            results["found"] = [p for p in parsed if p["exists"]]
            results["rate_limited"] = [p for p in parsed if p["rate_limit"]]
        if not parsed and proc.returncode != 0:
            results["error"] = f"holehe no devolvió resultados. Salida: {(proc.stderr or proc.stdout or '').strip()[:500]}"
    except subprocess.TimeoutExpired:
        results["error"] = "holehe excedió el tiempo de espera (180s). Puede haber rate-limiting."
    except Exception as e:
        results["error"] = str(e)

    return results