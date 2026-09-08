import socket
import re


def _validate_ip(ip):
    octets = ip.split(".")
    if len(octets) != 4:
        return False
    for o in octets:
        if not o.isdigit():
            return False
        if not 0 <= int(o) <= 255:
            return False
    return True


def _reverse_dns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


def _ip_whois(ip):
    try:
        import ipwhois
        obj = ipwhois.IPWhois(ip)
        res = obj.lookup_rdap(asn_methods=["whois"])
        return {
            "asn": res.get("asn"),
            "asn_description": res.get("asn_description"),
            "asn_country_code": res.get("asn_country_code"),
            "asn_registry": res.get("asn_registry"),
            "network": res.get("network"),
            "country": res.get("asn_country_code"),
        }
    except ImportError:
        return {"error": "ipwhois (paquete pip) no instalado."}
    except Exception as e:
        return {"error": str(e)}


def _whois_text(ip):
    whois_lines = []
    try:
        import whois as whois_pkg
        w = whois_pkg.whois(ip)
        for key in ["org", "netname", "desc", "country", "mnt-by", "created", "last-modified"]:
            val = getattr(w, key, None)
            if val:
                whois_lines.append({"field": key, "value": str(val)})
    except Exception:
        pass
    return whois_lines


def _abuse_links(ip):
    return [
        {
            "name": "AbuseIPDB",
            "url": f"https://www.abuseipdb.com/check/{ip}",
            "info": "Reportes de abuso y reputación de la IP.",
        },
        {
            "name": "VirusTotal",
            "url": f"https://www.virustotal.com/gui/ip-address/{ip}",
            "info": "Análisis de reputación y detección.",
        },
        {
            "name": "Shodan",
            "url": f"https://www.shodan.io/host/{ip}",
            "info": "Servicios y puertos expuestos.",
        },
        {
            "name": "GreyNoise",
            "url": f"https://viz.greynoise.io/ip/{ip}",
            "info": "Clasificación de ruido/exploración.",
        },
        {
            "name": "Censys",
            "url": f"https://search.censys.io/search?resource=hosts&sort=RELEVANCE&q={ip}",
            "info": "Inventario de internet.",
        },
        {
            "name": "Censys (explore)",
            "url": f"https://search.censys.io/hosts/{ip}",
            "info": "Certificados y servicios de la IP.",
        },
        {
            "name": "DNSlytics",
            "url": f"https://dnslytics.com/ip/{ip}",
            "info": "Historial y reputación DNS.",
        },
        {
            "name": "Ipinfo.io",
            "url": f"https://ipinfo.io/{ip}",
            "info": "Geolocalización y datos de la IP.",
        },
        {
            "name": "Robtex",
            "url": f"https://www.robtex.com/ip-lookup/{ip}",
            "info": "Relaciones DNS/IP.",
        },
    ]


def search_ip(ip):
    results = {"ip": ip, "valid": False, "error": None}

    ip = ip.strip()
    if not _validate_ip(ip):
        results["error"] = "Dirección IP no válida."
        return results

    results["valid"] = True
    results["reverse_dns"] = _reverse_dns(ip)
    results["whois"] = _ip_whois(ip)
    results["abuse"] = _abuse_links(ip)
    results["whois_text"] = _whois_text(ip)
    return results