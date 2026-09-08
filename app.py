import socket
import os
import hmac
import re
import secrets
import threading
from io import BytesIO
from urllib.parse import quote
from flask import Flask, request, jsonify, render_template, session, redirect, send_file

from core import (
    search_email,
    search_username,
    search_phone,
    search_whois,
    validate_cuit,
    analyze_cuit,
    search_ddjj,
    generate_dorks,
    search_ip,
    search_subdomains,
    search_dns,
    search_dni,
    search_breach,
    search_empresa,
)
from core import license_engine
from core import notify as notify_mail
from core import lic_sig
from core import proyectos as proyectos_core
from core.gps_engine import (
    create_link,
    list_links,
    report_location,
    delete_link,
    start_tunnel,
    get_tunnel_url,
    get_public_base,
    set_fallback_base,
)

MASTER = lic_sig.is_master()

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_SECRET_FILE = os.path.join(_DATA_DIR, ".secret")


def _load_secret():
    try:
        if os.path.exists(_SECRET_FILE):
            with open(_SECRET_FILE, "r", encoding="utf-8") as f:
                s = f.read().strip()
                if s:
                    return s
    except Exception:
        pass
    s = secrets.token_hex(32)
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(s)
    except Exception:
        pass
    return s


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.secret_key = _load_secret()


def _is_logged():
    return bool(session.get("user"))


def _is_admin():
    return bool(session.get("is_admin"))


def _current_user():
    if MASTER:
        return session.get("user")
    payload, _ = _liesencia()
    return payload.get("usuario") if payload else None


def _proyecto_activo_info():
    p = proyectos_core.get_activo()
    if not p:
        return None
    return {"id": p["id"], "nombre": p["nombre"], "auto": bool(p.get("auto"))}


def _liesencia():
    """Cliente: lee+valida el archivo de licencia firmado. Devuelve (payload, error)."""
    doc = lic_sig.license_read()
    return lic_sig.license_validate(doc)


@app.before_request
def _gate():
    path = request.path
    public = (
        path in ("/", "/login", "/activar", "/favicon.ico", "/favicon")
        or path.startswith((
            "/static/",
            "/api/login",
            "/api/me",
            "/api/login-licencia",
            "/api/license/check",
            "/gps/",
            "/api/gps/report/",
        ))
    )
    if public:
        return None
    if MASTER:
        if not _is_logged():
            if path.startswith("/api/"):
                return jsonify({"error": "No autorizado."}), 401
            return redirect("/login")
        return None
    payload, err = _liesencia()
    if payload:
        return None
    if path.startswith("/api/"):
        return jsonify({"error": "Sistema sin activar: %s" % err}), 401
    return redirect("/")


@app.route("/")
def index():
    if MASTER:
        if not _is_logged():
            return redirect("/login")
        return render_template("index.html")
    payload, err = _liesencia()
    if payload:
        session["user"] = payload["usuario"]
        session["is_admin"] = False
        return render_template("index.html")
    return render_template("activar.html", machine=lic_sig.machine_code(), error=err)


@app.route("/activar")
def activar_page():
    if MASTER:
        return redirect("/")
    payload, err = _liesencia()
    if payload:
        return redirect("/")
    return render_template("activar.html", machine=lic_sig.machine_code(), error=err)


