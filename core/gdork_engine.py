def generate_dorks(target, tipo):
    dorks = {
        "usuario": [
            f'""{target}"'
        ],
        "email": [],
        "telefono": [],
        "persona": [],
        "dominio": [],
    }

    base = {
        "usuario": [
            {"name": 'Perfiles sociales', "url": f"https://www.google.com/search?q=%22{target}%22+(profile+OR+user+OR+%E2%80%9Ccuenta%E2%80%9D)"},
            {"name": "Github", "url": f"https://github.com/{target}"},
            {"name": "Reddit", "url": f"https://www.reddit.com/user/{target}"},
            {"name": "Twitter/X", "url": f"https://twitter.com/{target}"},
            {"name": "Instagram", "url": f"https://www.instagram.com/{target}"},
            {"name": "Facebook", "url": f"https://www.facebook.com/{target}"},
            {"name": "Menciones con e-mail", "url": f"https://www.google.com/search?q=%22{target}%22+%40+email"},
            {"name": "Pastes / leaks", "url": f"https://www.google.com/search?q=%22{target}%22+pastebin"},
            {"name": "Imágenes", "url": f"https://www.google.com/search?q=%22{target}%22&tbm=isch"},
            {"name": "Noticias", "url": f"https://news.google.com/search?q={target}"},
        ],
        "email": [
            {"name": "Menciones del email", "url": f"https://www.google.com/search?q=%22{target}%22"},
            {"name": "Breach / leaks (dehashed)", "url": f"https://www.google.com/search?q=%22{target}%22+password+leak"},
            {"name": "Pastebin", "url": f"https://www.google.com/search?q=%22{target}%22+site:pastebin.com"},
            {"name": "Documentos expuestos", "url": f"https://www.google.com/search?q=%22{target}%22+filetype:pdf+OR+filetype:doc"},
            {"name": "Registro en webs", "url": f"https://www.google.com/search?q=%22{target}%22+inscription+OR+registration"},
            {"name": "Imágenes", "url": f"https://www.google.com/search?q=%22{target}%22&tbm=isch"},
            {"name": "Redes asociadas", "url": f"https://www.google.com/search?q=%22{target}%22+(twitter+OR+facebook+OR+instagram)"},
        ],
        "telefono": [
            {"name": 'Menciones del número', "url": f"https://www.google.com/search?q=%22{target}%22"},
            {"name": "Bing", "url": f"https://www.bing.com/search?q=%22{target}%22"},
            {"name": "DuckDuckGo", "url": f"https://duckduckgo.com/?q=%22{target}%22"},
            {"name": "WhatsApp", "url": f"https://wa.me/{target}"},
            {"name": "Pastes / leaks", "url": f"https://www.google.com/search?q=%22{target}%22+site:pastebin.com"},
            {"name": "Truecaller", "url": f"https://www.truecaller.com/search/all?search={target}"},
        ],
        "persona": [
            {"name": 'Perfil completo ("nombre apellido")', "url": f"https://www.google.com/search?q=%22{target}%22"},
            {"name": "Redes sociales", "url": f"https://www.google.com/search?q=%22{target}%22+(facebook+OR+instagram+OR+linkedin)"},
            {"name": "LinkedIn", "url": f"https://www.linkedin.com/search/results/people/?keywords={target.replace(' ', '+')}"},
            {"name": "Documentos públicos", "url": f"https://www.google.com/search?q=%22{target}%22+filetype:pdf"},
            {"name": "Noticias", "url": f"https://news.google.com/search?q={target.replace(' ', '+')}"},
            {"name": "Boletín Oficial", "url": f"https://www.boletinoficial.gob.ar/buscar?texto={target.replace(' ', '+')}"},
            {"name": "Registro de la Propiedad (CABA)", "url": "https://www.buenosaires.gob.ar/registro-inmuebles"},
            {"name": "Imágenes", "url": f"https://www.google.com/search?q=%22{target}%22&tbm=isch"},
        ],
        "dominio": [
            {"name": "Informe completo del dominio", "url": f"https://www.google.com/search?q=site:{target}"},
            {"name": "Emails en el dominio", "url": f"https://www.google.com/search?q=%40{target}"},
            {"name": "Documentos expuestos", "url": f"https://www.google.com/search?q=site:{target}+filetype:pdf"},
            {"name": "Subdominios", "url": f"https://www.google.com/search?q=site%3A*.{target}"},
            {"name": "Certificates (crt.sh)", "url": f"https://crt.sh/?q=%25.{target}"},
            {"name": "Historial DNS (ViewDNS)", "url": f"https://viewdns.info/iphistory/?domain={target}"},
            {"name": "Web Archive", "url": f"https://web.archive.org/web/*/{target}"},
            {"name": "VirusTotal", "url": f"https://www.virustotal.com/gui/domain/{target}/relations"},
            {"name": "URLScan", "url": f"https://urlscan.io/api/v1/search/?q=domain:{target}"},
        ],
    }
    return base.get(tipo, [])