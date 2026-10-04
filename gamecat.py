"""Catalogue de jeux par console, depuis internet.

- Jeux du commerce : liste complète des jeux sortis sur chaque console (bases No-Intro / Redump
  de RetroArch), avec genre, année et développeur. Fiches seulement : ces jeux sont protégés,
  on les copie depuis sa propre cartouche ou son propre disque.
- Notes et popularité : base LaunchBox (note de la communauté sur 5 et nombre de votes),
  téléchargée une fois par mois (108 Mo) puis réduite à un petit index.
- Jeux gratuits et légaux, installables directement sur la carte :
    Homebrew Hub (hh.gbdev.io) : jeux amateurs Game Boy, Game Boy Color, GBA et NES ;
    Freedoom : Doom complet et libre (dossier doom).
"""
import html
import io
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
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
LAUNCHBOX = "https://gamesdb.launchbox-app.com/Metadata.zip"
RATINGS_DAYS = 30
# dossier ArkOS -> plateforme LaunchBox
LB_PLATFORMS = {
    "gb": "Nintendo Game Boy", "gbc": "Nintendo Game Boy Color", "gba": "Nintendo Game Boy Advance",
    "nes": "Nintendo Entertainment System", "famicom": "Nintendo Entertainment System",
    "fds": "Nintendo Famicom Disk System", "snes": "Super Nintendo Entertainment System",
    "sfc": "Super Nintendo Entertainment System", "n64": "Nintendo 64", "nds": "Nintendo DS",
    "virtualboy": "Nintendo Virtual Boy", "pokemini": "Nintendo Pokemon Mini", "gameandwatch": "Nintendo Game & Watch",
    "gamegear": "Sega Game Gear", "mastersystem": "Sega Master System", "megadrive": "Sega Genesis",
    "genesis": "Sega Genesis", "sega32x": "Sega 32X", "segacd": "Sega CD", "saturn": "Sega Saturn",
    "dreamcast": "Sega Dreamcast", "sg-1000": "Sega SG-1000", "psx": "Sony Playstation", "psp": "Sony PSP",
    "pcengine": "NEC TurboGrafx-16", "tg16": "NEC TurboGrafx-16", "pcenginecd": "NEC TurboGrafx-CD",
    "pcfx": "NEC PC-FX", "ngp": "SNK Neo Geo Pocket", "ngpc": "SNK Neo Geo Pocket Color",
    "neogeocd": "SNK Neo Geo CD", "wonderswan": "WonderSwan", "wonderswancolor": "WonderSwan Color",
    "atari2600": "Atari 2600", "atari5200": "Atari 5200", "atari7800": "Atari 7800", "atarilynx": "Atari Lynx",
    "atarijaguar": "Atari Jaguar", "atarist": "Atari ST", "amiga": "Commodore Amiga", "c64": "Commodore 64",
    "coleco": "ColecoVision", "intellivision": "Mattel Intellivision", "msx": "Microsoft MSX",
    "msx2": "Microsoft MSX2", "3do": "3DO Interactive Multiplayer", "vectrex": "GCE Vectrex",
    "zxspectrum": "Sinclair ZX Spectrum",
    "neogeo": ("SNK Neo Geo MVS", "SNK Neo Geo AES", "Arcade"), "cps1": "Arcade", "cps2": "Arcade",
    "cps3": "Arcade", "fbneo": "Arcade", "arcade": "Arcade",
    "ports": ("Windows", "Linux", "MS-DOS", "Android"),  # jeu original des ports PortMaster
}


def lb_platforms(system):
    """Plateformes LaunchBox d'une console (la Neo Geo existe en version salle et salon)."""
    value = LB_PLATFORMS.get(system.lower(), ())
    return (value,) if isinstance(value, str) else value
HH_PLATFORMS = {"gb": "GB", "gbc": "GBC", "gba": "GBA", "nes": "NES"}
GENRES = set(metadata.GENRES.values())  # genres connus de la carte (un tag « 2d » n'en est pas un)
# versions qui ne sont pas des jeux sortis en boutique
EXCLUDED = re.compile(r"\((?:[^)]*\b(?:beta|proto|prototype|demo|sample|program|pirate|aftermarket|unl|kiosk|test|"
                      r"debug|bootleg|hack)\b[^)]*)\)|\[bios\]", re.I)