@app.route("/login")
def login_page():
    if not MASTER:
        return redirect("/")
    if _is_logged():
        return redirect("/")
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    if not MASTER:
        return jsonify({"error": "Este build se activa con archivo de licencia firmado, no con contraseñas."}), 403
    data = request.get_json(silent=True) or {}
    usuario = (data.get("usuario") or "").strip()
    clave = data.get("clave") or ""
    stored = lic_sig.admin_password()
    if stored is not None and hmac.compare_digest(usuario, "admin") and hmac.compare_digest(clave, stored):
        session.clear()
        session["user"] = "admin"
        session["is_admin"] = True
        return jsonify({"ok": True, "user": "admin", "rol": "admin"})
    return jsonify({"ok": False, "error": "Usuario o contraseña incorrectos."}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    if MASTER:
        return jsonify({
            "auth": _is_logged(),
            "user": session.get("user"),
            "is_admin": _is_admin(),
            "rol": "admin" if _is_admin() else ("cliente" if _is_logged() else None),
            "master": True,
            "proyecto_activo": _proyecto_activo_info(),
            "tunnel": {
                "url": get_tunnel_url(),
                "running": get_tunnel_url() is not None,
            },
        })
    payload, err = _liesencia()
    if payload:
        return jsonify({
            "auth": True,
            "user": payload.get("usuario"),
            "is_admin": False,
            "rol": "cliente",
            "master": False,
            "activacion": {"ok": True, "version": payload.get("version")},
            "proyecto_activo": _proyecto_activo_info(),
        })
    return jsonify({
        "auth": False,
        "user": None,
        "is_admin": False,
        "rol": None,
        "master": False,
        "activacion": {"ok": False, "error": err, "machine": lic_sig.machine_code()},
        "proyecto_activo": None,
    })


@app.route("/api/tools")
def api_tools():
    tools = [
        {
            "id": "email",
            "nombre": "Email OSINT",
            "desc": "Verifica a qué plataformas está asociado un email (holehe).",
            "requires": "email@dominio.com",
            "resultType": "email",
        },
        {
            "id": "usuario",
            "nombre": "Usuario / Nickname",
            "desc": "Busca un usuario en más de 300 plataformas (sherlock).",
            "requires": "nickname",
            "resultType": "user",
        },
        {
            "id": "telefono",
            "nombre": "Teléfono",
            "desc": "Valida número, operador, geolocalización y genera enlaces de búsqueda.",
            "requires": "+5491100000000",
            "resultType": "phone",
        },
        {
            "id": "whois",
            "nombre": "Whois / Dominio",
            "desc": "Registro del dominio, DNS e IP (python-whois).",
            "requires": "dominio.com",
            "resultType": "whois",
        },
        {
            "id": "cuit",
            "nombre": "CUIT / CUIL (Argentina)",
            "desc": "Valida el número, determina tipo de persona/sociedad y genera enlaces.",
            "requires": "20XXXXXXXXX (11 dígitos)",
            "resultType": "cuit",
        },
        {
            "id": "ddjj",
            "nombre": "Declaraciones Juradas",
            "desc": "Acceso a portales oficiales y datasets de declaraciones juradas.",
            "requires": "Nombre y Apellido (opcional)",
            "resultType": "ddjj",
        },
        {
            "id": "dorks",
            "nombre": "Google Dorks",
            "desc": "Genera búsquedas avanzadas para footprinting de una persona o entidad.",
            "requires": "texto a investigar",
            "resultType": "dorks",
        },
        {
            "id": "ip",
            "nombre": "IP Intelligence",
            "desc": "WHOIS de IP, reverse DNS, geolocalización y enlaces de reputación/abuso.",
            "requires": "8.8.8.8",
            "resultType": "ip",
        },
        {
            "id": "subdominios",
            "nombre": "Subdominios",
            "desc": "Enumeración de subdominios pasiva (crt.sh + sublist3r), sin API.",
            "requires": "dominio.com",
            "resultType": "subdomains",
        },
        {
            "id": "dns",
            "nombre": "DNS Records",
            "desc": "Consulta registros DNS (A, AAAA, MX, NS, TXT, CNAME, SOA...) sin API.",
            "requires": "dominio.com",
            "resultType": "dns",
        },
        {
            "id": "dni",
            "nombre": "DNI (Argentina)",
            "desc": "Enlaces de consulta de padrones y verificación de identidad.",
            "requires": "N° documento (6-8 dígitos)",
            "resultType": "dni",
        },
        {
            "id": "breach",
            "nombre": "Breach / Leaks",
            "desc": "Enlaces para verificar filtraciones de email/usuario en brechas.",
            "requires": "email@dominio.com",
            "resultType": "breach",
        },
        {
            "id": "empresa",
            "nombre": "Empresa (Argentina)",
            "desc": "Boletín Oficial, BCRA, IGJ, AFIP y contrataciones por razón social o CUIT.",
            "requires": "razón social o CUIT",
            "resultType": "empresa",
        },
        {
            "id": "gps",
            "nombre": "Localización (GPS)",
            "desc": "Genera un link y un mensaje amable (podés elegir entre varios) para que alguien COMPARTA su ubicación voluntariamente y la veas en Google Maps.",
            "requires": "elegir un mensaje",
            "resultType": "gps",
        },
        {
            "id": "proyectos",
            "nombre": "Proyectos",
            "desc": "Creá y gestioná proyectos de investigación. Guardá lo que buscaste y generá un informe en PDF.",
            "requires": "",
            "resultType": "proyectos",
        },
        {
            "id": "admin",
            "nombre": "Administración",
            "desc": "Licencias, clientes y notificaciones por email.",
            "requires": "",
            "resultType": "admin",
            "adminOnly": True,
        },
    ]
    if not _is_admin():
        tools = [t for t in tools if not t.get("adminOnly")]
    return jsonify({"tools": tools})


@app.route("/api/search/email", methods=["POST"])
def email_search():
    data = request.get_json(silent=True) or {}
    email = (data.get("query") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Ingrese un email válido."}), 400
    result = search_email(email)
    dorks = generate_dorks(email, "email")
    result["dorks"] = dorks
    return jsonify(result)


@app.route("/api/search/usuario", methods=["POST"])
def user_search():
    data = request.get_json(silent=True) or {}
    user = (data.get("query") or "").strip()
    if not user:
        return jsonify({"error": "Ingrese un usuario."}), 400
    result = search_username(user)
    dorks = generate_dorks(user, "usuario")
    result["dorks"] = dorks
    return jsonify(result)


@app.route("/api/search/telefono", methods=["POST"])
def phone_search():
    data = request.get_json(silent=True) or {}
    num = (data.get("query") or "").strip()
    if not num:
        return jsonify({"error": "Ingrese un número de teléfono."}), 400
    result = search_phone(num)
    dorks = generate_dorks(num, "telefono")
    result["dorks"] = dorks
    return jsonify(result)


@app.route("/api/search/whois", methods=["POST"])
def whois_search():
    data = request.get_json(silent=True) or {}
    domain = (data.get("query") or "").strip()
    if not domain:
        return jsonify({"error": "Ingrese un dominio."}), 400
    result = search_whois(domain)
    dorks = generate_dorks(domain, "dominio")
    result["dorks"] = dorks
    return jsonify(result)


@app.route("/api/search/cuit", methods=["POST"])
def cuit_search():
    data = request.get_json(silent=True) or {}
    cuit = (data.get("query") or "").strip()
    if not cuit:
        return jsonify({"error": "Ingrese un CUIT/CUIL."}), 400
    result = analyze_cuit(cuit)
    if not result.get("valid"):
        return jsonify({"error": result.get("error", "CUIT/CUIL inválido.")}), 400
    return jsonify(result)


@app.route("/api/search/ddjj", methods=["POST"])
def ddjj_search():
    data = request.get_json(silent=True) or {}
    persona = (data.get("query") or "").strip()
    result = search_ddjj(persona)
    return jsonify(result)


@app.route("/api/search/dorks", methods=["POST"])
def dorks_search():
    data = request.get_json(silent=True) or {}
    target = (data.get("query") or "").strip()
    tipo = (data.get("tipo") or "persona").strip()
    if not target:
        return jsonify({"error": "Ingrese el texto a investigar."}), 400
    dorks = generate_dorks(target, tipo)
    return jsonify({"target": target, "tipo": tipo, "dorks": dorks})


@app.route("/api/search/ip", methods=["POST"])
def ip_search():
    data = request.get_json(silent=True) or {}
    ip = (data.get("query") or "").strip()
    if not ip:
        return jsonify({"error": "Ingrese una dirección IP."}), 400
    result = search_ip(ip)
    return jsonify(result)


@app.route("/api/search/subdominios", methods=["POST"])
def subdomains_search():
    data = request.get_json(silent=True) or {}
    domain = (data.get("query") or "").strip()
    if not domain:
        return jsonify({"error": "Ingrese un dominio."}), 400
    result = search_subdomains(domain)
    return jsonify(result)


@app.route("/api/search/dns", methods=["POST"])
def dns_search():
    data = request.get_json(silent=True) or {}
    domain = (data.get("query") or "").strip()
    if not domain:
        return jsonify({"error": "Ingrese un dominio."}), 400
    result = search_dns(domain)
    return jsonify(result)


@app.route("/api/search/dni", methods=["POST"])
def dni_search():
    data = request.get_json(silent=True) or {}
    dni = (data.get("query") or "").strip()
    if not dni:
        return jsonify({"error": "Ingrese un número de DNI."}), 400
    result = search_dni(dni)
    return jsonify(result)


@app.route("/api/search/breach", methods=["POST"])
def breach_search():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Ingrese un email o usuario."}), 400
    result = search_breach(q)
    return jsonify(result)


@app.route("/api/search/empresa", methods=["POST"])
def empresa_search():
    data = request.get_json(silent=True) or {}
    q = (data.get("query") or "").strip()
    if not q:
        return jsonify({"error": "Ingrese una razón social o CUIT."}), 400
    result = search_empresa(q)
    return jsonify(result)


GPS_TEMPLATES = [
    {
        "id": "coordinar",
        "label": "Coordinar un encuentro",
        "text": "¡Hola! 😊 ¿Me das una mano? Necesito tu ubicación para coordinar con vos. Tocá el link de abajo y elegí 'Compartir mi ubicación' (se envía una sola vez y solo si tocás el botón verde). ¡Gracias!",
    },
    {
        "id": "entrega",
        "label": "Confirmar entrega / paquete",
        "text": "¡Hola! 🚚 Para resolver lo de la entrega necesito confirmar dónde estás. Tocá el link de abajo y compartí tu ubicación cuando puedas (solo se envía una vez, si le das al botón verde). ¡Muchas gracias!",
    },
    {
        "id": "reunion",
        "label": "Reunión / cita",
        "text": "¡Hola! 👋 Para concretar nuestra reunión, compartime dónde estás. Tocá el link y enviá tu ubicación (una sola vez y con tu confirmación). ¡Gracias!",
    },
    {
        "id": "seguimiento",
        "label": "Seguimiento / confirmar bienestar",
        "text": "¡Hola! 📍 Solo quiero confirmar que estás bien y en un lugar seguro. Tocá el link de abajo y compartí tu ubicación (una sola vez). ¡Gracias por avisarme!",
    },
    {
        "id": "favor",
        "label": "Pedir un favor / ayuda",
        "text": "¡Hola! 🙏 Necesito una mano y necesito saber dónde estás para organizarme. Tocá el link de abajo y compartí tu ubicación cuando puedas (solo una vez). ¡Te agradezco un montón!",
    },
]


@app.route("/api/gps/templates", methods=["GET"])
def gps_templates():
    return jsonify({"templates": GPS_TEMPLATES})


@app.route("/api/search/gps", methods=["POST"])
def gps_create():
    data = request.get_json(silent=True) or {}
    template_id = (data.get("template_id") or "").strip()
    nota = (data.get("nota") or "").strip()

    if template_id == "personalizado":
        text = (data.get("mensaje") or "").strip()
        if not text:
            return jsonify({"error": "Escribí el mensaje personalizado."}), 400
        if len(text) > 500:
            return jsonify({"error": "El mensaje personalizado no puede superar los 500 caracteres."}), 400
        template_label = "Mensaje personalizado"
    else:
        tpl = next((t for t in GPS_TEMPLATES if t["id"] == template_id), GPS_TEMPLATES[0])
        text = tpl["text"]
        template_label = tpl["label"]

    kwargs = {}
    if template_id == "personalizado":
        kwargs["texto"] = text
    rec = create_link(nota, template_id, **kwargs)
    url = rec["url"]
    mensaje = text + "\n\n" + url
    whatsapp = f"https://wa.me/?text={quote(mensaje)}"
    telegram = f"https://t.me/share/url?url={quote(url)}&text={quote(text)}"
    asunto = "Compartir tu ubicación"
    mailto = "mailto:?subject=" + quote(asunto) + "&body=" + quote(mensaje)
    return jsonify({
        "id": rec["id"],
        "link": url,
        "local": f"http://127.0.0.1:8090{rec['path']}",
        "whatsapp": whatsapp,
        "telegram": telegram,
        "mailto": mailto,
        "mensaje": mensaje,
        "template": template_label,
        "nota": nota,
        "estado": rec["estado"],
        "tunnel": get_tunnel_url() is not None,
    })


@app.route("/api/gps/links", methods=["GET"])
def gps_links():
    return jsonify({"records": list_links()})


@app.route("/api/gps/links/<token>", methods=["DELETE"])
def gps_delete(token):
    if delete_link(token):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Link no encontrado."}), 404


@app.route("/api/gps/tunnel", methods=["GET"])
def gps_tunnel():
    url = get_tunnel_url()
    return jsonify({
        "url": url,
        "running": url is not None,
        "cloudflared": os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "cloudflared.exe")),
    })


