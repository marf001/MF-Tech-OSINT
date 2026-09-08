import re

MULTIPLIERS = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

PREFIX_TYPES = {
    "20": {"tipo": "Persona física (varón, CUIL)"},
    "23": {"tipo": "Persona humana (CUIT, tributa)"},
    "24": {"tipo": "Persona humana (CUIT, tributa)"},
    "27": {"tipo": "Persona física (mujer, CUIL)"},
    "30": {"tipo": "Empresa / Sociedad (CUIT)"},
    "33": {"tipo": "Asociación Civil / Cooperativa (CUIT)"},
    "34": {"tipo": "Fundación (CUIT)"},
}


def _normalize(cuit):
    return re.sub(r"[\s\-.]+", "", str(cuit).strip())


def validate_cuit(cuit):
    c = _normalize(cuit)
    results = {"raw": str(cuit), "valid": False, "error": None, "info": {}}

    if not re.match(r"^\d{11}$", c):
        results["error"] = "El CUIT/CUIL debe tener 11 dígitos."
        return results

    digits = [int(d) for d in c]
    prefix = "".join(map(str, digits[:2]))

    verifier = _calculate_verifier(digits)

    if verifier != digits[10]:
        results["error"] = f"El dígito verificador es {digits[10]} pero debería ser {verifier}. CUIT/CUIL inválido."
        return results

    info = PREFIX_TYPES.get(prefix, {"tipo": "Prefijo no mapeado"})
    results["valid"] = True
    results["info"] = {
        "prefijo": prefix,
        "tipo": info["tipo"],
        "dni": "".join(map(str, digits[2:10])),
        "digito_verificador": digits[10],
        "formateado": f"{digits[0]}{digits[1]}-{''.join(map(str, digits[2:10]))}-{digits[10]}",
    }
    return results


def _calculate_verifier(digits):
    total = sum(d * m for d, m in zip(digits[:10], MULTIPLIERS))
    remainder = total % 11
    dv = 11 - remainder
    if dv == 10:
        prefix = f"{digits[0]}{digits[1]}"
        dv = 4 if prefix == "27" else 9
    elif dv == 11:
        dv = 0
    return dv


def analyze_cuit(cuit):
    validated = validate_cuit(cuit)
    if not validated["valid"]:
        return {"valid": False, "error": validated.get("error", "CUIT/CUIL inválido"), "links": []}

    c = _normalize(cuit)
    links = [
        {
            "name": "AFIP - Situación Fiscal",
            "url": "https://www.afip.gob.ar/genericos/situacion-fiscal/",
            "info": f"Constancia de inscripción y situación en AFIP para {validated['info']['formateado']}.",
        },
        {
            "name": "AFIP - Constancia de Inscripción",
            "url": "https://www.afip.gob.ar/genericos/constancia-de-inscripcion/",
            "info": "Verificar constancia de inscripción oficial.",
        },
        {
            "name": "Boletín Oficial AR",
            "url": "https://www.boletinoficial.gob.ar/buscar?texto=" + c,
            "info": "Publicaciones del Boletín Oficial que mencionan este CUIT.",
        },
        {
            "name": "SENASA / Agroindustria",
            "url": "https://www.argentina.gob.ar",
            "info": "Portales oficiales con registros por CUIT.",
        },
        {
            "name": "Búsqueda web del CUIT",
            "url": f"https://www.google.com/search?q=%22{c}%22+OR+%22{validated['info']['formateado']}%22",
            "info": "Menciones públicas del número en internet.",
        },
        {
            "name": "LinkedIn (empresa)",
            "url": "https://www.linkedin.com/search/results/companies/?keywords=" + c,
            "info": "Compañías asociadas al CUIT.",
        },
    ]
    return {"valid": True, "info": validated["info"], "links": links}