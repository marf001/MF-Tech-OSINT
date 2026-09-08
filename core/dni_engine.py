def search_dni(dni):
    results = {
        "dni": dni,
        "valid": False,
        "error": None,
        "links": [],
    }

    dni = str(dni).strip()
    if not dni.isdigit() or len(dni) < 6:
        results["error"] = "DNI no válido. Debe ser numérico (6-8 dígitos)."
        return results

    results["valid"] = True
    results["links"] = [
        {
            "name": "Padrón Electoral - CABA",
            "url": f"https://www.padron.gob.ar/",
            "info": "Consultar padrón electoral oficial (DNI completo).",
        },
        {
            "name": "ANSES - Consulta CUIL",
            "url": "https://www.anses.gob.ar/consultas",
            "info": "Obtener CUIL a partir del DNI.",
        },
        {
            "name": "Telexplorer (guía inversa)",
            "url": f"https://www.telexplorer.com.ar/",
            "info": "Guía telefónica inversa de Argentina.",
        },
        {
            "name": "Renaper (requiere trámite)",
            "url": "https://www.argentina.gob.ar/identidad",
            "info": "Trámite oficial para verificar identidad.",
        },
        {
            "name": "Búsqueda web del DNI",
            "url": f"https://www.google.com/search?q=%22DNI+{dni}%22+OR+%22{dni}%22",
            "info": "Menciones públicas del número de documento.",
        },
        {
            "name": "Boletín Oficial AR",
            "url": f"https://www.boletinoficial.gob.ar/buscar?texto=DNI%20{dni}",
            "info": "Publicaciones que referencian el DNI.",
        },
    ]

    if len(dni) == 8:
        cuit = "20" + dni
        results["links"].insert(1, {
            "name": "CUIT estimado (varón)",
            "url": "",
            "info": f"Prefijo para varón: 20-{dni}-X (verificable con módulo CUIT).",
        })

    return results