@app.route("/api/gps/report/<token>", methods=["POST"])
def gps_report(token):
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get("lat"))
        lng = float(data.get("lng"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Coordenadas inválidas."}), 400
    accuracy = data.get("accuracy")
    if accuracy is not None:
        try:
            accuracy = float(accuracy)
        except (TypeError, ValueError):
            accuracy = None
    if not report_location(token, lat, lng, accuracy):
        return jsonify({"ok": False, "error": "Link desconocido o expirado."}), 404
    return jsonify({"ok": True})


@app.route("/gps/<token>", methods=["GET"])
def gps_page(token):
    records = list_links()
    rec = next((r for r in records if r["id"] == token), None)
    if not rec:
        return render_template("gps.html", token=token, nota="desconocido")
    nota = rec.get("nota") or rec.get("numero") or "desconocido"
    return render_template("gps.html", token=token, nota=nota)


@app.route("/api/license/check", methods=["POST"])
def license_check():
    if not MASTER:
        return jsonify({"error": "No disponible en build de cliente."}), 403
    data = request.get_json(silent=True) or {}
    clave = data.get("clave") or ""
    return jsonify(license_engine.check_key(clave))


@app.route("/api/login-licencia", methods=["POST"])
def login_licencia():
    if not MASTER:
        return jsonify({"error": "No disponible en build de cliente."}), 403
    data = request.get_json(silent=True) or {}
    return jsonify(license_engine.check_login(
        data.get("usuario") or "",
        data.get("clave") or "",
    ))


@app.route("/api/activacion")
def api_activacion():
    if MASTER:
        return jsonify({"master": True, "ok": None})
    payload, err = _liesencia()
    return jsonify({
        "ok": payload is not None,
        "error": err,
        "machine": lic_sig.machine_code(),
    })


@app.route("/api/proyectos")
def proyectos_list():
    return jsonify({
        "proyectos": proyectos_core.list_proyectos(),
        "activo": proyectos_core.get_activo(),
    })


@app.route("/api/proyectos", methods=["POST"])
def proyectos_create():
    data = request.get_json(silent=True) or {}
    rec, err = proyectos_core.create_proyecto(data.get("nombre") or "", data.get("descripcion") or "")
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True, "proyecto": rec})


