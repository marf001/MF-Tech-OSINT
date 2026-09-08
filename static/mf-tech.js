(function () {
  "use strict";

  var tools = [];
  var activeTool = null;
  var isAdmin = false;

  var tabsEl = document.getElementById("tabs");
  var queryEl = document.getElementById("query");
  var extraTypeEl = document.getElementById("extraType");
  var gpsTemplateEl = document.getElementById("gpsTemplate");
  var gpsNotaEl = document.getElementById("gpsNota");
  var gpsCustomBoxEl = document.getElementById("gpsCustomBox");
  var gpsCustomMsgEl = document.getElementById("gpsCustomMsg");
  var gpsCountEl = document.getElementById("gpsCount");
  var btnEl = document.getElementById("btnSearch");
  var loadingEl = document.getElementById("loading");
  var loadingTextEl = document.getElementById("loadingText");
  var resultsEl = document.getElementById("results");
  var statusEl = document.getElementById("statusText");
  var statusUserEl = document.getElementById("statusUser");
  var btnLogoutEl = document.getElementById("btnLogout");
  var gpsTemplatesCached = null;
  var gpsPollTimer = null;
  var gpsSig = "";
  var lastGpsId = null;
  var gpsListenersAttached = false;
  var activeProyecto = null;
  var projView = "list";
  var projDetailId = null;
  var lastSummary = null;
  var proyectoBarEl = document.getElementById("proyectoBar");

  var FALLBACK_GPS_TEMPLATES = [
    { id: "coordinar", label: "Coordinar un encuentro" },
    { id: "entrega", label: "Confirmar entrega / paquete" },
    { id: "reunion", label: "Reunión / cita" },
    { id: "seguimiento", label: "Seguimiento / confirmar bienestar" },
    { id: "favor", label: "Pedir un favor / ayuda" }
  ];

  var FALLBACK_TOOLS = [
    { id: "email", nombre: "Email", requires: "alguien@correo.com" },
    { id: "usuario", nombre: "Usuario", requires: "nickname" },
    { id: "telefono", nombre: "Teléfono", requires: "+541123456789" },
    { id: "whois", nombre: "Whois / Dominio", requires: "dominio.com" },
    { id: "cuit", nombre: "CUIT / CUIL", requires: "20-12345678-9" },
    { id: "ddjj", nombre: "DDJJ", requires: "Nombre o dejar vacío" },
    { id: "dorks", nombre: "Dorks", requires: "Nombre a investigar (requiere tipo)" },
    { id: "ip", nombre: "IP", requires: "8.8.8.8" },
    { id: "subdominios", nombre: "Subdominios", requires: "dominio.com" },
    { id: "dns", nombre: "DNS", requires: "dominio.com" },
    { id: "dni", nombre: "DNI", requires: "30112233" },
    { id: "breach", nombre: "Leaks", requires: "email o usuario" },
    { id: "empresa", nombre: "Empresa", requires: "Nombre o razón social" },
    { id: "gps", nombre: "Localización (GPS)", requires: "elegir un mensaje abajo" },
    { id: "proyectos", nombre: "Proyectos", requires: "" },
    { id: "admin", nombre: "Administración", requires: "" }
  ];

  if (location.protocol === "file:") {
    if (resultsEl) {
      resultsEl.innerHTML = '<div class="error-box">Estás viendo el archivo HTML directo (doble clic). Este sistema necesita el servidor local: doble clic en <strong>iniciar.bat</strong> y abrí <strong>http://localhost:8090</strong> en el navegador.</div>';
    }
    return;
  }

  function esc(s) {
    if (s == null) return "";
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setStatus(on) {
    statusEl.textContent = on ? "Sistema operativo" : "Análisis en curso...";
  }

  function showLoading(on, msg) {
    loadingEl.style.display = on ? "flex" : "none";
    btnEl.disabled = on;
    setStatus(!on);
    if (on && loadingTextEl) loadingTextEl.textContent = msg || "Ejecutando análisis...";
  }

  function renderToolbar() {
    tabsEl.innerHTML = "";
    tools.forEach(function (t) {
      if (t.adminOnly && !isAdmin) return;
      var b = document.createElement("button");
      b.className = "tab";
      b.textContent = t.nombre;
      b.dataset.id = t.id;
      b.addEventListener("click", function () { setActive(t.id); });
      tabsEl.appendChild(b);
    });
  }

  function setActive(id) {
    activeTool = tools.find(function (t) { return t.id === id; }) || tools[0];
    document.querySelectorAll(".tab").forEach(function (b) {
      b.classList.toggle("active", b.dataset.id === activeTool.id);
    });
    var isGps = activeTool.id === "gps";
    var isDorks = activeTool.id === "dorks";
    var isAdminTab = activeTool.id === "admin";
    var isProyectos = activeTool.id === "proyectos";
    queryEl.placeholder = "Ej: " + (activeTool.requires || "");
    queryEl.style.display = (isGps || isAdminTab || isProyectos) ? "none" : "";
    extraTypeEl.style.display = isDorks ? "block" : "none";
    if (gpsTemplateEl) gpsTemplateEl.style.display = isGps ? "block" : "none";
    if (gpsNotaEl) gpsNotaEl.style.display = isGps ? "block" : "none";
    if (isGps) populateGpsTemplates();
    if (!isGps) stopGpsPolling();
    resultsEl.innerHTML = "";
    if (isGps) {
      resultsEl.innerHTML = '<div id="gps-dashboard"></div>';
      loadGpsDashboard();
      startGpsPolling();
    } else if (isAdminTab) {
      resultsEl.innerHTML = '<div id="admin-dash"></div>';
      loadAdminDashboard();
    } else if (isProyectos) {
      projView = "list";
      projDetailId = null;
      resultsEl.innerHTML = '<div id="proj-dash"></div>';
      loadProjectDashboard();
    }
  }

  function startGpsPolling() {
    if (gpsPollTimer) return;
    gpsPollTimer = setInterval(function () {
      loadGpsDashboard();
    }, 5000);
  }

  function stopGpsPolling() {
    if (gpsPollTimer) {
      clearInterval(gpsPollTimer);
      gpsPollTimer = null;
    }
    gpsSig = "";
  }

  function populateGpsTemplates() {
    if (!gpsTemplateEl) return;
    if (!gpsListenersAttached) {
      gpsListenersAttached = true;
      gpsTemplateEl.addEventListener("change", updateGpsCustomBox);
      if (gpsCustomMsgEl) {
        gpsCustomMsgEl.addEventListener("input", updateGpsCount);
      }
    }
    var fill = function (list) {
      if (gpsTemplateEl.children.length) { updateGpsCustomBox(); return; }
      gpsTemplateEl.innerHTML = "";
      var opts = (list && list.length) ? list : FALLBACK_GPS_TEMPLATES;
      opts.forEach(function (t) {
        var o = document.createElement("option");
        o.value = t.id;
        o.textContent = t.label;
        gpsTemplateEl.appendChild(o);
      });
      var c = document.createElement("option");
      c.value = "personalizado";
      c.textContent = "Mensaje personalizado";
      gpsTemplateEl.appendChild(c);
      updateGpsCustomBox();
    };
    if (gpsTemplatesCached) { fill(gpsTemplatesCached); return; }
    fetch("/api/gps/templates")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        gpsTemplatesCached = (d && d.templates) || FALLBACK_GPS_TEMPLATES;
        fill(gpsTemplatesCached);
      })
      .catch(function () {
        gpsTemplatesCached = FALLBACK_GPS_TEMPLATES;
        fill(gpsTemplatesCached);
      });
  }

  function updateGpsCustomBox() {
    if (!gpsCustomBoxEl) return;
    var isCustom = gpsTemplateEl && gpsTemplateEl.value === "personalizado";
    gpsCustomBoxEl.style.display = isCustom ? "block" : "none";
    if (isCustom) updateGpsCount();
  }

  function updateGpsCount() {
    if (!gpsCountEl || !gpsCustomMsgEl) return;
    gpsCountEl.textContent = gpsCustomMsgEl.value.length + " / 500";
  }

  function fetchTools() {
    var apply = function (list) {
      tools = list && list.length ? list : FALLBACK_TOOLS;
      renderToolbar();
      setActive(tools[0] ? tools[0].id : null);
    };
    fetch("/api/tools")
      .then(function (r) { return r.json(); })
      .then(function (data) { apply(data.tools); })
      .catch(function () {
        apply(FALLBACK_TOOLS);
        if (resultsEl) resultsEl.innerHTML = '<div class="error-box">No se pudo cargar la lista del servidor; usando herramientas de respaldo.</div>';
      });
  }

  function initApp() {
    fetch("/api/me")
      .then(function (r) { return r.json(); })
      .then(function (me) {
        if (!me || !me.auth) {
          window.location.href = "/login";
          return;
        }
        isAdmin = !!me.is_admin;
        renderStatus(me);
        if (me.proyecto_activo) {
          activeProyecto = { id: me.proyecto_activo.id, nombre: me.proyecto_activo.nombre, auto: !!me.proyecto_activo.auto };
        }
        bindProyectoBar();
        syncProyectoBar();
        fetchTools();
        refreshProyectoState();
      })
      .catch(function () {
        applyStaticFallback();
      });
  }

  function renderStatus(me) {
    if (statusEl && me.user) {
      statusEl.textContent = "Sistema operativo";
    }
    if (statusUserEl) {
      var rol = me.rol === "admin" ? "ADMIN" : "CLIENTE";
      statusUserEl.textContent = me.user + " (" + rol + ")";
      statusUserEl.style.display = "";
    }
    if (btnLogoutEl) {
      btnLogoutEl.style.display = "";
      btnLogoutEl.addEventListener("click", function () {
        fetch("/api/logout", { method: "POST" })
          .then(function () { window.location.href = "/login"; })
          .catch(function () { window.location.href = "/login"; });
      });
    }
  }

  function applyStaticFallback() {
    tools = FALLBACK_TOOLS;
    renderToolbar();
    setActive(tools[0] ? tools[0].id : null);
  }

  function submitSearch() {
    if (activeTool && activeTool.id === "admin") { loadAdminDashboard(); return; }
    if (activeTool && activeTool.id === "gps") { gpsSearch(); return; }
    if (activeTool && activeTool.id === "proyectos") { loadProjectDashboard(); return; }
    var q = queryEl.value.trim();
    if (!q || !activeTool) return;
    resultsEl.innerHTML = "";
    showLoading(true, "Buscando \u0022" + q + "\u0022 en " + (activeTool.nombre || activeTool.id) + "...");

    var body = { query: q };
    if (activeTool.id === "dorks") {
      body.tipo = extraTypeEl.value;
    }

    fetch("/api/search/" + activeTool.id, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, data: d }; });
      })
      .then(function (res) {
        try {
          if (!res.ok) {
            resultsEl.innerHTML = '<div class="error-box">' + esc(res.data.error || "Error en la búsqueda.") + "</div>";
            return;
          }
          renderResults(activeTool, res.data);
          maybeShowSaveButton(activeTool, res.data);
          if (activeProyecto && activeProyecto.auto && lastSummary) {
            saveResultToProject(activeProyecto.id, lastSummary, true);
          }
        } catch (err) {
          resultsEl.innerHTML = '<div class="error-box">Error al mostrar el resultado: ' + esc(err.message) + "</div>";
        } finally {
          showLoading(false);
        }
      })
      .catch(function (e) {
        showLoading(false);
        resultsEl.innerHTML = '<div class="error-box">Error de red: ' + esc(e.message) + "</div>";
      });
  }

  function gpsSearch() {
    if (!gpsTemplateEl || !gpsTemplateEl.value) {
      resultsEl.innerHTML = '<div class="error-box">Elegí un mensaje de la lista para generar el link.</div>';
      return;
    }
    var tplId = gpsTemplateEl.value;
    var nota = gpsNotaEl ? gpsNotaEl.value.trim() : "";
    var tplLabel = gpsTemplateEl.options[gpsTemplateEl.selectedIndex]
      ? gpsTemplateEl.options[gpsTemplateEl.selectedIndex].textContent : "";
    var body = { template_id: tplId, nota: nota };
    if (tplId === "personalizado") {
      var custom = gpsCustomMsgEl ? gpsCustomMsgEl.value.trim() : "";
      if (!custom) {
        resultsEl.innerHTML = '<div class="error-box">Escribí el mensaje personalizado antes de generar el link.</div>';
        return;
      }
      body.mensaje = custom;
      tplLabel = "Mensaje personalizado";
    }
    resultsEl.innerHTML = "";
    showLoading(true, "Generando link de localización...");

    fetch("/api/search/gps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        return r.json().then(function (d) { return { ok: r.ok, data: d }; });
      })
      .then(function (res) {
        try {
          if (!res.ok) {
            resultsEl.innerHTML = '<div class="error-box">' + esc(res.data.error || "Error al generar el link.") + "</div>";
            return;
          }
          res.data.templateLabel = tplLabel;
          lastGpsId = res.data.id;
          resultsEl.innerHTML = renderGps(res.data);
          gpsSig = "";
          loadGpsDashboard();
          bindGpsCopy();
          maybeShowSaveButton(activeTool, res.data);
          if (activeProyecto && activeProyecto.auto && lastSummary) {
            saveResultToProject(activeProyecto.id, lastSummary, true);
          }
        } catch (err) {
          resultsEl.innerHTML = '<div class="error-box">Error al mostrar: ' + esc(err.message) + "</div>";
        } finally {
          showLoading(false);
        }
      })
      .catch(function (e) {
        showLoading(false);
        resultsEl.innerHTML = '<div class="error-box">Error de red: ' + esc(e.message) + "</div>";
      });
  }

  function renderResults(tool, data) {
    var html = "";
    switch (tool.id) {
      case "email": html = renderEmail(data); break;
      case "usuario": html = renderUser(data); break;
      case "telefono": html = renderPhone(data); break;
      case "whois": html = renderWhois(data); break;
      case "cuit": html = renderCuit(data); break;
      case "ddjj": html = renderDdjj(data); break;
      case "dorks": html = renderDorks(data); break;
      case "ip": html = renderIp(data); break;
      case "subdominios": html = renderSubdomains(data); break;
      case "dns": html = renderDns(data); break;
      case "dni": html = renderDni(data); break;
      case "breach": html = renderBreach(data); break;
      case "empresa": html = renderEmpresa(data); break;
      case "gps": html = renderGps(data); break;
      default: html = '<div class="error-box">Tipo sin renderizador.</div>';
    }
    resultsEl.innerHTML = html;
    if (tool.id === "gps") {
      loadGpsDashboard();
      bindGpsCopy();
    }
  }

  function renderCard(title, badge, inner) {
    return '<div class="result-card"><h3>' + esc(title) + " " + (badge ? badge : "") + "</h3>" + inner + "</div>";
  }

  function renderEmail(d) {
    var html = "";
    html += renderCard("Email: " + d.email, '<span class="badge ok">holehe</span>', "");

    var found = (d.found || []).length;
    var rl = (d.rate_limited || []).length;
    var checked = (d.checked || []).length;
    var statusBadge = d.error ? '<span class="badge err">error</span>'
      : found ? '<span class="badge ok">' + found + " cuentas</span>"
      : '<span class="badge warn">sin resultados</span>';
    var inner = "";
    if (d.error) inner += '<div class="error-box">' + esc(d.error) + "</div>";
    if (checked) inner += '<p class="muted">Sitios analizados: ' + checked + (rl ? " | Rate-limit: " + rl + " (verificar manualmente)" : "") + "</p>";
    inner += (found ? rowsFromList(d.found.map(function (s) {
          return [s.name, s.exists ? "Cuenta detectada" : "No confirmada"];
        })) : '<p class="muted">No se detectaron cuentas asociadas al email. Los resultados dependen de que la plataforma exponga el estado del email.</p>');
    html += renderCard("Plataformas asociadas", statusBadge, inner);

    if (d.dorks && d.dorks.length) html += renderLinkList("Búsquedas complementarias (Google Dorks)", d.dorks);
    return html;
  }

  function rowsFromList(arr) {
    return "<table>" + arr.map(function (r) {
      return "<tr><td>" + esc(r[0]) + "</td><td>" + esc(r[1]) + "</td></tr>";
    }).join("") + "</table>";
  }

  function renderUser(d) {
    var html = "";
    var found = (d.found || []);
    var badge = d.error ? '<span class="badge err">error</span>'
      : found.length ? '<span class="badge ok">' + found.length + " plataformas</span>"
      : '<span class="badge warn">sin resultados</span>';

    html += renderCard("Usuario: " + d.username, badge, "");

    var inner = "";
    if (d.error) inner += '<div class="error-box">' + esc(d.error) + "</div>";
    if (!d.error && !found.length) inner += '<p class="muted">No se encontraron perfiles con ese nombre de usuario (o el servicio de sherlock no reportó coincidencias).</p>';

    if (found.length) {
      inner += '<div class="linklist">' + found.map(function (s) {
        return '<a href="' + esc(s.url) + '" target="_blank" rel="noopener"><span class="ln">' + esc(s.name) + '</span><span class="li">' + esc(s.info || "Perfil encontrado") + ' &#8599;</span></a>';
      }).join("") + "</div>";
    }
    html += renderCard("Perfiles detectados", badge, inner);

    if (d.dorks && d.dorks.length) html += renderLinkList("Búsquedas complementarias (Google Dorks)", d.dorks);
    return html;
  }

  function renderPhone(d) {
    var html = "";
    html += renderCard("Teléfono: " + d.number, '<span class="badge ok">phonenumbers</span>', "");

    var la = d.local_analysis;
    if (la && la.valid) {
      var rows = [
        ["E.164", la.e164],
        ["Internacional", la.international],
        ["Formato nacional", la.national],
        ["Código de país", la.country_code === undefined ? "-" : "+" + la.country_code],
        ["Número nacional", la.national_number],
        ["Región", la.region],
        ["Operador", la.carrier || "Sin datos"],
        ["Geolocalización", la.geolocation || "Sin datos"],
        ["Zonas horarias", (la.timezones || []).join(", ")]
      ];
      html += renderCard("Análisis local (sin API)", '<span class="badge ok">válido</span>', rowsFromList(rows));
    } else {
      html += renderCard("Análisis local (sin API)", '<span class="badge err">inválido</span>',
        '<div class="error-box">' + esc((la && la.error) || "Número inválido.") + "</div>");
    }

    if (d.phoneinfoga) {
      html += renderCard("phoneinfoga (avanzado)", '<span class="badge">CLI</span>',
        '<pre>' + esc(d.phoneinfoga.length > 2000 ? d.phoneinfoga.slice(0, 2000) + "..." : d.phoneinfoga) + "</pre>");
    }

    if (d.lookups && d.lookups.length) html += renderLinkList("Enlaces de búsqueda públicos", d.lookups);
    if (d.dorks && d.dorks.length) html += renderLinkList("Búsquedas complementarias (Google Dorks)", d.dorks);
    return html;
  }

  function renderWhois(d) {
    var html = "";
    html += renderCard("Dominio: " + d.domain, '<span class="badge ok">python-whois</span>', "");

    if (d.error) html += '<div class="error-box">' + esc(d.error) + "</div>";

    if (d.dns) {
      html += renderCard("Resolución DNS", '<span class="badge ok">IP</span>',
        '<table><tr><th>Dominio</th><td>' + esc(d.domain) + '</td></tr><tr><th>IP</th><td>' + esc(d.dns.ip) + "</td></tr></table>");
    }

    if (d.whois) {
      var rows = [];
      ["domain_name", "registrar", "creation_date", "expiration_date", "updated_date",
       "status", "name_servers", "org", "registrant_name", "registrant_organization",
       "registrant_country", "admin_name", "admin_email", "emails"
      ].forEach(function (k) {
        var v = d.whois[k];
        if (v == null) return;
        if (Array.isArray(v)) v = v.join(", ");
        if (k === "emails") return;
        rows.push([k.toUpperCase().replace(/_/g, " "), v]);
      });
      if (rows.length) html += renderCard("Registro Whois", '<span class="badge ok">datos</span>', rowsFromList(rows));
      else if (d.raw_text) html += renderCard("Registro Whois", '<span class="badge ok">datos</span>', '<pre style="white-space:pre-wrap;font-size:12px">' + esc(d.raw_text.slice(0, 4000)) + "</pre>");
      else html += '<p class="muted">No se pudieron extraer campos del registro whois.</p>';
    }

    if (d.dorks && d.dorks.length) html += renderLinkList("Búsquedas complementarias", d.dorks);
    return html;
  }

  function renderCuit(d) {
    var html = "";
    if (d.error) {
      html += '<div class="error-box">' + esc(d.error) + "</div>";
      return html;
    }
    var info = d.info || {};
    html += renderCard("CUIT/CUIL válido: " + info.formateado, '<span class="badge ok">válido</span>', rowsFromList([
      ["Prefijo", info.prefijo],
      ["Tipo", info.tipo],
      ["DNI / Base", info.dni],
      ["Dígito verificador", info.digito_verificador]
    ]));

    if (d.links && d.links.length) html += renderLinkList("Consultas oficiales y enlaces", d.links);
    return html;
  }

  function renderDdjj(d) {
    var html = "";
    html += renderCard("Declaraciones Juradas" + (d.persona ? " - " + d.persona : ""), '<span class="badge ok">datos abiertos</span>', "");

    if (d.error) html += '<div class="error-box">' + esc(d.error) + "</div>";
    if (d.portales && d.portales.length) html += renderLinkList("Portales oficiales", d.portales);
    if (d.busquedas && d.busquedas.length) html += renderLinkList("Búsquedas del nombre", d.busquedas);

    if (d.datasets && d.datasets.length) {
      var inner = "";
      d.datasets.forEach(function (ds) {
        inner += "<h4 style='margin:12px 0 6px'>" + esc(ds.title) + " <span class='muted'>(from " + esc(ds.origin) + ")</span></h4>";
        inner += '<p class="muted">' + esc(ds.description || "") + "</p>";
        if (ds.resources && ds.resources.length) {
          inner += '<div class="linklist">' + ds.resources.map(function (r) {
            return '<a href="' + esc(r.url) + '" target="_blank" rel="noopener"><span class="ln">' + esc(r.name) + ' (' + esc(r.format || "?") + ')</span><span class="li">Descargar &#8599;</span></a>';
          }).join("") + "</div>";
        }
      });
      html += renderCard("Datasets de datos abiertos", '<span class="badge">CKAN</span>', inner);
    } else {
      html += '<p class="muted">No se pudieron recuperar datasets ahora; los portales oficiales siguen disponibles arriba.</p>';
    }
    return html;
  }

  function renderDorks(d) {
    var html = "";
    var badge = d.tipo ? '<span class="badge">' + esc(d.tipo) + "</span>" : "";
    html += renderCard("Dorks para: " + d.target, badge, "");
    if (d.dorks && d.dorks.length) {
      html += renderLinkList("Búsquedas generadas", d.dorks);
    } else {
      html += '<p class="muted">Sin dorks para este tipo.</p>';
    }
    return html;
  }

  function renderIp(d) {
    var html = "";
    if (d.error) return '<div class="error-box">' + esc(d.error) + "</div>";
    html += renderCard("IP: " + d.ip, '<span class="badge ok">whois+geo</span>', "");

    var rows = [["Reverse DNS", d.reverse_dns || "No resuelto"]];
    html += renderCard("Reverse DNS", '<span class="badge">PTR</span>', rowsFromList(rows));

    if (d.whois && !d.whois.error) {
      var w = d.whois;
      var wrows = [
        ["ASN", w.asn],
        ["Registro AS", w.asn_registry],
        ["Proveedor / Descripción", w.asn_description],
        ["País (AS)", w.asn_country_code]
      ];
      var net = w.network;
      if (net && typeof net === "object") {
        wrows.push(["Rango de red", net.cidr && (net.cidr[0] || "")]);
        wrows.push(["Nombre del bloque", net.name]);
        wrows.push(["Org/Holder", net.handle || net.name]);
        wrows.push(["Tipo", net.type]);
        wrows.push(["Autónomo", net.parent]);
      }
      html += renderCard("WHOIS de la IP", '<span class="badge">RDAP</span>', rowsFromList(wrows));
    } else if (d.whois && d.whois.error) {
      html += renderCard("WHOIS de la IP", '<span class="badge err">no disp</span>', '<div class="error-box">' + esc(d.whois.error) + "</div>");
    }

    if (d.whois_text && d.whois_text.length) {
      html += renderCard("Detalle WHOIS (texto)", '<span class="badge">whois</span>', rowsFromList(d.whois_text.map(function (r) {
        return [r.field, r.value];
      })));
    }

    if (d.abuse && d.abuse.length) html += renderLinkList("Reputación y abuso de la IP", d.abuse);
    return html;
  }

  function renderSubdomains(d) {
    var html = "";
    if (d.error) return '<div class="error-box">' + esc(d.error) + "</div>";
    if (d.warning) html += '<div class="error-box">' + esc(d.warning) + "</div>";
    if (d.warning_sublist3r && !d.subdomains.length) html += '<p class="muted">' + esc(d.warning_sublist3r) + "</p>";

    var subs = d.subdomains || [];
    html += renderCard("Subdominios de: " + d.domain,
      '<span class="badge ok">' + subs.length + " encontrados</span>",
      subs.length
        ? '<div class="kv">' + subs.map(function (s) {
            return '<span><a href="https://' + esc(s) + '" target="_blank" rel="noopener">' + esc(s) + ' &#8599;</a></span>';
          }).join("") + "</div>"
        : '<p class="muted">No se encontraron subdominios.</p>'
    );
    return html;
  }

  function renderDns(d) {
    var html = "";
    if (d.error) html += '<div class="error-box">' + esc(d.error) + "</div>";
    html += renderCard("Registros DNS de: " + d.domain, '<span class="badge ok">dnspython</span>', "");
    if (d.ip) html += '<p class="muted">IP principal: ' + esc(d.ip) + "</p>";

    var order = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SPF"];
    var inner = "";
    order.forEach(function (k) {
      var rec = d.records && d.records[k];
      if (rec == null) return;
      var val;
      if (Array.isArray(rec)) {
        val = rec.length ? rec.join("<br>") : "(sin registros)";
      } else if (rec && rec.error) {
        val = "Error: " + esc(rec.error);
      } else {
        val = esc(String(rec));
      }
      inner += '<div style="margin-bottom:8px"><strong style="color:var(--accent)">' + k + ":</strong> " + val + "</div>";
    });
    html += renderCard("Registros", "", inner || '<p class="muted">Sin registros.</p>');
    return html;
  }

  function renderDni(d) {
    var html = "";
    if (d.error) return '<div class="error-box">' + esc(d.error) + "</div>";
    html += renderCard("DNI válido: " + d.dni, '<span class="badge ok">documento</span>', "");
    if (d.links && d.links.length) {
      html += renderLinkList("Consultas de identidad", d.links.filter(function (l) { return l.url; }));
      var notas = d.links.filter(function (l) { return !l.url; });
      if (notas.length) html += renderCard("Notas", "", notas.map(function (n) { return "<div class='muted'>" + esc(n.info) + "</div>"; }).join(""));
    }
    return html;
  }

  function renderBreach(d) {
    var html = "";
    if (d.error) return '<div class="error-box">' + esc(d.error) + "</div>";
    html += renderCard("Filtraciones para: " + d.query, '<span class="badge ok">leaks</span>', "");
    if (d.links && d.links.length) html += renderLinkList("Motores de búsqueda de brechas", d.links);
    return html;
  }

  function renderEmpresa(d) {
    var html = "";
    if (d.error) return '<div class="error-box">' + esc(d.error) + "</div>";
    html += renderCard("Empresa / Entidad: " + d.query, '<span class="badge ok">empresa AR</span>', "");
    if (d.links && d.links.length) html += renderLinkList("Consultas oficiales y registros", d.links);
    return html;
  }

  function loadAdminDashboard() {
    var holder = document.getElementById("admin-dash");
    if (!holder) return;
    holder.innerHTML = '<p class="muted">Cargando panel de administración...</p>';

    Promise.all([
      fetch("/api/admin/stats").then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/admin/licenses").then(function (r) { return r.json(); }).catch(function () { return { licenses: [] }; }),
      fetch("/api/admin/email-config").then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/admin/notificaciones").then(function (r) { return r.json(); }).catch(function () { return []; })
    ]).then(function (res) {
      var stats = res[0] || {};
      var licenses = (res[1] && res[1].licenses) || [];
      var emailCfg = res[2] || {};
      var logs = res[3] || [];
      var html = "";

      html += renderCard("Licencias", "",
        '<div class="kv">' +
          '<span>Disponibles: <b>' + esc(String(stats.disponibles == null ? "-" : stats.disponibles)) + '</b></span>' +
          '<span>Asignadas: <b>' + esc(String(stats.asignadas == null ? "-" : stats.asignadas)) + '</b></span>' +
          '<span>Revocadas: <b>' + esc(String(stats.revocadas == null ? "-" : stats.revocadas)) + '</b></span>' +
          '<span>Total: <b>' + esc(String(stats.total == null ? "-" : stats.total)) + '</b></span>' +
        '</div>'
      );

      html += renderCard("Generar licencia disponible", "",
        '<div class="search-box">' +
          '<input type="text" id="licVersion" placeholder="Versión (ej. v1.0 - clientes)">' +
          '<input type="text" id="licNotas" placeholder="Notas (opcional)">' +
          '<button class="mini-btn" id="licGenBtn">Generar</button>' +
        '</div>'
      );

      html += renderCard("Registro de licencias (" + licenses.length + ")", "",
        licenses.length
          ? '<table><thead><tr><th>Clave</th><th>Usuario</th><th>Email</th><th>Versión</th><th>Estado</th><th>Asignada</th><th>Acciones</th></tr></thead><tbody>' +
            licenses.map(licRow).join("") + "</tbody></table>"
          : '<p class="muted">No hay licencias.</p>'
      );

      var destTxt = emailCfg.to || "martinf@mftechar.com";
      html += renderCard("Email de notificaciones (destino: " + esc(destTxt) + ")", "",
        '<div class="search-box">' +
          '<input type="text" id="cfgHost" placeholder="Servidor SMTP" value="' + esc(emailCfg.smtp_host || "") + '">' +
          '<input type="text" id="cfgPort" placeholder="Puerto" value="' + esc(String(emailCfg.smtp_port || "")) + '" style="flex:0 0 80px">' +
          '<input type="text" id="cfgUser" placeholder="Usuario SMTP" value="' + esc(emailCfg.smtp_user || "") + '">' +
          '<input type="password" id="cfgPass" placeholder="Contraseña SMTP" value="' + esc(emailCfg.smtp_pass || "") + '">' +
          '<input type="text" id="cfgFrom" placeholder="Remitente" value="' + esc(emailCfg.smtp_from || "") + '" style="flex:0 0 220px">' +
          '<input type="text" id="cfgTo" placeholder="Destino" value="' + esc(emailCfg.to || "martinf@mftechar.com") + '" style="flex:0 0 200px">' +
        '</div>' +
        '<div class="send-row">' +
          '<label class="muted" style="padding:10px 0"><input type="checkbox" id="cfgEnabled" ' + (emailCfg.enabled ? "checked" : "") + '> Email habilitado</label>' +
          '<button class="mini-btn" id="cfgSaveBtn">Guardar config</button>' +
          '<button class="mini-btn" id="cfgTestBtn">Probar envío</button>' +
          '<button class="mini-btn" id="cfgNoteBtn">Enviar aviso manual</button>' +
        '</div>' +
        '<p class="muted">Las notificaciones (asignación, recuperación de acceso, aviso de problemas, revocación) se envían al destino configurado (por defecto martinf@mftechar.com) y quedan registradas aunque el SMTP no esté configurado.</p>'
      );

      if (logs.length) {
        html += renderCard("Historial de notificaciones", "",
          '<table><thead><tr><th>Fecha</th><th>Tipo</th><th>Asunto</th><th>Destino</th><th>Estado</th></tr></thead><tbody>' +
          logs.slice(0, 40).map(function (n) {
            var ok = n.ok ? '<span class="badge ok">enviado</span>'
              : '<span class="badge warn">' + esc(n.error || "no enviado") + '</span>';
            return "<tr><td>" + esc(n.fecha) + "</td><td>" + esc(n.tipo) + "</td><td>" + esc(n.asunto) + "</td><td>" + esc(n.destino) + "</td><td>" + ok + "</td></tr>";
          }).join("") + "</tbody></table>"
        );
      }

      holder.innerHTML = html;
      bindAdminActions();
    });
  }

  function licRow(l) {
    var estado = l.estado === "asignada" ? '<span class="badge ok">asignada</span>'
      : l.estado === "revocada" ? '<span class="badge err">revocada</span>'
      : '<span class="badge warn">disponible</span>';
    var acciones = "";
    if (l.estado === "disponible") {
      acciones += '<button class="mini-btn" data-act="asignar" data-id="' + esc(l.id) + '">Asignar</button> ';
    } else if (l.estado === "asignada") {
      acciones += '<button class="mini-btn" data-act="emitir" data-id="' + esc(l.id) + '">Emitir licencia</button> ';
      acciones += '<button class="mini-btn" data-act="recuperar" data-id="' + esc(l.id) + '">Recuperar</button> ';
      acciones += '<button class="mini-btn del" data-act="revocar" data-id="' + esc(l.id) + '">Revocar</button>';
    }
    return "<tr><td>" + esc(l.clave) + "</td><td>" + esc(l.usuario || "-") + "</td><td>" + esc(l.email || "-") + "</td><td>" + esc(l.version || "-") + "</td><td>" + estado + "</td><td>" + esc(l.fecha_asignacion || "-") + "</td><td>" + acciones + "</td></tr>";
  }

  function bindAdminActions() {
    var holder = document.getElementById("admin-dash");
    if (!holder) return;

    var genBtn = document.getElementById("licGenBtn");
    if (genBtn) {
      genBtn.addEventListener("click", function () {
        var version = (document.getElementById("licVersion") || { value: "" }).value || "";
        var notas = (document.getElementById("licNotas") || { value: "" }).value || "";
        apiPost("/api/admin/licenses", { version: version, notas: notas }, function () {
          loadAdminDashboard();
        }, "Error al generar la licencia.");
      });
    }

    holder.querySelectorAll("[data-act]").forEach(function (b) {
      b.addEventListener("click", function () {
        var act = b.dataset.act;
        var id = b.dataset.id;
        if (act === "asignar") {
          var usuario = window.prompt("Usuario / cliente:");
          if (usuario == null) return;
          var email = window.prompt("Email asociado a la licencia:");
          if (email == null) return;
          var version = window.prompt("Versión (ej. v1.0 - clientes):", "v1.0");
          if (version == null) return;
          apiPost("/api/admin/licenses/" + encodeURIComponent(id) + "/asignar",
            { usuario: usuario, email: email, version: version },
            function (d) {
              var e = d && d.email;
              window.alert(e && e.ok ? "Licencia asignada y email enviado/registrado." : "Licencia asignada (registrada). Email: " + ((e && e.error) || "no enviado"));
              loadAdminDashboard();
            }, "Error al asignar.");
        } else if (act === "emitir") {
          var maquina = window.prompt("Código de la PC del cliente (vacío = máquina libre):");
          if (maquina == null) return;
          var expira = window.prompt("Vencimiento YYYY-MM-DD (vacío = sin vencimiento):");
          if (expira == null) return;
          apiPost("/api/admin/emitir", { pool_id: id, maquina: maquina.trim(), expira: expira.trim() },
            function (d) {
              window.alert("Archivo firmado generado en data/licencia.rel (cliente: " + (d.payload.usuario || "") + "). Copialo a la carpeta data del cliente.");
              loadAdminDashboard();
            }, "No se pudo emitir: comprobá que la licencia esté asignada y que el servidor sea la maestra.");
        } else if (act === "recuperar") {
          if (!window.confirm("Enviar email de recuperación de acceso al administrador y al email del cliente?")) return;
          apiPost("/api/admin/licenses/" + encodeURIComponent(id) + "/recuperar", {},
            function (d) {
              var e = d && d.email;
              window.alert(e && e.ok ? "Email de recuperación enviado y registrado." : "Email de recuperación registrado (" + ((e && e.error) || "SMTP no configurado") + ").");
              loadAdminDashboard();
            }, "Error.");
        } else if (act === "revocar") {
          if (!window.confirm("¿Revocar esta licencia? La clave dejará de ser válida.")) return;
          apiPost("/api/admin/licenses/" + encodeURIComponent(id) + "/revocar", {},
            function () { loadAdminDashboard(); }, "Error al revocar.");
        }
      });
    });

    var saveBtn = document.getElementById("cfgSaveBtn");
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        apiPost("/api/admin/email-config", readEmailCfg(), function () {
          window.alert("Configuración guardada.");
        }, "Error al guardar la configuración.");
      });
    }
    var testBtn = document.getElementById("cfgTestBtn");
    if (testBtn) {
      testBtn.addEventListener("click", function () {
        var cfg = readEmailCfg();
        cfg.temporal = true;
        apiPost("/api/admin/email-test", cfg, function (d) {
          window.alert(d && d.ok ? "Email de prueba enviado a " + esc(d.destino || "el destino configurado")
            : "Falló el envío: " + ((d && d.error) || "desconocido"));
        }, "Error.");
      });
    }
    var noteBtn = document.getElementById("cfgNoteBtn");
    if (noteBtn) {
      noteBtn.addEventListener("click", function () {
        var mensaje = window.prompt("Mensaje de aviso (ej. problema con un cliente):");
        if (mensaje == null || !mensaje.trim()) return;
        apiPost("/api/admin/email", { tipo: "aviso manual", mensaje: mensaje },
          function (d) {
            var e = d && d.email;
            window.alert(e && e.ok ? "Aviso enviado y registrado." : "Aviso registrado (" + ((e && e.error) || "SMTP no configurado") + ").");
          }, "Error.");
      });
    }
  }

  function readEmailCfg() {
    function v(id) { var el = document.getElementById(id); return el ? el.value : ""; }
    return {
      enabled: document.getElementById("cfgEnabled") ? document.getElementById("cfgEnabled").checked : false,
      smtp_host: v("cfgHost"),
      smtp_port: parseInt(v("cfgPort") || "587", 10) || 587,
      smtp_user: v("cfgUser"),
      smtp_pass: v("cfgPass"),
      smtp_from: v("cfgFrom"),
      to: v("cfgTo") || "martinf@mftechar.com"
    };
  }

  function apiPost(url, body, onOk, errMsg) {
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    }).then(function (res) {
      if (!res.ok) {
        window.alert((res.data && res.data.error) || errMsg || "Error.");
        return;
      }
      onOk(res.data);
    }).catch(function () {
      window.alert("Error de red.");
    });
  }

  function renderGps(data) {
    var html = "";
    var notaTxt = data.nota ? ' &middot; Nota: ' + esc(data.nota) : "";
    html += renderCard("Link de localización generado", '<span id="gpsEstado" class="badge ' + (data.estado === "recibida" ? "ok" : "warn") + '">' + esc(data.estado) + "</span>",
      '<p class="muted">Mensaje elegido: <strong>' + esc(data.template || data.templateLabel || "") + "</strong>" +
      notaTxt + ". La persona debe abrir el link y tocar el botón verde para que se envíe su ubicación (una sola vez, con su consentimiento).</p>" +
      '<p id="gpsRecibida" style="display:none" class="muted">La persona compartió su ubicación: <a id="gpsMapsLink" href="#" target="_blank" rel="noopener">Ver en Google Maps &#8599;</a></p>'
    );

    var inner = "";
    inner += '<p class="muted">Mensaje listo para enviar (el link va al final). Copialo o mandalo directo desde una red:</p>';
    inner += '<textarea id="gpsMsg" readonly rows="5">' + esc(data.mensaje) + "</textarea>";
    inner += '<div class="link-send">';
    inner += '<button id="gpsCopyMsg" class="mini-btn">Copiar mensaje</button>';
    inner += "</div>";

    inner += '<div class="send-row">' +
      '<a href="' + esc(data.whatsapp) + '" target="_blank" rel="noopener" class="send-btn wa">WhatsApp</a>' +
      '<a href="' + esc(data.telegram) + '" target="_blank" rel="noopener" class="send-btn tg">Telegram</a>' +
      '<a href="' + esc(data.mailto) + '" class="send-btn em">Correo</a>' +
      "</div>";
    inner += '<p class="muted">WhatsApp y Correo abren con el mensaje completo ya escrito (solo elegís el contacto). Telegram compone el texto y el link en su ventana de compartir.</p>';

    inner += '<p class="muted" style="margin-top:14px">Link directo (si lo preferís suelto):</p>';
    inner += '<div class="link-send">';
    inner += '<input id="gpsLink" readonly value="' + esc(data.link) + '" onclick="this.select()">';
    inner += '<button id="gpsCopy" class="mini-btn">Copiar link</button>';
    inner += "</div>";

    html += renderCard("Mensaje a enviar", "", inner);
    html += '<div id="gps-dashboard"></div>';
    return html;
  }

  function bindGpsCopy() {
    var copyMsgBtn = document.getElementById("gpsCopyMsg");
    if (copyMsgBtn) {
      copyMsgBtn.addEventListener("click", function () {
        var msgEl = document.getElementById("gpsMsg");
        if (!msgEl) return;
        copyText(msgEl.value, copyMsgBtn, "¡Copiado!");
      });
    }
    var copyLinkBtn = document.getElementById("gpsCopy");
    if (copyLinkBtn) {
      copyLinkBtn.addEventListener("click", function () {
        var linkEl = document.getElementById("gpsLink");
        if (!linkEl) return;
        copyText(linkEl.value, copyLinkBtn, "¡Copiado!");
      });
    }
  }

  function copyText(text, btn, doneText) {
    if (!btn.dataset.origLabel) btn.dataset.origLabel = btn.textContent;
    var restore = function () {
      btn.textContent = btn.dataset.origLabel;
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = doneText;
        setTimeout(restore, 1500);
      }).catch(function () {});
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        btn.textContent = doneText;
        setTimeout(restore, 1500);
      } catch (e) {}
      document.body.removeChild(ta);
    }
  }

  function loadGpsDashboard() {
    var holder = document.getElementById("gps-dashboard");
    if (!holder) return;
    holder.innerHTML = '<p class="muted">Cargando estado del túnel y enlaces...</p>';

    Promise.all([
      fetch("/api/gps/tunnel").then(function (r) { return r.json(); }).catch(function () { return {}; }),
      fetch("/api/gps/links").then(function (r) { return r.json(); }).catch(function () { return { records: [] }; })
    ]).then(function (res) {
      var tunnel = res[0] || {};
      var records = (res[1] && res[1].records) || [];
      var html = "";

      var sig = JSON.stringify({ t: tunnel.url || null, r: records });
      syncGpsBadge(records);
      if (sig === gpsSig) return;
      gpsSig = sig;

      if (tunnel.url) {
        html += renderCard("Túnel público (HTTPS)", '<span class="badge ok">activo</span>',
          '<p class="muted">Los links nuevos usan esta URL pública. La persona puede abrirlos desde cualquier lugar con internet.</p>' +
          '<div class="kv"><span>' + esc(tunnel.url) + '</span></div>');
      } else {
        html += renderCard("Túnel público (HTTPS)", '<span class="badge warn">sin túnel</span>',
          '<p class="muted">No hay túnel activo (revisá internet). Los links funcionan solo dentro de esta red local y la geolocalización puede estar bloqueada por HTTPS.</p>');
      }

      if (records.length) {
        var rows = records.map(function (r) {
          var estado = r.estado === "recibida"
            ? '<span class="badge ok">¡Recibida!</span>'
            : '<span class="badge warn">pendiente</span>';
          var etiqueta = r.nota || r.numero || "Sin etiqueta";
          var coords = "";
          if (r.maps) {
            coords = '<a href="' + esc(r.maps) + '" target="_blank" rel="noopener">Ver en Google Maps &#8599;</a>';
            var acc = r.accuracy ? " (" + Math.round(r.accuracy) + " m aprox.)" : "";
            coords += "<br>Precisión" + acc;
          } else {
            coords = "Sin coordenadas aún";
          }
          return "<tr><td>" + esc(etiqueta) + "<br><span class='muted'>" + esc(r.creado) + "</span></td>" +
            "<td>" + estado + "</td><td>" + coords + "</td>" +
            "<td><button class='mini-btn del' data-token='" + esc(r.id) + "'>Borrar</button></td></tr>";
        }).join("");
        html += renderCard("Enlaces generados (" + records.length + ")", "", "<table><thead><tr><th>Etiqueta</th><th>Estado</th><th>Ubicación</th><th>Acción</th></tr></thead><tbody>" + rows + "</tbody></table>");
      } else {
        html += renderCard("Enlaces generados", "", '<p class="muted">Aún no hay enlaces. Elegí un mensaje arriba y toca Buscar para generar el primero.</p>');
      }
      holder.innerHTML = html;

      holder.querySelectorAll(".del").forEach(function (b) {
        b.addEventListener("click", function () {
          var token = b.dataset.token;
          if (!window.confirm("¿Eliminar esta petición del panel?")) return;
          fetch("/api/gps/links/" + encodeURIComponent(token), { method: "DELETE" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (d.ok) {
                gpsSig = "";
                loadGpsDashboard();
              }
              else window.alert("No se pudo eliminar: " + (d.error || "desconocido"));
            })
            .catch(function () { window.alert("Error de red al eliminar."); });
        });
      });
    });
  }

  function syncGpsBadge(records) {
    if (!lastGpsId) return;
    var badge = document.getElementById("gpsEstado");
    if (!badge) return;
    var rec = null;
    for (var i = 0; i < records.length; i++) {
      if (records[i].id === lastGpsId) { rec = records[i]; break; }
    }
    if (!rec) return;
    var nuevo = rec.estado || "pendiente";
    if (badge.textContent !== nuevo) {
      badge.textContent = nuevo;
      badge.className = "badge " + (nuevo === "recibida" ? "ok" : "warn");
    }
    if (nuevo === "recibida" && rec.maps) {
      var recP = document.getElementById("gpsRecibida");
      var mapsA = document.getElementById("gpsMapsLink");
      if (mapsA) mapsA.href = rec.maps;
      if (recP) recP.style.display = "block";
    }
  }

  function renderLinkList(title, links) {
    var inner = '<div class="linklist">' + links.map(function (l) {
      return '<a href="' + esc(l.url) + '" target="_blank" rel="noopener">' +
        '<span class="ln">' + esc(l.name || l.key || l.title || "Enlace") + '</span>' +
        (l.info ? '<span class="li">' + esc(l.info) + " &#8599;</span>" : '<span class="li">Abrir &#8599;</span>') +
        "</a>";
    }).join("") + "</div>";
    return renderCard(title || "Enlaces", "", inner);
  }

  /* ---------------- Proyectos de investigación ---------------- */

  function summarizeResult(tool, data) {
    if (!data) return null;
    var t = tool.id;
    var out = { tool: t, toolNombre: tool.nombre || t, objetivo: "", lineas: [], links: [], detalle: "" };
    var fin = (data.found || []);
    var w = data.whois || {};
    var dks = (data.dorks || []).map(function (d) {
      return { name: (d && (d.name || d.title)) || ((d && d.url) || ""), url: (d && d.url) || "" };
    });
    switch (t) {
      case "email":
        out.objetivo = data.email || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.lineas.push("Sitios analizados: " + ((data.checked || []).length));
        out.lineas.push("Cuentas detectadas: " + fin.length);
        fin.forEach(function (s) { out.lineas.push("- " + s.name + " (" + (s.exists ? "cuenta detectada" : "sin confirmar") + ")"); });
        (data.rate_limited || []).forEach(function (s) { out.lineas.push("- " + s.name + " (rate limit, verificar manualmente)"); });
        out.links = dks;
        break;
      case "usuario":
        out.objetivo = data.username || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.lineas.push("Perfiles encontrados: " + fin.length);
        fin.forEach(function (s) { out.lineas.push("- " + s.name); });
        out.links = fin.map(function (s) { return { name: s.name, url: s.url }; }).concat(dks);
        break;
      case "telefono":
        out.objetivo = data.number || "";
        var la = data.local_analysis || {};
        if (la && la.valid) {
          out.lineas.push("E.164: " + (la.e164 || ""));
          out.lineas.push("Internacional: " + (la.international || ""));
          out.lineas.push("Nacional: " + (la.national || ""));
          out.lineas.push("Región: " + (la.region || ""));
          out.lineas.push("Operador: " + (la.carrier || "Sin datos"));
          out.lineas.push("Geolocalización: " + (la.geolocation || "Sin datos"));
        } else {
          out.lineas.push((la && la.error) || "Número inválido.");
        }
        out.links = (data.lookups || []).concat(dks);
        if (data.phoneinfoga && data.phoneinfoga.indexOf("no está instalado") === -1) {
          out.detalle = "phoneinfoga:\n" + String(data.phoneinfoga).slice(0, 2000);
        }
        break;
      case "whois":
        out.objetivo = data.domain || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        if (data.dns) out.lineas.push("IP: " + data.dns.ip);
        ["registrar", "creation_date", "expiration_date", "updated_date", "status", "name_servers",
         "org", "registrant_name", "registrant_organization", "registrant_country", "admin_name", "admin_email"
        ].forEach(function (k) {
          var v = w[k];
          if (v == null) return;
          if (Array.isArray(v)) v = v.join(", ");
          out.lineas.push(k.toUpperCase().replace(/_/g, " ") + ": " + v);
        });
        if (data.raw_text) out.detalle = data.raw_text.slice(0, 1500);
        out.links = dks;
        break;
      case "cuit":
        var info = data.info || {};
        out.objetivo = info.formateado || data.raw || "";
        out.lineas.push("Prefijo: " + (info.prefijo || ""));
        out.lineas.push("Tipo: " + (info.tipo || ""));
        out.lineas.push("DNI / Base: " + (info.dni || ""));
        out.lineas.push("Dígito verificador: " + (info.digito_verificador || ""));
        out.links = (data.links || []).slice(0, 20);
        break;
      case "ddjj":
        out.objetivo = data.persona || "DDJJ";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.lineas.push("Portales oficiales: " + ((data.portales || []).length));
        (data.datasets || []).forEach(function (ds) {
          out.lineas.push("- Dataset: " + (ds.title || ""));
          if (ds.resources && ds.resources.length) {
            out.links.push({ name: (ds.title || "recurso") + " (" + (ds.resources[0].format || "?") + ")", url: ds.resources[0].url });
          }
        });
        out.links = out.links.concat(data.portales || []).concat(data.busquedas || []);
        break;
      case "dorks":
        out.objetivo = data.target || "";
        out.lineas.push("Tipo: " + (data.tipo || ""));
        (data.dorks || []).forEach(function (d) {
          out.lineas.push("- " + ((d && (d.name || d.title)) || ((d && d.url) || "")));
        });
        out.links = data.dorks || [];
        break;
      case "ip":
        out.objetivo = data.ip || "";
        if (data.error) { out.lineas.push("Error: " + data.error); break; }
        out.lineas.push("Reverse DNS: " + (data.reverse_dns || "No resuelto"));
        out.lineas.push("ASN: " + (w.asn || "-"));
        out.lineas.push("Descripción: " + (w.asn_description || "-"));
        out.lineas.push("País: " + (w.asn_country_code || "-"));
        if (w.network && typeof w.network === "object") {
          out.lineas.push("Rango: " + ((w.network.cidr && w.network.cidr[0]) || ""));
          out.lineas.push("Org: " + (w.network.name || w.network.handle || ""));
        }
        if (data.whois_text && data.whois_text.length) {
          out.detalle = data.whois_text.map(function (r) { return r.field + ": " + r.value; }).join("\n").slice(0, 1500);
        }
        out.links = data.abuse || [];
        break;
      case "subdominios":
        out.objetivo = data.domain || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        if (data.warning) out.lineas.push("Aviso: " + data.warning);
        (data.subdomains || []).slice(0, 120).forEach(function (s) { out.lineas.push("- " + s); });
        break;
      case "dns":
        out.objetivo = data.domain || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        if (data.ip) out.lineas.push("IP principal: " + data.ip);
        ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SPF"].forEach(function (k) {
          var rec = data.records && data.records[k];
          if (rec == null) return;
          if (Array.isArray(rec)) out.lineas.push(k + ": " + rec.join(", "));
          else if (rec && rec.error) out.lineas.push(k + ": error " + rec.error);
          else out.lineas.push(k + ": " + String(rec));
        });
        break;
      case "dni":
        out.objetivo = data.dni || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.links = (data.links || []).filter(function (l) { return l && l.url; });
        break;
      case "breach":
        out.objetivo = data.query || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.links = data.links || [];
        break;
      case "empresa":
        out.objetivo = data.query || "";
        if (data.error) out.lineas.push("Error: " + data.error);
        out.links = data.links || [];
        break;
      case "gps":
        out.objetivo = data.nota || data.template || data.templateLabel || "Localización";
        out.lineas.push("Tipo: Localización GPS");
        out.lineas.push("Estado: " + (data.estado || "pendiente"));
        out.lineas.push("Mensaje: " + String(data.mensaje || "").slice(0, 300));
        if (data.link) out.links.push({ name: "Link de localización", url: data.link });
        break;
      default:
        out.objetivo = data.query || data.objetivo || "";
        out.lineas = out.lineas.concat([String(data).slice(0, 800)]);
    }
    out.lineas = out.lineas.slice(0, 120);
    out.links = out.links.slice(0, 60);
    return out;
  }

  function saveResultToProject(rid, summary, auto) {
    if (!rid || !summary) return false;
    var body = {
      tool: summary.tool, toolNombre: summary.toolNombre, objetivo: summary.objetivo,
      resumen: summary.lineas, links: summary.links, detalle: summary.detalle, auto: !!auto
    };
    fetch("/api/proyectos/" + encodeURIComponent(rid) + "/guardar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    }).then(function (res) {
      if (!res.ok) return;
      var hint = document.getElementById("saveProjHint");
      if (hint) hint.textContent = auto ? "Guardado automáticamente en el proyecto." : "Guardado en el proyecto.";
      refreshProyectoState();
    }).catch(function () {});
    return true;
  }

  function maybeShowSaveButton(tool, data) {
    if (!activeProyecto) return;
    if (tool.id === "proyectos" || tool.id === "admin") return;
    if (resultsEl.querySelector(".save-row")) return;
    lastSummary = summarizeResult(tool, data);
    if (!lastSummary) return;
    var row = document.createElement("div");
    row.className = "save-row";
    row.innerHTML = '<button class="mini-btn" id="btnSaveProj">Guardar al proyecto: ' + esc(activeProyecto.nombre) + '</button> <span id="saveProjHint"></span>';
    resultsEl.insertBefore(row, resultsEl.firstChild);
    var btn = document.getElementById("btnSaveProj");
    if (btn) {
      btn.addEventListener("click", function () {
        if (!activeProyecto) {
          window.alert("Primero activá o creá un proyecto desde la pestaña Proyectos.");
          return;
        }
        if (!lastSummary) return;
        var hint = document.getElementById("saveProjHint");
        if (hint) hint.textContent = "Guardando...";
        saveResultToProject(activeProyecto.id, lastSummary, false);
      });
    }
  }

  function refreshProyectoState() {
    fetch("/api/proyectos")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var list = (d && d.proyectos) || [];
        var act = null;
        for (var i = 0; i < list.length; i++) {
          if (list[i].activo) { act = list[i]; break; }
        }
        activeProyecto = act ? { id: act.id, nombre: act.nombre, auto: !!act.auto } : null;
        syncProyectoBar();
      })
      .catch(function () {});
  }

  function syncProyectoBar() {
    if (!proyectoBarEl) return;
    if (!activeProyecto) {
      proyectoBarEl.style.display = "none";
      return;
    }
    proyectoBarEl.style.display = "";
    var bn = document.getElementById("projBarName");
    if (bn) bn.textContent = activeProyecto.nombre;
    var cb = document.getElementById("projAuto");
    if (cb) cb.checked = !!activeProyecto.auto;
  }

  function bindProyectoBar() {
    if (!proyectoBarEl || proyectoBarEl.dataset.bound) return;
    proyectoBarEl.dataset.bound = "1";
    var cb = document.getElementById("projAuto");
    if (cb) {
      cb.addEventListener("change", function () {
        if (!activeProyecto) return;
        activeProyecto.auto = cb.checked;
        apiPost("/api/proyectos/" + encodeURIComponent(activeProyecto.id) + "/autoguardar",
          { auto: cb.checked }, null, "Error al cambiar el autoguardado.");
      });
    }
    var mg = document.getElementById("projBtnManage");
    if (mg) {
      mg.addEventListener("click", function () {
        var t = tools.find(function (x) { return x.id === "proyectos"; });
        if (t) setActive("proyectos");
      });
    }
    var cl = document.getElementById("projBtnClose");
    if (cl) {
      cl.addEventListener("click", function () {
        if (!activeProyecto) return;
        if (!window.confirm("Cerrar el proyecto activo? Dejará de guardar búsquedas automáticamente (lo ya guardado se conserva).")) return;
        fetch("/api/proyectos/desactivar", { method: "POST" })
          .then(function () { refreshProyectoState(); })
          .catch(function () { window.alert("Error de red."); });
      });
    }
  }

  function loadProjectDashboard() {
    var holder = document.getElementById("proj-dash");
    if (!holder) return;
    if (projView === "detail" && projDetailId) {
      loadProjDetail(projDetailId);
      return;
    }
    projView = "list";
    loadProjList();
  }

  function loadProjList() {
    var holder = document.getElementById("proj-dash");
    if (!holder) return;
    holder.innerHTML = '<p class="muted">Cargando proyectos...</p>';
    fetch("/api/proyectos")
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var list = (d && d.proyectos) || [];
        var html = "";
        html += renderCard("Nuevo proyecto", "",
          '<div class="search-box">' +
            '<input type="text" id="projNombre" placeholder="Nombre del proyecto (ej. Caso Juan Pérez)">' +
            '<input type="text" id="projDesc" placeholder="Qué querés investigar / descripción (opcional)">' +
            '<button class="mini-btn" id="projCreateBtn">Crear y activar</button>' +
          "</div>");
        if (!list.length) {
          html += renderCard("Proyectos", "", '<p class="muted">No hay proyectos todavía. Creá el primero arriba.</p>');
        } else {
          html += renderCard("Proyectos (" + list.length + ")", "",
            "<table><thead><tr><th>Proyecto</th><th>Creado</th><th>Resultados</th><th>Guardado</th><th>Acciones</th></tr></thead><tbody>" +
            list.map(projectRow).join("") + "</tbody></table>");
        }
        holder.innerHTML = html;
        bindProjectActions(holder);
      })
      .catch(function () {
        holder.innerHTML = '<div class="error-box">No se pudieron cargar los proyectos.</div>';
      });
  }

  function projectRow(p) {
    var badge = p.activo ? '<span class="badge ok">activo</span>' : "";
    var auto = '<label class="muted" style="white-space:nowrap"><input type="checkbox" data-auto="' + esc(p.id) + '" ' + (p.auto ? "checked" : "") + '> autoguardar</label>';
    var acciones = "";
    acciones += '<button class="mini-btn" data-act="ver" data-id="' + esc(p.id) + '">Abrir / resultados</button> ';
    acciones += '<a class="mini-btn" href="/api/proyectos/' + esc(p.id) + '/informe" target="_blank" rel="noopener">PDF</a> ';
    if (!p.activo) acciones += '<button class="mini-btn" data-act="activar" data-id="' + esc(p.id) + '">Activar</button> ';
    acciones += '<button class="mini-btn del" data-act="eliminar" data-id="' + esc(p.id) + '">Eliminar</button>';
    return "<tr><td><b>" + esc(p.nombre) + "</b> " + badge +
      (p.descripcion ? "<br><span class='muted'>" + esc(p.descripcion) + "</span>" : "") + "</td>" +
      "<td>" + esc(p.creado || "-") + "</td>" +
      "<td>" + (p.n_resultados == null ? "-" : p.n_resultados) + "</td>" +
      "<td>" + auto + "</td>" +
      "<td>" + acciones + "</td></tr>";
  }

  function loadProjDetail(pid) {
    var holder = document.getElementById("proj-dash");
    if (!holder) return;
    holder.innerHTML = '<p class="muted">Cargando proyecto...</p>';
    fetch("/api/proyectos/" + encodeURIComponent(pid))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.proyecto) {
          holder.innerHTML = '<div class="error-box">' + esc((d && d.error) || "No encontrado.") + "</div>";
          return;
        }
        var p = d.proyecto;
        var results = p.resultados || [];
        var html = "";
        html += '<p><button class="mini-btn" data-act="volver">« Volver a la lista</button></p>';
        html += renderCard("Proyecto: " + p.nombre,
          (p.activo ? '<span class="badge ok">activo</span>' : '<span class="badge warn">inactivo</span>'),
          '<div class="kv"><span>Descripción: <b>' + esc(p.descripcion || "-") + '</b></span></div>' +
          '<div class="kv"><span>Creado: ' + esc(p.creado || "-") + "</span>" +
          "<span>Actualizado: " + esc(p.actualizado || "-") + "</span></div>" +
          '<div class="search-box" style="margin-bottom:0">' +
            '<button class="mini-btn" data-act="activar" data-id="' + esc(p.id) + '">' + (p.activo ? "Ya está activo" : "Activar como proyecto actual") + '</button> ' +
            '<a class="mini-btn" href="/api/proyectos/' + esc(p.id) + '/informe" target="_blank" rel="noopener">Generar informe PDF</a> ' +
            '<label class="muted" style="align-self:center"><input type="checkbox" id="projAutoDetail" ' + (p.auto ? "checked" : "") + '> autoguardar</label> ' +
            '<button class="mini-btn del" data-act="eliminar" data-id="' + esc(p.id) + '">Eliminar proyecto</button>' +
          "</div>");

        var rhtml = "";
        if (results.length) {
          rhtml += renderCard("Resultados guardados (" + results.length + ")", "",
            '<p class="muted" style="margin-top:0"><label><input type="checkbox" id="projSelAll"> Seleccionar todos</label> ' +
            '<button class="mini-btn del" id="projDelSel" style="margin-left:10px">Eliminar seleccionados</button></p>' +
            results.map(resultRow).join(""));
        } else {
          rhtml += renderCard("Resultados guardados", "",
            '<p class="muted">Sin resultados todavía. Con el proyecto activo y el autoguardado encendido, cada búsqueda queda guardada acá sola (o usá el botón "Guardar al proyecto" que aparece arriba de cada resultado).</p>');
        }
        holder.innerHTML = html + rhtml;
        bindProjectActions(holder);

        var autoD = document.getElementById("projAutoDetail");
        if (autoD) {
          autoD.addEventListener("change", function () {
            apiPost("/api/proyectos/" + encodeURIComponent(p.id) + "/autoguardar", { auto: autoD.checked },
              function () {
                if (activeProyecto && activeProyecto.id === p.id) activeProyecto.auto = autoD.checked;
                syncProyectoBar();
              }, "Error al cambiar el autoguardado.");
          });
        }
        var selAll = document.getElementById("projSelAll");
        if (selAll) {
          selAll.addEventListener("change", function () {
            holder.querySelectorAll(".projSelRow").forEach(function (c) { c.checked = selAll.checked; });
          });
        }
        var delSel = document.getElementById("projDelSel");
        if (delSel) {
          delSel.addEventListener("click", function () {
            var rids = [];
            holder.querySelectorAll(".projSelRow:checked").forEach(function (c) { rids.push(c.value); });
            if (!rids.length) {
              window.alert("Primero seleccioná los resultados a eliminar.");
              return;
            }
            if (!window.confirm("Eliminar " + rids.length + " resultado(s)?")) return;
            var done = 0;
            rids.forEach(function (rid) {
              fetch("/api/proyectos/" + encodeURIComponent(p.id) + "/resultados/" + encodeURIComponent(rid), { method: "DELETE" })
                .then(function () { done++; if (done === rids.length) loadProjDetail(p.id); })
                .catch(function () { done++; });
            });
          });
        }
      })
      .catch(function () {
        holder.innerHTML = '<div class="error-box">No se pudo cargar el proyecto.</div>';
      });
  }

  function resultRow(r) {
    var lineas = "";
    (r.lineas || []).slice(0, 8).forEach(function (l) {
      lineas += "<div class='muted' style='overflow-wrap:anywhere'>" + esc(l) + "</div>";
    });
    if ((r.lineas || []).length > 8) lineas += "<div class='muted'>... (+" + ((r.lineas || []).length - 8) + " líneas)</div>";
    var links = "";
    (r.links || []).slice(0, 6).forEach(function (l) {
      links += '<a class="muted" href="' + esc(l.url) + '" target="_blank" rel="noopener">' + esc(l.name) + " &#8599;</a> ";
    });
    var autoLabel = r.auto ? ' <span class="muted">(auto)</span>' : "";
    return '<div class="result-card">' +
      '<input type="checkbox" class="projSelRow" value="' + esc(r.id) + '" style="float:right" title="Seleccionar para eliminar">' +
      "<h3>" + esc(r.tool_nombre || r.tool) + autoLabel + "</h3>" +
      (r.objetivo ? "<p><b>" + esc(r.objetivo) + "</b> <span class='muted'>" + esc(r.fecha || "") + "</span></p>" : "") +
      lineas +
      (r.detalle ? "<pre style='font-size:11px;white-space:pre-wrap'>" + esc(r.detalle.slice(0, 1000)) + "</pre>" : "") +
      (links ? '<div class="linklist" style="margin-top:8px">' + links + "</div>" : "") +
      '<div style="margin-top:8px"><button class="mini-btn del" data-act="delres" data-id="' + esc(r.id) + '">Eliminar</button></div>' +
      "</div>";
  }

  function bindProjectActions(holder) {
    if (!holder) return;

    holder.querySelectorAll("[data-act]").forEach(function (b) {
      b.addEventListener("click", function () {
        var act = b.dataset.act;
        var id = b.dataset.id;
        if (act === "volver") {
          projView = "list";
          projDetailId = null;
          loadProjList();
        } else if (act === "ver") {
          projView = "detail";
          projDetailId = id;
          loadProjDetail(id);
        } else if (act === "activar") {
          apiPost("/api/proyectos/" + encodeURIComponent(id) + "/activar", {}, function () {
            refreshProyectoState();
            if (projView === "detail") loadProjDetail(id); else loadProjList();
          }, "Error al activar el proyecto.");
        } else if (act === "eliminar") {
          if (!window.confirm("¿Eliminar este proyecto y TODOS sus resultados guardados? Esta acción no se puede deshacer.")) return;
          fetch("/api/proyectos/" + encodeURIComponent(id), { method: "DELETE" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (!d.ok) { window.alert((d && d.error) || "Error."); return; }
              refreshProyectoState();
              projView = "list";
              projDetailId = null;
              loadProjList();
            })
            .catch(function () { window.alert("Error de red."); });
        } else if (act === "delres") {
          if (!window.confirm("¿Eliminar este resultado?")) return;
          var pid = projDetailId;
          fetch("/api/proyectos/" + encodeURIComponent(pid) + "/resultados/" + encodeURIComponent(id), { method: "DELETE" })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (!d.ok) { window.alert((d && d.error) || "Error."); return; }
              loadProjDetail(pid);
              refreshProyectoState();
            })
            .catch(function () { window.alert("Error de red."); });
        }
      });
    });

    var createBtn = holder.querySelector("#projCreateBtn");
    if (createBtn) {
      createBtn.addEventListener("click", function () {
        var nombre = (document.getElementById("projNombre") || { value: "" }).value.trim();
        if (!nombre) {
          window.alert("Ingresá el nombre del proyecto.");
          return;
        }
        var desc = (document.getElementById("projDesc") || { value: "" }).value.trim();
        apiPost("/api/proyectos", { nombre: nombre, descripcion: desc }, function () {
          refreshProyectoState();
          loadProjList();
        }, "Error al crear el proyecto.");
      });
    }

    holder.querySelectorAll("[data-auto]").forEach(function (cb) {
      cb.addEventListener("change", function () {
        var pid = cb.dataset.auto;
        apiPost("/api/proyectos/" + encodeURIComponent(pid) + "/autoguardar", { auto: cb.checked }, function () {
          if (activeProyecto && activeProyecto.id === pid) activeProyecto.auto = cb.checked;
          syncProyectoBar();
        }, "Error al cambiar el autoguardado.");
      });
    });
  }

  btnEl.addEventListener("click", submitSearch);
  queryEl.addEventListener("keydown", function (e) { if (e.key === "Enter") submitSearch(); });

  initApp();
})();