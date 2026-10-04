"""Accès internet commun à tout le programme.

- Utilise les certificats du module certifi quand il est présent : le magasin de certificats
  Windows vu par Python peut contenir des certificats expirés (erreur CERTIFICATE_VERIFY_FAILED
  sur Wikidata, par exemple).
- Reste poli avec les sites : délai minimal entre deux requêtes vers un même site et nouvelle
  tentative si le site répond « trop de requêtes » (429) ou « indisponible » (503).
"""
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "R36S-Game-Manager/1.0 (gestionnaire de jeux R36S)"
MIN_INTERVAL = {"www.wikidata.org": 0.4, "fr.wikipedia.org": 0.2, "en.wikipedia.org": 0.2}
RETRIES = 2  # un jeu introuvable ne doit pas faire attendre longtemps

try:
    import certifi
    _CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _CONTEXT = None

_last = {}
_lock = threading.Lock()


def _wait_turn(url):
    host = urllib.parse.urlsplit(url).hostname or ""
    delay = MIN_INTERVAL.get(host, 0)
    if not delay:
        return
    with _lock:
        wait = _last.get(host, 0) + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()


def open_url(url, timeout=30):
    """Ouvre une URL (à utiliser avec « with »), en réessayant si le site est surchargé."""
    for attempt in range(RETRIES):
        _wait_turn(url)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}),
                                          timeout=timeout, context=_CONTEXT)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == RETRIES - 1:
                raise
            retry_after = e.headers.get("Retry-After", "")
            time.sleep(min(int(retry_after), 8) if retry_after.isdigit() else 3)
    raise OSError("site indisponible")


def get(url, timeout=30):
    with open_url(url, timeout) as r:
        return r.read()