@app.route("/api/proyectos/<pid>")
def proyectos_get(pid):
    p = proyectos_core.get_proyecto(pid)
    if not p:
        return jsonify({"error": "Proyecto no encontrado."}), 404
    return jsonify({"proyecto": p})


@app.route("/api/proyectos/<pid>", methods=["DELETE"])
def proyectos_delete(pid):
    if proyectos_core.delete_proyecto(pid):
        return jsonify({"ok": True})
    return jsonify({"error": "Proyecto no encontrado."}), 404


@app.route("/api/proyectos/<pid>/activar", methods=["POST"])
def proyectos_activar(pid):
    p = proyectos_core.set_activo(pid)
    if not p:
        return jsonify({"error": "Proyecto no encontrado."}), 404
    return jsonify({"ok": True, "proyecto": p})


@app.route("/api/proyectos/<pid>/autoguardar", methods=["POST"])
def proyectos_auto(pid):
    data = request.get_json(silent=True) or {}
    if not proyectos_core.set_auto(pid, bool(data.get("auto"))):
        return jsonify({"error": "Proyecto no encontrado."}), 404
    return jsonify({"ok": True})


@app.route("/api/proyectos/desactivar", methods=["POST"])
def proyectos_desactivar():
    proyectos_core.desactivar_activo()
    return jsonify({"ok": True})


