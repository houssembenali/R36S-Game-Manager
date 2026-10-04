"""Compléter la fiche d'un jeu depuis internet, sans compte :

  1. base libretro (RetroArch) : genre, année, développeur, éditeur, joueurs — le jeu est
     reconnu par l'empreinte CRC de la ROM, sinon par son nom ;
  2. Wikidata : ce qui manque encore (année, genre, développeur, éditeur) + l'article Wikipédia ;
  3. Wikipédia (français, sinon anglais) : la description.
Aucune source gratuite ne fournit la note : elle reste à mettre à la main.

lookup(game) ne lève jamais d'exception : en cas de problème réseau elle renvoie ce qu'elle a.
Seuls les champs vides de la fiche sont proposés (rien n'est écrasé).
"""
import difflib
import html
import json
import os
import re
import time
import urllib.parse
import zipfile
import zlib

import core
import net
import paths
import scraper
import systems

METADAT = "https://raw.githubusercontent.com/libretro/libretro-database/master/metadat/{}/{}.dat"
METADAT_FIELDS = {"genre": "genre", "releaseyear": "year", "developer": "developer",
                  "publisher": "publisher", "maxusers": "players"}
CACHE_DIR = paths.data("cache", "metadat")
CACHE_DAYS = 30
VIDEO_GAME = "Q7889"  # Wikidata : « jeu vidéo »

# genres anglais (libretro) / libellés Wikidata -> genres utilisés sur la carte
GENRES = {
    "action": "Action", "adventure": "Aventure", "racing": "Course", "driving": "Course",
    "sports": "Sport", "sport": "Sport", "fighting": "Combat", "shooter": "Tir", "shoot'em up": "Shoot'em up",
    "shoot 'em up": "Shoot'em up", "beat'em up": "Beat'em All", "beat 'em up": "Beat'em All",
    "platform": "Plateforme", "platformer": "Plateforme", "puzzle": "Puzzle", "role-playing": "Jeu de rôles",
    "role-playing (rpg)": "Jeu de rôles", "rpg": "Jeu de rôles", "strategy": "Stratégie",
    "simulation": "Simulation", "board game": "Jeu de société", "music": "Musique et Danse",
    "pinball": "Flipper", "educational": "Éducatif", "compilation": "Compilation", "casino": "Casino",
    "card game": "Jeu de cartes", "quiz": "Quiz", "party": "Party game", "maze": "Labyrinthe",
    "jeu de plates-formes": "Plateforme", "jeu de plate-forme": "Plateforme", "jeu de course": "Course",
    "jeu de combat": "Combat", "jeu de rôle": "Jeu de rôles", "jeu vidéo de rôle": "Jeu de rôles",
    "jeu d'action": "Action", "jeu d'aventure": "Aventure", "action-aventure": "Action", "jeu de tir": "Tir",
    "jeu de tir à la première personne": "Tir", "beat them all": "Beat'em All", "jeu de sport": "Sport",
    "jeu de réflexion": "Puzzle", "jeu de puzzle": "Puzzle", "jeu de stratégie": "Stratégie",
    "jeu de simulation": "Simulation", "jeu de rythme": "Rythme", "jeu de flipper": "Flipper",
}

_dats = {}  # (champ, système libretro) -> {"crc": {crc: valeur}, "name": {nom: valeur}}


# ---------------------------------------------------------------- réseau

def _get(url, timeout=20):
    return net.get(url, timeout)


def _json(url):
    return json.loads(_get(url).decode("utf-8"))


# ---------------------------------------------------------------- base libretro

