def search_breach(email=None, username=None):
    results = {
        "query": email or username,
        "type": "email" if email else "username",
        "links": [],
        "error": None,
    }

    q = (email or username or "").strip()
    if not q:
        results["error"] = "Ingrese un email o usuario."
        return results

    results["links"] = [
        {
            "name": "Have I Been Pwned (brechas)",
            "url": f"https://haveibeenpwned.com/",
            "info": "Verificar si el email aparece en filtraciones (gratuito).",
        },
        {
            "name": "dehashed (consulta pública)",
            "url": f"https://www.dehashed.com/search?query={q}",
            "info": "Motor de búsqueda de filtraciones.",
        },
        {
            "name": "BreachDirectory",
            "url": f"https://breachdirectory.org/",
            "info": "Búsqueda de emails en brechas.",
        },
        {
            "name": "LeakCheck (vista web)",
            "url": f"https://leakcheck.io/",
            "info": "Búsqueda en base de datos de filtraciones.",
        },
        {
            "name": "EmailRep.io",
            "url": f"https://emailrep.io/query/{q}",
            "info": "Reputación y riesgo del email/dominio.",
        },
        {
            "name": "Disify (email descartable)",
            "url": f"https://www.disify.com/",
            "info": "Detectar emails temporales/descartables.",
        },
        {
            "name": "Pastebin (búsqueda)",
            "url": f"https://google.com/search?q=site:pastebin.com+%22{q}%22",
            "info": "Pastes públicos que mencionan el dato.",
        },
        {
            "name": "Búsqueda web de la filtración",
            "url": f"https://google.com/search?q=%22{q}%22+leak+OR+breach+OR+password",
            "info": "Menciones de la filtración.",
        },
    ]
    return results