@app.route("/api/proyectos/<pid>/guardar", methods=["POST"])
def proyectos_guardar(pid):
    data = request.get_json(silent=True) or {}
    rec = proyectos_core.guardar_resultado(pid, data)
    if rec is None:
        return jsonify({"error": "Proyecto no encontrado."}), 404
    return jsonify({"ok": True, "resultado": rec})


@app.route("/api/proyectos/<pid>/resultados/<rid>", methods=["DELETE"])
def proyectos_del_resultado(pid, rid):
    if proyectos_core.eliminar_resultado(pid, rid):
        return jsonify({"ok": True})
    return jsonify({"error": "Resultado no encontrado."}), 404


@app.route("/api/proyectos/<pid>/informe")
def proyectos_informe(pid):
    p = proyectos_core.get_proyecto(pid)
    if not p:
        return jsonify({"error": "Proyecto no encontrado."}), 404
    data = proyectos_core.generar_informe(p, _current_user())
    nombre = re.sub(r"[^A-Za-z0-9]+", "-", p.get("nombre") or "proyecto").strip("-")
    nombre = nombre or "proyecto"
    return send_file(
        BytesIO(data),
        mimetype="application/pdf",
        as_attachment=False,
        download_name="informe_%s.pdf" % nombre,
    )


def _admin_guard():
    if not _is_admin():
        return jsonify({"error": "Sin permisos de administración."}), 403
    return None