def parse_dat(text, field):
    """{"crc": {...}, "name": {...}} depuis un fichier .dat clrmamepro de libretro."""
    key = "users" if field == "maxusers" else field
    out = {"crc": {}, "name": {}}
    for block in re.findall(r"^game \($(.*?)^\)", text, re.M | re.S):
        name = re.search(r'^\s*comment "([^"]*)"', block, re.M)
        value = re.search(rf'^\s*{key} "?([^"\n]*)"?\s*$', block, re.M)
        if not (name and value):
            continue
        val = value.group(1).strip()
        out["name"][name.group(1)] = val
        for crc in re.findall(r"crc ([0-9A-Fa-f]{8})", block):
            out["crc"][crc.upper()] = val
    return out


def _dat(field, system_name):
    key = (field, system_name)
    if key in _dats:
        return _dats[key]
    path = os.path.join(CACHE_DIR, field, system_name + ".dat")
    text = None
    if os.path.isfile(path) and time.time() - os.path.getmtime(path) < CACHE_DAYS * 86400:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    if text is None:
        try:
            text = _get(METADAT.format(field, urllib.parse.quote(system_name))).decode("utf-8", "replace")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError:
            text = ""  # pas de fichier pour cette console (ou pas de réseau)
    _dats[key] = parse_dat(text, field)
    return _dats[key]


def rom_crc(path):
    """CRC32 de la ROM (lu dans l'en-tête du .zip, sinon calculé). None pour les gros fichiers."""
    try:
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                return f"{infos[0].CRC:08X}" if len(infos) == 1 else None
        if os.path.getsize(path) > 64 << 20:
            return None
        crc = 0
        with open(path, "rb") as f:
            while chunk := f.read(1 << 20):
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08X}"
    except (OSError, zipfile.BadZipFile, IndexError):
        return None


def from_libretro(game):
    system_name = scraper.LIBRETRO.get(game.system.lower())
    if not system_name:
        return {}
    dats = {f: _dat(f, system_name) for f in METADAT_FIELDS}
    crc = rom_crc(game.path)
    names = sorted({n for d in dats.values() for n in d["name"]})
    match = scraper.best_match(game, names) if names else None
    out = {}
    for field, target in METADAT_FIELDS.items():
        value = dats[field]["crc"].get(crc) if crc else None
        if value is None and match:
            value = dats[field]["name"].get(match)
        if value:
            out[target] = value
    if "players" in out and out["players"] not in ("", "1"):
        out["players"] = f"1-{out['players']}"
    return out


# ---------------------------------------------------------------- Wikidata / Wikipédia

def _label(entity):
    labels = entity.get("labels", {})
    return (labels.get("fr") or labels.get("en") or {}).get("value", "")


def _ids(entity, prop):
    return [c["mainsnak"]["datavalue"]["value"]["id"] for c in entity.get("claims", {}).get(prop, [])
            if c["mainsnak"].get("datavalue", {}).get("type") == "wikibase-entityid"]


def _entities(ids, props="labels|claims|sitelinks"):
    if not ids:
        return {}
    url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&languages=fr|en"
           f"&props={props}&ids=" + "|".join(ids[:50]))
    return _json(url).get("entities", {})


def _search(title):
    """Identifiants Wikidata des résultats, en essayant des variantes du titre."""
    variants = dict.fromkeys([title, title.replace(" - ", ": "), title.replace(" - ", " "),
                              re.sub(r",\s*The\b", "", title)])
    for query in variants:
        url = ("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&type=item&limit=10"
               "&language=fr&uselang=fr&search=" + urllib.parse.quote(query))
        ids = [r["id"] for r in _json(url).get("search", [])]
        if ids:
            return ids
    return []


