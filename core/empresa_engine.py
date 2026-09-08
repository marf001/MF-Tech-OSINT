def search_empresa(razon_social=None, cuit=None):
    results = {
        "query": razon_social or cuit,
        "links": [],
        "error": None,
    }

    q = (razon_social or cuit or "").strip()
    if not q:
        results["error"] = "Ingrese razón social o número de CUIT."
        return results

    encoded = q.replace(" ", "+")

    links = [
        {
            "name": "Boletín Oficial de la República Argentina",
            "url": f"https://www.boletinoficial.gob.ar/buscar?texto={encoded}",
            "info": "Constitución de sociedades, edictos, concursos, quiebras.",
        },
        {
            "name": "IGJ - Inspección General de Justicia (CABA)",
            "url": "https://www.argentina.gob.ar/justicia/igj",
            "info": "Registro de entidades civiles y comerciales (CABA).",
        },
        {
            "name": "AFIP - Ficha de CUIT (Situación Fiscal)",
            "url": "https://www.afip.gob.ar/genericos/situacion-fiscal/",
            "info": "Estado tributario del contribuyente.",
        },
        {
            "name": "Central de Deudores BCRA",
            "url": f"https://www.bcra.gob.ar/BCRAyVos/Situacion_Crediticia.asp?cuit={q}",
            "info": "Historial crediticio, cheques rechazados y deudas.",
        },
        {
            "name": "Compr.AR - Contrataciones Públicas",
            "url": f"https://comprar.gob.ar/",
            "info": "Contratos y proveedores del Estado.",
        },
        {
            "name": "Búsqueda web de la empresa",
            "url": f"https://www.google.com/search?q=%22{q}%22",
            "info": "Presencia pública y menciones.",
        },
        {
            "name": "LinkedIn - Empresas",
            "url": f"https://www.linkedin.com/search/results/companies/?keywords={encoded}",
            "info": "Perfil corporativo.",
        },
        {
            "name": "Boletín de comercio - Jurisdicciones",
            "url": "https://www.argentina.gob.ar/justicia/registros",
            "info": "Registros públicos provinciales.",
        },
    ]
    results["links"] = links
    return results