@app.route("/api/admin/stats")
def admin_stats():
    g = _admin_guard()
    if g:
        return g
    return jsonify(license_engine.get_stats())


@app.route("/api/admin/licenses")
def admin_licenses():
    g = _admin_guard()
    if g:
        return g
    return jsonify({"licenses": license_engine.list_licenses(), "stats": license_engine.get_stats()})


@app.route("/api/admin/licenses", methods=["POST"])
def admin_create_license():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    rec = license_engine.create_license(data.get("version"), data.get("notas"))
    return jsonify({"ok": True, "licencia": rec})


@app.route("/api/admin/emitir", methods=["POST"])
def admin_emitir():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    rid = data.get("pool_id") or data.get("rid")
    if not rid:
        return jsonify({"error": "Falta el id de la licencia."}), 400
    doc, err = license_engine.emit_client_license(
        rid,
        maquina=(data.get("maquina") or "").strip() or None,
        expira=(data.get("expira") or "").strip() or None,
    )
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True, "archivo": "data/licencia.rel", "payload": doc["payload"]})


@app.route("/api/admin/certificados")
def admin_certificados():
    g = _admin_guard()
    if g:
        return g
    with open(os.path.join(_DATA_DIR, "master", "certificados.json"), "r", encoding="utf-8") as f:
        import json as _json
        return jsonify({"certificados": _json.load(f)})


@app.route("/api/admin/licenses/<rid>/asignar", methods=["POST"])
def admin_assign(rid):
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    rec, err = license_engine.assign_license(
        rid,
        data.get("usuario") or "",
        data.get("email") or "",
        data.get("version") or "",
    )
    if err:
        return jsonify({"error": err}), 400
    cuerpo = (
        "Se asignó una licencia de MF Tech - OSINT.\n\n"
        "Cliente: %s\nEmail: %s\nVersión: %s\n"
        "Clave de acceso: %s\n\n"
        "El cliente debe ingresar en el panel con su usuario y esta clave (edición clientes).\n"
        "- Enviado desde el servidor MF Tech OSINT." % (rec["usuario"], rec["email"], rec["version"], rec["clave"])
    )
    destinos = [notify_mail._load_config().get("to")]
    if rec.get("email"):
        destinos.append(rec["email"])
    res = notify_mail.send_email(
        "[MF Tech OSINT] Licencia asignada - %s (%s)" % (rec["usuario"], rec["version"]),
        cuerpo,
        kind="asignacion",
        destinos=destinos,
    )
    return jsonify({"ok": True, "licencia": rec, "email": res})


@app.route("/api/admin/licenses/<rid>/recuperar", methods=["POST"])
def admin_recover(rid):
    g = _admin_guard()
    if g:
        return g
    rec = license_engine.find_license(rid)
    if not rec:
        return jsonify({"error": "Licencia no encontrada."}), 404
    if rec.get("estado") != "asignada":
        return jsonify({"error": "La licencia no está asignada."}), 400
    cuerpo = (
        "Recuperación de acceso / aviso.\n\n"
        "Cliente: %s\nEmail: %s\nVersión: %s\n"
        "Clave de acceso: %s\n\n"
        "Si se reporta un problema con esta licencia, revisá el panel y contactá al cliente."
        % (rec["usuario"], rec["email"], rec["version"], rec["clave"])
    )
    destinos = [notify_mail._load_config().get("to")]
    if rec.get("email"):
        destinos.append(rec["email"])
    res = notify_mail.send_email(
        "[MF Tech OSINT] Recuperación / aviso - %s" % rec["usuario"],
        cuerpo,
        kind="recuperacion",
        destinos=destinos,
    )
    return jsonify({"ok": True, "licencia": rec, "email": res})