def find_wikidata(title, system):
    """(entité du jeu, libellés des entités liées) : un jeu vidéo au titre proche, de préférence
    au titre exact, sur la bonne console, et le plus connu (le plus d'articles Wikipédia)."""
    games = [e for e in _entities(_search(title)).values() if VIDEO_GAME in _ids(e, "P31")]
    if not games:
        return None, {}
    linked = sorted({i for e in games for prop in ("P400", "P136", "P178", "P123") for i in _ids(e, prop)[:6]})
    labels = {k: _label(v) for k, v in _entities(linked, "labels").items()}  # une seule requête
    wanted = systems.name(system).lower()

    def score(e):
        similar = difflib.SequenceMatcher(None, core.title_key(_label(e)), core.title_key(title)).ratio()
        platforms = [labels.get(p, "").lower() for p in _ids(e, "P400")]
        on_system = any(p and (wanted in p or p in wanted) for p in platforms)
        return (similar >= 0.95, similar >= 0.8, on_system, similar, len(e.get("sitelinks", {})))
    best = max(games, key=score)
    if score(best)[3] < 0.6:
        return None, {}
    return best, labels


def from_wikidata(game, title):
    entity, labels = find_wikidata(title, game.system)
    if not entity:
        return {}, None
    out = {}
    dates = [c["mainsnak"]["datavalue"]["value"]["time"] for c in entity.get("claims", {}).get("P577", [])
             if "datavalue" in c["mainsnak"]]
    if dates:
        out["year"] = min(d[1:5] for d in dates)
    for prop, target in (("P136", "genre"), ("P178", "developer"), ("P123", "publisher")):
        names = [labels[i] for i in _ids(entity, prop)[:2] if labels.get(i)]
        if names:
            out[target] = ", ".join(names)
    links = entity.get("sitelinks", {})
    wiki = ("fr", links["frwiki"]["title"]) if "frwiki" in links else (
        ("en", links["enwiki"]["title"]) if "enwiki" in links else None)
    return out, wiki


def wikipedia_summary(lang, title, limit=900):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_"))
    text = (_json(url).get("extract") or "").strip()
    if len(text) > limit:  # coupe proprement à la fin d'une phrase
        cut = text.rfind(". ", 0, limit)
        text = text[:cut + 1] if cut > 200 else text[:limit].rstrip() + "…"
    return text


# ---------------------------------------------------------------- assemblage

# mots-clés -> genre, pour les libellés détaillés (« jeu de plateforme en 3D » -> Plateforme)
GENRE_KEYWORDS = (("shoot", "Shoot'em up"), ("beat", "Beat'em All"), ("plate", "Plateforme"),
                  ("platform", "Plateforme"), ("course", "Course"), ("racing", "Course"),
                  ("combat", "Combat"), ("fighting", "Combat"), ("rôle", "Jeu de rôles"),
                  ("role", "Jeu de rôles"), ("tir", "Tir"), ("shooter", "Tir"), ("sport", "Sport"),
                  ("football", "Sport"), ("puzzle", "Puzzle"), ("réflexion", "Puzzle"),
                  ("stratégie", "Stratégie"), ("strategy", "Stratégie"), ("aventure", "Aventure"),
                  ("adventure", "Aventure"), ("simulation", "Simulation"), ("rythme", "Rythme"),
                  ("music", "Musique et Danse"), ("flipper", "Flipper"), ("pinball", "Flipper"),
                  ("action", "Action"))


def french_genre(value):
    """Genre d'internet -> genre de la carte (« Racing » -> « Course »)."""
    first = re.split(r"\s*[,/]\s*", value.strip())[0]
    if first.lower() in GENRES:
        return GENRES[first.lower()]
    for word, genre in GENRE_KEYWORDS:
        if word in first.lower():
            return genre
    return first[:1].upper() + first[1:]


def clean_title(game):
    """Titre lisible : « Mario Kart - Super Circuit (USA) » -> « Mario Kart - Super Circuit »."""
    return re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", core.DISC_RE.sub("", game.stem)).strip(" -") or game.stem


# ---------------------------------------------------------------- noms des jeux d'arcade

FBNEO_DAT = ("https://raw.githubusercontent.com/libretro/FBNeo/master/dats/"
             "FinalBurn%20Neo%20(ClrMame%20Pro%20XML%2C%20Arcade%20only).dat")
_arcade = {}


