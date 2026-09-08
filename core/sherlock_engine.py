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


def _parse_sherlock_output(output, username):
    results = []
    url_re = re.compile(r"(https?://[^\s]+)")
    for line in output.splitlines():
        line = line.strip()
        if ":" in line and ("+]" in line or ("http" in line and username.lower() in line.lower())):
            m = url_re.search(line)
            if not m:
                continue
            url = m.group(1)
            name_part = line.split(":", 1)[0]
            name = name_part.replace("[+]", "").strip()
            results.append({"name": name, "url": url, "info": "Perfil encontrado"})
    return results


def search_username(username):
    results = {"username": username, "found": [], "error": None}

    bin_path = _find_bin("sherlock")
    if not bin_path:
        try:
            import sherlock  # noqa: F401
            bin_path = "sherlock"
        except ImportError:
            bin_path = None

    if not bin_path:
        results["error"] = (
            "La herramienta 'sherlock' no está instalada. Ejecuta: pip install sherlock-project"
        )
        return results

    try:
        cmd = [bin_path, username, "--print-found", "--no-color", "--timeout", "12"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        output = proc.stdout or ""
        if not output:
            output = proc.stderr or ""
        parsed = _parse_sherlock_output(_strip_ansi(output), username)
        results["found"] = parsed
        if proc.returncode != 0 and not parsed:
            results["error"] = f"sherlock terminó con salida: {(proc.stderr or proc.stdout or '').strip()[:500]}"
    except subprocess.TimeoutExpired:
        results["error"] = "sherlock excedió el tiempo de espera (240s)."
    except Exception as e:
        results["error"] = str(e)

    return results