@app.route("/api/admin/licenses/<rid>/revocar", methods=["POST"])
def admin_revoke(rid):
    g = _admin_guard()
    if g:
        return g
    rec, err = license_engine.revoke_license(rid)
    if err:
        return jsonify({"error": err}), 400
    res = notify_mail.send_email(
        "[MF Tech OSINT] Licencia revocada - %s" % (rec.get("usuario") or rec.get("clave")),
        "Se revocó la licencia %s del cliente %s.\n\nLa clave dejará de ser válida al instante."
        % (rec.get("clave"), rec.get("usuario") or "-"),
        kind="revocacion",
    )
    return jsonify({"ok": True, "licencia": rec, "email": res})


@app.route("/api/admin/email", methods=["POST"])
def admin_email():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    tipo = (data.get("tipo") or "aviso").strip()
    mensaje = (data.get("mensaje") or "").strip()
    if not mensaje:
        return jsonify({"error": "Escribí el aviso."}), 400
    lic = None
    rid = data.get("licencia_id")
    if rid:
        lic = license_engine.find_license(rid)
    cuerpo = "Notificación: %s\n\n%s" % (tipo, mensaje)
    if lic:
        cuerpo += "\n\nRelacionada con la licencia: %s (cliente: %s, email: %s, versión: %s)" % (
            lic.get("clave"), lic.get("usuario") or "-", lic.get("email") or "-", lic.get("version") or "-"
        )
    res = notify_mail.send_email("[MF Tech OSINT] %s" % tipo.upper(), cuerpo, kind="aviso")
    return jsonify({"ok": True, "email": res})


@app.route("/api/admin/email-config", methods=["GET"])
def admin_email_config_get():
    g = _admin_guard()
    if g:
        return g
    cfg = notify_mail._load_config()
    cfg["smtp_pass"] = cfg.get("smtp_pass") or ""
    return jsonify(cfg)


@app.route("/api/admin/email-config", methods=["POST"])
def admin_email_config_save():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    return jsonify(notify_mail.save_config(data))


@app.route("/api/admin/email-test", methods=["POST"])
def admin_email_test():
    g = _admin_guard()
    if g:
        return g
    data = request.get_json(silent=True) or {}
    notify_mail.save_config(data)
    cfg = notify_mail._load_config()
    res = notify_mail.send_email(
        "[MF Tech OSINT] Prueba de email",
        "Este es un correo de prueba desde el servidor MF Tech - OSINT.",
        kind="prueba",
    )
    return jsonify({"ok": res["ok"], "destino": res["destino"], "error": res["error"]})


@app.route("/api/admin/notificaciones")
def admin_notificaciones():
    g = _admin_guard()
    if g:
        return g
    return jsonify(notify_mail.get_log())


def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for addr in socket.gethostbyname_ex(hostname)[2]:
            if addr.startswith("127."):
                continue
            ips.append(addr)
    except Exception:
        pass
    if "127.0.0.1" not in ips:
        ips.append("127.0.0.1")
    return ips


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    ip = "0.0.0.0"
    inits = get_local_ips()
    set_fallback_base(f"http://{inits[0]}:{port}" if inits else f"http://127.0.0.1:{port}")
    if MASTER:
        if license_engine.init_pool(100):
            print("  Pool de 100 licencias generado en data/licenses.json")
    else:
        print("  MODO CLIENTE: este equipo se activa con el archivo data/licencia.rel firmado por tu proveedor.")
        print("  Código de licencia de esta PC: %s" % lic_sig.machine_code())
    start_tunnel(f"http://127.0.0.1:{port}")
    print("=" * 60)
    print("  MF Tech - OSINT  -  Panel de búsqueda")
    print("=" * 60)
    for i in inits:
        print(f"  Accede desde un navegador: http://{i}:{port}")
    print("  Túnel público (Cloudflare): detectando...")

    def _anunciar_tunel():
        for _ in range(40):
            url = get_tunnel_url()
            if url:
                print(f"  URL pública (HTTPS)       : {url}")
                return
            threading.Event().wait(3)
        print("  Túnel público: no disponible aún (revisar internet).")

    threading.Thread(target=_anunciar_tunel, daemon=True).start()
    print("  Ctrl+C para detener el servidor.")
    print("=" * 60)
    app.run(host=ip, port=port, debug=False, threaded=True)