def parse_fbneo(text):
    """{nom de code: titre} depuis la liste FinalBurn Neo (« ffight » -> « Final Fight (World, set 1) »)."""
    return {m.group(1).lower(): html.unescape(m.group(2)) for m in
            re.finditer(r'<game name="([^"]+)"[^>]*>\s*<description>([^<]*)</description>', text)}


def arcade_titles():
    """Titres des jeux d'arcade par nom de code (liste téléchargée puis gardée un mois)."""
    if not _arcade:
        path = os.path.join(CACHE_DIR, "fbneo.dat")
        text = ""
        if os.path.isfile(path) and time.time() - os.path.getmtime(path) < CACHE_DAYS * 86400:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        else:
            try:
                text = _get(FBNEO_DAT, 60).decode("utf-8", "replace")
                os.makedirs(CACHE_DIR, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError:
                if os.path.isfile(path):
                    with open(path, encoding="utf-8") as f:
                        text = f.read()
        _arcade.update(parse_fbneo(text))
    return _arcade


def arcade_name(game):
    """Vrai titre d'un jeu d'arcade affiché sous son nom de code, avec ou sans numéro devant
    (« 010 ffight » -> « Final Fight »). None si le nom est déjà un vrai titre."""
    if game.system.lower() not in core.ARCADE_SYSTEMS:
        return None
    name = game.name.strip()
    code = re.sub(r"^\d+\s+", "", name)
    if code.lower() != game.stem.lower():
        return None
    title = arcade_titles().get(game.stem.lower())
    new = re.sub(r"\s*\(.*$", "", title).strip() if title else code
    return new if new and new != name else None


def missing_fields(game):
    """Champs vides de la fiche (ceux qu'on cherchera à compléter)."""
    i = game.info
    wanted = {"year": not i.get("releasedate"), "genre": not i.get("genre"), "developer": not i.get("developer"),
              "publisher": not i.get("publisher"), "players": not i.get("players"), "desc": not i.get("desc"),
              "name": game.name == game.stem}
    return {k for k, v in wanted.items() if v}


def lookup(game):
    """Valeurs trouvées pour les champs vides (dict pour core.set_info). Ne lève jamais."""
    todo = missing_fields(game)
    if not todo:
        return {}
    local = from_port_json(game)  # port PortMaster : son port.json d'abord (sans internet)
    found, title = dict(local), local.get("name") or clean_title(game)
    for source in (lambda: from_libretro(game), lambda: _wiki(game, title, todo - set(found), found)):
        try:
            for k, v in source().items():
                found.setdefault(k, v)
        except Exception:  # réseau, format inattendu… : on garde ce qu'on a et on continue
            continue
    if "genre" in found:
        found["genre"] = french_genre(found["genre"])
    if "name" in todo:
        found["name"] = title
    return {k: v for k, v in found.items() if k in todo and v}


def _wiki(game, title, todo, found):
    if not todo:
        return {}
    data, wiki = from_wikidata(game, title)
    if "desc" in todo and wiki:
        try:
            data["desc"] = wikipedia_summary(*wiki)
        except Exception:
            pass
    return data


def from_port_json(game):
    """Fiche d'un port PortMaster d'après son port.json : titre, description, genre."""
    attr = core.port_info(game.path).get("attr") or {}
    out = {"name": attr.get("title"), "desc": attr.get("desc"),
           "genre": (attr.get("genres") or [""])[0]}
    return {k: v.strip() for k, v in out.items() if isinstance(v, str) and v.strip()}


def needs_images(game):
    """Le jeu n'a pas d'image dans sa fiche (pour un port, ses images locales ne sont pas encore inscrites)."""
    if game.system.lower() == "ports" and core.port_media(game):
        return not game.media.get("image")
    return not core.cover_for(game)


def incomplete(games):
    """Jeux à qui il manque une description, une année, un genre ou une image."""
    return [g for g in games if {"desc", "year", "genre"} & missing_fields(g) or needs_images(g)]
