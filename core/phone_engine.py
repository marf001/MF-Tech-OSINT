import subprocess
import shutil
import os
import sys


def _find_bin(name):
    p = shutil.which(name)
    if p:
        return p
    project_tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
    for candidate in (
        os.path.join(project_tools, name + ".exe"),
        os.path.join(project_tools, name),
        os.path.join(sys.prefix, "Scripts", name + ".exe"),
        os.path.join(sys.prefix, "bin", name),
        os.path.join(os.path.dirname(sys.executable), "Scripts", name + ".exe"),
    ):
        if os.path.exists(candidate):
            return candidate
    return None

def _format_number(num_str, country_hint="AR"):
    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, timezone

        raw = num_str.strip().replace(" ", "").replace("-", "")
        parsed = None
        if raw.startswith("+"):
            parsed = phonenumbers.parse(raw, None)
        else:
            parsed = phonenumbers.parse(raw, country_hint)

        if not phonenumbers.is_valid_number(parsed):
            return {"valid": False, "error": "Número no válido para la región indicada."}

        return {
            "valid": True,
            "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
            "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
            "country_code": parsed.country_code,
            "national_number": parsed.national_number,
            "region": phonenumbers.region_code_for_number(parsed),
            "carrier": carrier.name_for_number(parsed, "es"),
            "geolocation": geocoder.description_for_number(parsed, "es"),
            "timezones": list(timezone.time_zones_for_number(parsed)),
        }
    except ImportError:
        return {"valid": False, "error": "phonenumbers no instalado."}
    except Exception as e:
        return {"valid": False, "error": str(e)}


def _lookup_urls(number):
    n = number.strip()
    return [
        {"name": "Truecaller (web)", "url": f"https://www.truecaller.com/search/all?search={n}", "info": "Buscar en Truecaller"},
        {"name": "FreeCarrierLookup", "url": f"https://freecarrierlookup.com/", "info": "Consulta manual de operador (gratuito)"},
        {"name": "Google Dork (tel)", "url": f"https://www.google.com/search?q=%22{n}%22", "info": "Buscar menciones del número"},
        {"name": "Bing Dork (tel)", "url": f"https://www.bing.com/search?q=%22{n}%22", "info": "Buscar menciones del número"},
        {"name": "DuckDuckGo (tel)", "url": f"https://duckduckgo.com/?q=%22{n}%22", "info": "Buscar menciones del número"},
        {"name": "WhatsApp (chat)", "url": f"https://wa.me/{n.replace('+', '')}", "info": "Enlace de WhatsApp"},
        {"name": "Telegram (búsqueda)", "url": f"https://t.me/{n.replace('+', '')}", "info": "Perfil de Telegram"},
        {"name": "SpyDialer", "url": f"https://www.spydialer.com/search/Reverse+Phone+Lookup/?phone_number={n}", "info": "Búsqueda telefónica inversa"},
    ]


def search_phone(number):
    results = {"number": number, "local_analysis": None, "phoneinfoga": None, "lookups": []}

    results["local_analysis"] = _format_number(number)

    phoneinfoga_bin = _find_bin("phoneinfoga")
    if phoneinfoga_bin:
        try:
            out = subprocess.run(
                [phoneinfoga_bin, "scan", "-n", number],
                capture_output=True, text=True, timeout=60
            )
            results["phoneinfoga"] = out.stdout or out.stderr
        except Exception as e:
            results["phoneinfoga"] = f"Error ejecutando phoneinfoga: {e}"
    else:
        results["phoneinfoga"] = (
            "phoneinfoga (binario Go) no está instalado. "
            "Descárgalo desde https://github.com/sundowndev/phoneinfoga/releases "
            "y colócalo en el PATH para análisis avanzados."
        )

    results["lookups"] = _lookup_urls(number)

    if results["local_analysis"] and not results["local_analysis"].get("valid"):
        results["error"] = results["local_analysis"].get("error")
    return results