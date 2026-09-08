import requests

DATOS_JUS_API = "https://datos.jus.gob.ar/api/3/action/package_search"
DATOS_GOB_API = "https://datos.gob.ar/api/3/action/package_search"
CONSULTA_PORTAL = "https://www2.jus.gov.ar/consultaddjj/Home/Busqueda"
DDJJ_PAGE = "https://www.argentina.gob.ar/anticorrupcion/declaraciones-juradas"


def search_ddjj(persona):
    results = {
        "persona": persona,
        "datasets": [],
        "portales": [
            {
                "name": "Consulta DDJJ - Portal Oficial (Oficina Anticorrupción)",
                "url": CONSULTA_PORTAL,
                "info": "Buscar y descargar declaraciones juradas de funcionarios públicos (2012 - actualidad).",
            },
            {
                "name": "DDJJ Anticorrupción - Argentina.gob.ar",
                "url": DDJJ_PAGE,
                "info": "Información y registros de declaraciones juradas patrimoniales.",
            },
            {
                "name": "Justicia Abierta - Datos (datos.jus.gob.ar)",
                "url": "https://datos.jus.gob.ar",
                "info": "Datos abiertos del Poder Judicial de la Nación, incluye DDJJ.",
            },
        ],
        "error": None,
    }

    api_and_names = [
        (DATOS_JUS_API, "Datos Jus"),
        (DATOS_GOB_API, "Datos Gob"),
    ]

    for api_url, name in api_and_names:
        try:
            resp = requests.get(api_url, params={"q": "declaraciones juradas"}, timeout=30)
            if resp.ok:
                payload = resp.json()
                for pkg in payload.get("result", {}).get("results", [])[:8]:
                    resources = []
                    for res in pkg.get("resources", [])[:10]:
                        resources.append({
                            "name": res.get("name") or res.get("format", "recurso"),
                            "format": res.get("format"),
                            "url": res.get("url"),
                        })
                    results["datasets"].append({
                        "origin": name,
                        "title": pkg.get("title"),
                        "description": (pkg.get("notes") or "")[:300],
                        "resources": resources,
                    })
        except Exception as e:
            results["error"] = f"Error consultando {name}: {e}"

    if persona:
        bq = "+".join(persona.split())
        results["busquedas"] = [
            {
                "name": "Buscar nombre en portal DDJJ",
                "url": CONSULTA_PORTAL,
                "info": f"Ingresar manualmente el nombre '{persona}'.",
            },
            {
                "name": "Google Dork (documentos)",
                "url": f"https://www.google.com/search?q=%22{persona}%22+declaraci%C3%B3n+jurada",
                "info": "Buscar menciones de declaraciones juradas del nombre.",
            },
            {
                "name": "Buscador Anticorrupción",
                "url": f"https://www.google.com/search?q=site:argentina.gob.ar+anticorrupcion+%22{persona}%22",
                "info": "Resultados dentro del portal institucional.",
            },
        ]
    return results