# consoles d'arcade : jeux pris dans la liste FinalBurn Neo (« sourcefile » de chaque jeu)
ARCADE_SOURCES = {"neogeo": "neogeo/", "cps1": "/d_cps1.", "cps2": "/d_cps2.", "cps3": "/d_cps3.",
                  "fbneo": "", "arcade": ""}
ARCADE_THUMBS = "FBNeo - Arcade Games"


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
    rating: float = 0.0         # note de la communauté LaunchBox, sur 5 (0 = inconnue)
    votes: int = 0              # nombre de votes : sert de mesure de popularité
    codes: list = field(default_factory=list)   # arcade : noms de code (« mslug », « mslugh »…)
    thumbs: str = ""            # dossier d'images libretro, s'il n'est pas celui de la console
    game_id: str = ""           # identifiant LaunchBox : réunit les titres japonais / occidentaux d'un jeu

    @property
    def keys(self):
        """Titres simplifiés du jeu et de toutes ses versions."""
        names = [self.key] + [core.title_key(core.DISC_RE.sub("", n)) for n in self.names]
        return {k for k in names + [core.title_key(c) for c in self.codes] if k}

    @property
    def score(self):
        """Note corrigée par le nombre de votes (moyenne bayésienne) : un 5/5 donné par une seule
        personne ne passe pas devant un 4,6/5 donné par mille."""
        prior, weight = 3.0, 10
        return (self.rating * self.votes + prior * weight) / (self.votes + weight) if self.votes else 0.0


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
    s = system.lower()
    return s in ARCADE_SOURCES or (s in scraper.LIBRETRO and scraper.LIBRETRO[s] not in ("MAME", "DOS", "ScummVM"))


def parse_fbneo_games(text):
    """[{name, cloneof, source, desc, year, maker}] depuis la liste FinalBurn Neo."""
    out = []
    for m in re.finditer(r'<game name="([^"]+)"([^>]*)>(.*?)</game>', text, re.S):
        attrs, body = m.group(2), m.group(3)

        def get(pattern, where):
            found = re.search(pattern, where)
            return html.unescape(found.group(1)) if found else ""
        out.append({"name": m.group(1), "cloneof": get(r'cloneof="([^"]+)"', attrs),
                    "source": get(r'sourcefile="([^"]+)"', attrs), "desc": get(r"<description>([^<]*)<", body),
                    "year": get(r"<year>(\d{4})", body), "maker": get(r"<manufacturer>([^<]*)<", body)})
    return out


def arcade(system):
    """[Entry] des jeux d'arcade d'une console : un par jeu, ses versions (clones) regroupées."""
    source = ARCADE_SOURCES[system.lower()]
    games = [g for g in parse_fbneo_games(metadata.fbneo_text()) if source in g["source"]]
    parents = {}
    for g in games:
        if not g["cloneof"] and not EXCLUDED.search(g["desc"]):
            title = display_title(re.sub(r"\s*\(.*$", "", g["desc"].split(" / ")[0]).strip())
            parents[g["name"]] = Entry(title, system.lower(), core.title_key(title), [g["desc"]],
                                       regions.regions(g["desc"]), year=g["year"], developer=g["maker"],
                                       codes=[g["name"]], thumbs=ARCADE_THUMBS)
    for g in games:
        e = parents.get(g["cloneof"])
        if e and not EXCLUDED.search(g["desc"]):
            e.names.append(g["desc"])
            e.codes.append(g["name"])
            e.regions += [c for c in regions.regions(g["desc"]) if c not in e.regions]
    return sorted(parents.values(), key=lambda e: e.title.lower())


def commercial(system):
    """[Entry] : un par jeu (toutes régions regroupées) sorti sur la console."""
    if system.lower() in ARCADE_SOURCES:
        return arcade(system)
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
    system_name = entry.thumbs or scraper.LIBRETRO.get(entry.system.lower())
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


# ---------------------------------------------------------------- notes et popularité

def _ratings_path():
    return os.path.join(CACHE_DIR, "launchbox-ratings-v3.json")  # v3 : arcade et PC (ports)


