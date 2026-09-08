"""Gestion de proyectos de investigacion.

Permite crear/cambiar/eliminar proyectos, guardar resultados de las busquedas
(automatico o manual) y generar un informe PDF con el detalle guardado.
"""

import datetime
import io
import json
import os
import secrets

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_FILE = os.path.join(BASE, "data", "proyectos.json")

MAX_RESULTADOS = 400
MAX_LINEAS = 200
MAX_LINEA = 300
MAX_DETALLE = 4000


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load():
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(proyectos):
    os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
    with open(_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(proyectos, f, ensure_ascii=False, indent=1)


def _find(pid):
    return next((p for p in _load() if p["id"] == pid), None)


def _recortar(texto, n=MAX_LINEA):
    texto = " ".join(str(texto).split())
    if len(texto) > n:
        return texto[: n - 3].rstrip() + "..."
    return texto


def list_proyectos():
    return _load()


def get_proyecto(pid):
    p = _find(pid)
    if not p:
        return None
    return dict(p)


def get_activo():
    for p in _load():
        if p.get("activo"):
            return p
    return None


def _publico(p):
    return {
        "id": p["id"],
        "nombre": p.get("nombre"),
        "descripcion": p.get("descripcion", ""),
        "creado": p.get("creado"),
        "actualizado": p.get("actualizado"),
        "activo": bool(p.get("activo")),
        "auto": bool(p.get("auto", True)),
        "n_resultados": len(p.get("resultados") or []),
    }


def create_proyecto(nombre, descripcion=""):
    nombre = (nombre or "").strip()
    if not nombre:
        return None, "Ingresá un nombre para el proyecto."
    proyectos = _load()
    rec = {
        "id": secrets.token_hex(6),
        "nombre": _recortar(nombre, 120),
        "descripcion": _recortar(descripcion or "", 500),
        "creado": _now(),
        "actualizado": _now(),
        "activo": False,
        "auto": True,
        "resultados": [],
    }
    if not any(p.get("activo") for p in proyectos):
        rec["activo"] = True
    proyectos.insert(0, rec)
    _save(proyectos)
    return rec, None


def delete_proyecto(pid):
    proyectos = _load()
    if not any(p["id"] == pid for p in proyectos):
        return False
    proyectos = [p for p in proyectos if p["id"] != pid]
    if not any(p.get("activo") for p in proyectos) and proyectos:
        proyectos[0]["activo"] = True
    _save(proyectos)
    return True


def set_activo(pid):
    proyectos = _load()
    found = None
    for p in proyectos:
        p["activo"] = p["id"] == pid
        if p["id"] == pid:
            found = p
            p["actualizado"] = _now()
    if found:
        _save(proyectos)
    return found


def set_auto(pid, value):
    proyectos = _load()
    p = next((x for x in proyectos if x["id"] == pid), None)
    if not p:
        return False
    p["auto"] = bool(value)
    p["actualizado"] = _now()
    _save(proyectos)
    return True


def desactivar_activo():
    proyectos = _load()
    changed = any(p.get("activo") for p in proyectos)
    for p in proyectos:
        p["activo"] = False
    if changed:
        _save(proyectos)
    return changed


def guardar_resultado(pid, data):
    proyectos = _load()
    p = next((x for x in proyectos if x["id"] == pid), None)
    if not p:
        return None

    tool = (data.get("tool") or "").strip()[:40]
    tool_nombre = _recortar(data.get("toolNombre") or tool or "", 60)
    objetivo = _recortar(data.get("objetivo") or "", 200)

    lineas = data.get("resumen") or []
    if not isinstance(lineas, list):
        lineas = [str(lineas)]
    lineas = [_recortar(x) for x in lineas if str(x or "").strip()][:MAX_LINEAS]

    links = data.get("links") or []
    links = [
        {
            "name": _recortar(l.get("name") or "Enlace", 120),
            "url": _recortar(l.get("url") or "", 500),
        }
        for l in links[:80]
        if isinstance(l, dict) and l.get("url")
    ]

    detalle = _recortar(data.get("detalle") or "", MAX_DETALLE)

    rec = {
        "id": secrets.token_hex(6),
        "tool": tool or "general",
        "tool_nombre": tool_nombre,
        "objetivo": objetivo,
        "fecha": _now(),
        "lineas": lineas,
        "links": links,
        "detalle": detalle,
        "auto": bool(data.get("auto")),
    }
    p["resultados"].append(rec)
    if len(p["resultados"]) > MAX_RESULTADOS:
        p["resultados"] = p["resultados"][-MAX_RESULTADOS:]
    p["actualizado"] = _now()
    _save(proyectos)
    return rec


def eliminar_resultado(pid, rid):
    proyectos = _load()
    p = next((x for x in proyectos if x["id"] == pid), None)
    if not p:
        return False
    antes = len(p["resultados"])
    p["resultados"] = [r for r in p["resultados"] if r["id"] != rid]
    if len(p["resultados"]) == antes:
        return False
    p["actualizado"] = _now()
    _save(proyectos)
    return True


def _l1(s):
    return str(s or "").encode("latin-1", "replace").decode("latin-1")


def generar_informe(proyecto, usuario):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(10, 24, 18)
    pdf.cell(0, 9, _l1("MF Tech - OSINT"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(0, 120, 90)
    pdf.cell(0, 8, _l1("Informe de investigación"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_draw_color(0, 150, 110)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.set_x(10)
    pdf.ln(5)

    meta = [
        ("Proyecto:", proyecto.get("nombre") or "-"),
        ("Descripción:", proyecto.get("descripcion") or "-"),
        ("Creado:", proyecto.get("creado") or "-"),
        ("Generado:", _now()),
        ("Usuario:", usuario or "-"),
        ("Resultados guardados:", str(len(proyecto.get("resultados") or []))),
    ]
    for k, v in meta:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(40, 50, 60)
        pdf.multi_cell(0, 6, _l1("%s %s" % (k, v)), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(pdf.get_y() + 2)

    resultados = proyecto.get("resultados") or []
    if not resultados:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(130, 130, 130)
        pdf.multi_cell(0, 6, _l1("Todavía no hay resultados guardados en este proyecto."), new_x="LMARGIN", new_y="NEXT")

    for i, r in enumerate(resultados, 1):
        pdf.set_draw_color(0, 224, 141)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.set_x(10)
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 20, 30)
        pdf.multi_cell(
            0, 6,
            _l1("#%d  %s" % (i, r.get("tool_nombre") or r.get("tool") or "Resultado")),
            new_x="LMARGIN", new_y="NEXT",
        )
        if r.get("objetivo"):
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(0, 120, 90)
            pdf.multi_cell(0, 5, _l1("Objetivo: " + r["objetivo"]), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, _l1("Fecha: " + (r.get("fecha") or "")), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(30, 40, 50)
        for linea in r.get("lineas") or []:
            pdf.multi_cell(0, 5, _l1(linea), new_x="LMARGIN", new_y="NEXT")

        for lk in r.get("links") or []:
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(0, 90, 160)
            pdf.multi_cell(0, 5, _l1(lk.get("name") or ""), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Courier", "", 7.5)
            pdf.set_text_color(80, 90, 100)
            pdf.multi_cell(0, 4, _l1(lk.get("url") or ""), new_x="LMARGIN", new_y="NEXT")

        if r.get("detalle"):
            pdf.set_font("Courier", "", 7.5)
            pdf.set_text_color(70, 80, 90)
            pdf.multi_cell(0, 4, _l1(r["detalle"]), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()