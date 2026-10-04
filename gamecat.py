"""Catalogue de jeux par console, depuis internet.

- Jeux du commerce : liste complète des jeux sortis sur chaque console (bases No-Intro / Redump
  de RetroArch), avec genre, année et développeur. Fiches seulement : ces jeux sont protégés,
  on les copie depuis sa propre cartouche ou son propre disque.
- Jeux gratuits et légaux, installables directement sur la carte :
    Homebrew Hub (hh.gbdev.io) : jeux amateurs Game Boy, Game Boy Color, GBA et NES ;
    Freedoom : Doom complet et libre (dossier doom).
"""
import io
import json
import os
import re
import time
import urllib.parse
import zipfile
from dataclasses import dataclass, field

import core
import journal
import metadata
import net
import paths
import regions
import scraper

DAT_URL = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/{}/{}.dat"
HH_SEARCH = "https://hh3.gbdev.io/api/search?platform={}&typetag=game&page={}"
HH_FILE = "https://hh3.gbdev.io/static/{}/entries/{}/{}"
FREEDOOM = "https://api.github.com/repos/freedoom/freedoom/releases/latest"
CACHE_DIR = paths.data("cache", "catalog")
CACHE_DAYS = 7
HH_PLATFORMS = {"gb": "GB", "gbc": "GBC", "gba": "GBA", "nes": "NES"}
GENRES = set(metadata.GENRES.values())  # genres connus de la carte (un tag « 2d » n'en est pas un)
# versions qui ne sont pas des jeux sortis en boutique
EXCLUDED = re.compile(r"\((?:[^)]*\b(?:beta|proto|demo|sample|program|pirate|aftermarket|unl|kiosk|test|debug)\b"
                      r"[^)]*)\)|\[bios\]", re.I)


@dataclass
class Entry:
    title: str
    system: str                 # dossier ArkOS (« gb », « snes »…)
    key: str = ""               # core.title_key : sert à reconnaître le jeu sur la carte
    names: list = field(default_factory=list)   # noms complets des versions (« Tetris (World) »)
    regions: list = field(default_factory=list)
    year: str = ""
    genre: str = ""
    developer: str = ""
    desc: str = ""
    free: bool = False          # installable (gratuit et légal)
    url: str = ""               # fichier à télécharger
    filename: str = ""          # nom du fichier sur la carte
    image: str = ""             # URL de l'image
    license: str = ""
    website: str = ""
    added: str = ""             # date d'arrivée dans le catalogue (jeux gratuits)


# ---------------------------------------------------------------- cache

def _cached(name, fetch, days=CACHE_DAYS):
    """Contenu texte en cache (renouvelé après quelques jours) ; l'ancien sert si internet manque."""
    path = os.path.join(CACHE_DIR, name)
    if os.path.isfile(path) and time.time() - os.path.getmtime(path) < days * 86400:
        with open(path, encoding="utf-8") as f:
            return f.read()
    try:
        text = fetch()
    except OSError:
        if not os.path.isfile(path):
            raise
        with open(path, encoding="utf-8") as f:
            return f.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


# ---------------------------------------------------------------- jeux du commerce

def parse_dat(text):
    """Noms des jeux d'un .dat No-Intro / Redump."""
    return re.findall(r'^\s*name "([^"]+)"\s*$', "\n".join(re.findall(r"^game \($(.*?)^\)", text, re.M | re.S)),
                      re.M)


def _dat_text(system_name):
    for kind in ("no-intro", "redump"):
        try:
            return _cached(f"{kind}/{system_name}.dat",
                           lambda: net.get(DAT_URL.format(kind, urllib.parse.quote(system_name)), 60).decode(
                               "utf-8", "replace"), days=30)
        except OSError:
            continue
    return ""


def has_list(system):
    return system.lower() in scraper.LIBRETRO and scraper.LIBRETRO[system.lower()] not in ("MAME", "DOS",
                                                                                           "ScummVM")