def parse_launchbox(xml_file):
    """{plateforme: {titre simplifié: [note, votes, identifiant, année, genre]}} depuis Metadata.xml de LaunchBox
    (titres alternatifs compris : noms européens, japonais…)."""
    wanted = {p for s in LB_PLATFORMS for p in lb_platforms(s)}
    games, alternates = {}, []
    for _event, el in ET.iterparse(xml_file):
        if el.tag == "Game":
            platform, votes = el.findtext("Platform"), el.findtext("CommunityRatingCount") or "0"
            if platform in wanted:
                try:
                    rating = float(el.findtext("CommunityRating") or 0)
                except ValueError:
                    rating = 0.0
                year = (el.findtext("ReleaseDate") or el.findtext("ReleaseYear") or "")[:4]
                genre = metadata.french_genre((el.findtext("Genres") or "").split(";")[0]) or ""
                games[el.findtext("DatabaseID")] = (platform, el.findtext("Name") or "", round(rating, 2),
                                                    int(votes) if votes.isdigit() else 0,
                                                    year if year.isdigit() else "", genre)
            el.clear()
        elif el.tag == "GameAlternateName":
            alternates.append((el.findtext("DatabaseID"), el.findtext("AlternateName") or ""))
            el.clear()
        elif el.tag == "GameImage":
            el.clear()
    out = {}
    for db_id, (platform, name, rating, votes, year, genre) in games.items():
        table, key = out.setdefault(platform, {}), core.title_key(name)
        if key and (key not in table or votes > table[key][1]):
            table[key] = [rating, votes, db_id, year, genre]
    for db_id, name in alternates:
        if db_id in games and (key := core.title_key(name)):
            platform, _name, rating, votes, year, genre = games[db_id]
            out[platform].setdefault(key, [rating, votes, db_id, year, genre])
    return out


def ratings(force=False):
    """Index des notes LaunchBox (renouvelé tous les mois). {} si indisponible."""
    path = _ratings_path()
    fresh = os.path.isfile(path) and time.time() - os.path.getmtime(path) < RATINGS_DAYS * 86400
    if force or not fresh:
        part = os.path.join(CACHE_DIR, "launchbox-metadata.zip")
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with net.open_url(LAUNCHBOX, timeout=120) as r, open(part, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            with zipfile.ZipFile(part) as z, z.open("Metadata.xml") as xml_file:
                table = parse_launchbox(xml_file)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(table, f, separators=(",", ":"))
        except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError):
            pass  # pas d'internet : on garde l'ancien index s'il existe
        finally:
            if os.path.isfile(part):
                os.remove(part)  # 108 Mo : seul le petit index est gardé
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def apply_ratings(entries, table):
    """Ajoute note et nombre de votes aux jeux, puis réunit en une ligne les titres d'un même jeu
    (« Castlevania - Aria of Sorrow » et « Akatsuki no Minuet »). Retourne la nouvelle liste."""
    merged = {}  # console -> notes de toutes ses plateformes LaunchBox (la première a le dernier mot)
    for e in entries:
        if e.system not in merged:
            merged[e.system] = {}
            for platform in reversed(lb_platforms(e.system)):
                merged[e.system].update(table.get(platform, {}))
        found = merged[e.system]
        for key in [e.key] + sorted(e.keys - {e.key}):  # le titre principal d'abord
            if key in found:
                e.rating, e.votes, *rest = found[key]
                e.game_id, year, genre = (rest + ["", "", ""])[:3]
                e.year, e.genre = e.year or year, e.genre or genre  # CD (Redump) : pas d'année dans RetroArch
                break
    out, first = [], {}
    for e in entries:
        main = first.get(e.game_id) if e.game_id and e.votes and not e.free else None
        if main is None:
            if e.game_id and e.votes and not e.free:
                first[e.game_id] = e
            out.append(e)
            continue
        if _region_rank(e.names[0]) < _region_rank(main.names[0]):  # le titre européen / américain d'abord
            main.title, e.title = e.title, main.title
            main.names[:0] = e.names
        else:
            main.names += e.names
        main.regions += [c for c in e.regions if c not in main.regions]
        main.year = min(filter(None, (main.year, e.year)), default="")
        main.genre, main.developer = main.genre or e.genre, main.developer or e.developer
    return out


# ---------------------------------------------------------------- sur la carte ?

def owned_keys(games):
    """Titres simplifiés des jeux de la carte (pour cocher « sur ta carte »)."""
    return {core.title_key(core.DISC_RE.sub("", g.stem)) for g in games} | \
           {core.title_key(g.name) for g in games}


def owned(entry, keys, folder_files=()):
    if entry.free and entry.filename.lower() in folder_files:
        return True
    return bool(entry.keys & keys)


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
