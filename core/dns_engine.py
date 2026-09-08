import dns.resolver
import socket


def _query(domain, rtype):
    result = []
    try:
        answers = dns.resolver.resolve(domain, rtype)
        for r in answers:
            result.append(r.to_text())
    except dns.resolver.NoAnswer:
        pass
    except dns.resolver.NXDOMAIN:
        return None, "El dominio no existe (NXDOMAIN)."
    except dns.resolver.NoNameservers:
        return None, "Sin servidores DNS disponibles."
    except dns.exception.DNSException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)
    return result, None


def search_dns(domain):
    results = {"domain": domain, "records": {}, "error": None}

    lookup_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "SPF"]

    target = domain
    for rtype in lookup_types:
        records, err = _query(target, rtype)
        if err:
            results["records"][rtype] = {"error": err}
        else:
            results["records"][rtype] = records

    try:
        results["ip"] = socket.gethostbyname(domain)
    except Exception:
        results["ip"] = None

    return results