def commercial(system):
    """[Entry] : un par jeu (toutes régions regroupées) sorti sur la console."""
    system_name = scraper.LIBRETRO.get(system.lower())
    if not system_name or not has_list(system):
        return []
    groups = {}
    for name in parse_dat(_dat_text(system_name)):
        if EXCLUDED.search(name):
            continue
        key = core.title_key(core.DISC_RE.sub("", name))
        if key:
            groups.setdefault(key, []).append(name)
    info = {f: metadata._dat(f, system_name)["name"] for f in ("genre", "releaseyear", "developer")}
    out = []
    for key, names in groups.items():
        names = sorted(dict.fromkeys(names), key=_region_rank)
        title = display_title(re.sub(r"\s*\(.*$", "", core.DISC_RE.sub("", names[0])).strip())
        e = Entry(title, system, key, names, list(dict.fromkeys(c for n in names for c in regions.regions(n))))
        for n in names:
            e.genre = e.genre or metadata.french_genre(info["genre"].get(n, "")) or ""
            e.year = e.year or info["releaseyear"].get(n, "")
            e.developer = e.developer or info["developer"].get(n, "")
        out.append(e)
    return sorted(out, key=lambda e: e.title.lower())


def display_title(title):
    """« Legend of Zelda, The - A Link to the Past » -> « The Legend of Zelda - A Link to the Past »."""
    m = re.match(r"^(.*?), (The|A|An|Le|La|Les|Der|Die|Das|El|Il)( - .*)?$", title)
    return f"{m.group(2)} {m.group(1)}{m.group(3) or ''}" if m else title


def _region_rank(name):
    """Europe / France d'abord (meilleure image et titre), puis USA, monde, Japon."""
    order = ["fr", "eu", "world", "us", "jp"]
    codes = regions.regions(name)
    return min((order.index(c) for c in codes if c in order), default=len(order)), len(name)


def boxart_url(entry):
    """Jaquette libretro du jeu (première version qui en a une), ou ""."""
    system_name = scraper.LIBRETRO.get(entry.system.lower())
    if not system_name:
        return ""
    known = set(scraper._listing(system_name, "Named_Boxarts"))
    for n in entry.names:
        if scraper._clean(n) in known:
            return scraper._url(system_name, "Named_Boxarts", scraper._clean(n) + ".png")
    return ""


# ---------------------------------------------------------------- jeux gratuits

def _homebrew(system, report=None, cancel=None):
    platform = HH_PLATFORMS[system.lower()]

    def fetch():
        entries, page, pages = [], 1, 1
        while page <= pages:
            if cancel is not None and cancel.is_set():
                raise OSError("annulé")
            data = json.loads(net.get(HH_SEARCH.format(platform, page), 30))
            pages = data.get("page_total", 1)
            entries += data.get("entries", [])
            if report:
                report(page, pages)
            page += 1
        return json.dumps(entries)
    out = []
    for h in json.loads(_cached(f"homebrew/{platform}.json", fetch)):
        files = [f for f in h.get("files") or [] if f.get("playable", True)]
        rom = next((f for f in files if f.get("default")), files[0] if files else None)
        if not rom:
            continue
        base, slug = h.get("basepath", ""), h.get("slug", "")
        shots = h.get("screenshots") or []
        ext = os.path.splitext(rom["filename"])[1].lower()
        tags = [t for t in h.get("tags") or [] if ":" not in t]  # « event:gbajam26 » n'est pas un genre
        title = re.sub(r"^\((?:game boy|gb|gbc|gba|nes)[^)]*\)\s*", "", (h.get("title") or slug).strip(), flags=re.I)
        out.append(Entry(
            title, system.lower(), core.title_key(title),
            desc=(h.get("description") or "").strip(), developer=_text(h.get("developer")),
            genre=next((g for g in map(metadata.french_genre, tags) if g in GENRES), ""), free=True,
            url=HH_FILE.format(base, slug, rom["filename"]),
            filename=_safe(title) + ext,
            image=HH_FILE.format(base, slug, shots[0]) if shots else "",
            license=h.get("license") or "", website=h.get("website") or h.get("gameWebsite") or "",
            year=(h.get("date") or "")[:4], added=(h.get("firstadded_date") or "")[:10]))
    return sorted(out, key=lambda e: e.title.lower())


def _text(value):
    if isinstance(value, list):
        return ", ".join(v.get("name", "") if isinstance(v, dict) else str(v) for v in value)
    return value.get("name", "") if isinstance(value, dict) else str(value or "")


def _safe(title):
    return re.sub(r'[<>:"/\\|?*]', "", title).strip().rstrip(".") or "game"


def _freedoom():
    data = json.loads(_cached("freedoom.json", lambda: net.get(FREEDOOM, 30).decode("utf-8")))
    asset = next((a for a in data.get("assets", []) if re.fullmatch(r"freedoom-[\d.]+\.zip", a["name"])), None)
    if not asset:
        return []
    desc = ("Freedoom est un jeu de tir complet, libre et gratuit, compatible avec le moteur de Doom. "
            "Phase 1 reprend les épisodes du premier Doom, Phase 2 la campagne de Doom II.")
    return [Entry(f"Freedoom: Phase {n}", "doom", f"freedoomphase{n}", desc=desc, developer="Freedoom Project",
                  genre="Tir", year=(data.get("published_at") or "")[:4], free=True, url=asset["browser_download_url"],
                  filename=f"freedoom{n}.wad", license="BSD-3-Clause", website="https://freedoom.github.io",
                  image=f"https://freedoom.github.io/img/screenshots/p{n}_1.png")
            for n in (1, 2)]


def free_games(system, report=None, cancel=None):
    if system.lower() in HH_PLATFORMS:
        return _homebrew(system, report, cancel)
    if system.lower() == "doom":
        return _freedoom()
    return []


def has_free(system):
    return system.lower() in HH_PLATFORMS or system.lower() == "doom"


# ---------------------------------------------------------------- sur la carte ?

def owned_keys(games):
    """Titres simplifiés des jeux de la carte (pour cocher « sur ta carte »)."""
    return {core.title_key(core.DISC_RE.sub("", g.stem)) for g in games} | \
           {core.title_key(g.name) for g in games}


def owned(entry, keys, folder_files=()):
    if entry.free and entry.filename.lower() in folder_files:
        return True
    return bool(entry.key) and entry.key in keys


# ---------------------------------------------------------------- installation

def install(root, entry, report=None, cancel=None):
    """Télécharge un jeu gratuit dans le dossier de sa console. Retourne son chemin (None si annulé)."""
    dest = os.path.join(root, entry.system, entry.filename)
    data = bytearray()
    with net.open_url(entry.url, timeout=60) as r:
        while chunk := r.read(1 << 20):
            if cancel is not None and cancel.is_set():
                return None
            data += chunk
            if report:
                report(len(data))
    if entry.system == "doom":  # l'archive Freedoom contient freedoom1.wad et freedoom2.wad
        with zipfile.ZipFile(io.BytesIO(bytes(data))) as z:
            member = next(n for n in z.namelist() if os.path.basename(n).lower() == entry.filename.lower())
            data = z.read(member)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    def write(path):
        with open(path, "wb") as f:
            f.write(data)
    journal.write_file(dest, write)
    return dest


def card_values(entry):
    """Fiche du gamelist pour un jeu gratuit installé."""
    desc = entry.desc
    if entry.license:
        desc = (desc + "\n\n" if desc else "") + f"Licence : {entry.license}" + \
               (f" — {entry.website}" if entry.website else "")
    return {"name": entry.title, "desc": desc, "developer": entry.developer, "genre": entry.genre,
            "year": entry.year}
