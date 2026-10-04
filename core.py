"""Logique métier (sans interface graphique).

Lit une partition EASYROMS d'ArkOS (R36S) : un dossier par système, chacun avec
un gamelist.xml (EmulationStation / Skraper) et ses médias. Permet de lister les
jeux, retrouver leurs images et les supprimer proprement (ROM + fichiers liés +
médias + entrée du gamelist.xml).
"""
import ctypes
import datetime
import json
import os
import re
import shutil
import string
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import journal
from i18n import _

# Dossiers à la racine qui ne sont pas des systèmes de jeux
NOT_SYSTEMS = {"bios", "themes", "backup", "launchimages", "tools", "bgmusic",
               "system volume information", ".trash-1000"}

# Sous-dossiers d'un système qui ne contiennent pas de jeux
NOT_GAME_SUBDIRS = {"media", "downloaded_images", "downloaded_videos", "images", "image",
                    "videos", "manuals", "snap", "boxart", "cartart", "wheel", "savestates",
                    "saves", "backup", "cheats", "logs_arrm", "slot2", "fba", "fbneo",
                    "mame2003", "mame2003-plus", "mame2010", "controls", "psp", "ppsspp",
                    "savedata"}

# Systèmes où seuls les fichiers à la racine sont des jeux (les sous-dossiers = données),
# avec les seules extensions qui comptent comme jeux
ROOT_ONLY_SYSTEMS = {"ports": {".sh"}}

# Extensions qui ne sont jamais des jeux
NOT_GAME_EXT = {".xml", ".txt", ".bak", ".old", ".png", ".jpg", ".jpeg", ".gif", ".bmp",
                ".webp", ".mp4", ".avi", ".cfg", ".ini", ".log", ".nfo", ".pdf", ".db", ".auto",
                ".bat", ".json"}

# Fichiers de sauvegarde (même nom que la ROM)
SAVE_RE = re.compile(r"\.(srm|sav|rtc|mcd|dsv|nv|fs|sra|eep|fla|mpk|state\d*|state\.auto)$", re.I)

# Quand plusieurs fichiers ont le même nom (ex. .ccd/.img/.sub), lequel représente le jeu
PRIMARY_EXT = (".m3u", ".cue", ".ccd", ".gdi", ".cdi", ".chd", ".pbp", ".iso")

# Balises médias du gamelist.xml (supprimées avec le jeu)
MEDIA_TAGS = ("image", "thumbnail", "box", "boxback", "marquee", "wheel", "video", "fanart",
              "titleshot", "mix", "manual", "map")
# Ordre de préférence pour l'aperçu
IMAGE_TAGS = ("image", "thumbnail", "box", "titleshot", "mix", "marquee", "wheel")
COVER_TAGS = ("box", "thumbnail", "image", "mix", "marquee", "wheel")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

# Dossiers où chercher des médias nommés comme la ROM (jeux sans entrée gamelist)
FALLBACK_MEDIA_DIRS = ("downloaded_images", "downloaded_videos", "media/images", "media/box3d",
                       "media/boxes", "media/wheels", "media/videos", "images", "image",
                       "snap", "boxart")

INFO_TAGS = ("desc", "developer", "publisher", "releasedate", "genre", "players", "rating",
             "playcount", "lastplayed")


@dataclass
class Game:
    system: str
    name: str
    path: str                                    # chemin absolu de la ROM (fichier ou dossier)
    sysdir: str                                  # dossier du système
    media: dict = field(default_factory=dict)    # balise -> chemin absolu
    info: dict = field(default_factory=dict)     # desc, developer, ...
    in_gamelist: bool = True
    size: int = 0
    favorite: bool = False

    @property
    def filename(self):
        return os.path.relpath(self.path, self.sysdir)

    @property
    def rating(self):
        """Note EmulationStation entre 0 et 1 (None si absente)."""
        try:
            return min(max(float(self.info.get("rating", "")), 0.0), 1.0)
        except ValueError:
            return None

    @property
    def playcount(self):
        """Nombre de parties lancées (compté par la console)."""
        try:
            return int(self.info.get("playcount") or 0)
        except ValueError:
            return 0

    @property
    def lastplayed(self):
        """Date de la dernière partie (datetime) ou None."""
        try:
            return datetime.datetime.strptime(self.info.get("lastplayed", "")[:15], "%Y%m%dT%H%M%S")
        except ValueError:
            return None

    @property
    def stem(self):
        return os.path.splitext(os.path.basename(self.path))[0]


def same(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


# ---------------------------------------------------------------- lecteurs

def volume_label(root):
    buf = ctypes.create_unicode_buffer(261)
    try:
        if ctypes.windll.kernel32.GetVolumeInformationW(root, buf, 261, None, None, None, None, 0):
            return buf.value
    except (AttributeError, OSError):
        pass
    return ""


# Dossiers typiques d'une partition EASYROMS d'ArkOS (au moins 2 doivent être présents)
EASYROMS_DIRS = {"bios", "themes", "ports", "gb", "gbc", "gba", "nes", "snes", "sfc", "n64", "nds", "psx", "psp",
                 "megadrive", "genesis", "mastersystem", "gamegear", "segacd", "saturn", "dreamcast", "pcengine",
                 "neogeo", "mame", "fbneo", "arcade", "cps1", "cps2", "cps3", "atarilynx", "atari2600"}


def looks_like_easyroms(root):
    """Vérification rapide (un seul listage) : la partition ressemble-t-elle à une carte ArkOS ?"""
    try:
        names = {e.name.lower() for e in os.scandir(root) if e.is_dir()}
    except OSError:
        return False
    return len(names & EASYROMS_DIRS) >= 2


def list_drives():
    """[(racine, libellé, est_easyroms)] : lecteurs (Windows) ou supports montés (Linux)."""
    out = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = f"{letter}:\\"
            if os.path.isdir(root):
                out.append((root, volume_label(root), looks_like_easyroms(root)))
        return out
    user = os.environ.get("USER", "")
    for base in (f"/media/{user}", f"/run/media/{user}", "/media", "/mnt"):
        try:
            entries = sorted(e.path for e in os.scandir(base) if e.is_dir())
        except OSError:
            continue
        for root in entries:
            if os.path.ismount(root) and all(r != root for r, _x, _x in out):
                out.append((root, os.path.basename(root), looks_like_easyroms(root)))
    return out


def disk_usage(root):
    try:
        return shutil.disk_usage(root)
    except OSError:
        return None


# ---------------------------------------------------------------- lecture

def resolve_path(root, sysdir, raw):
    """Convertit un chemin du gamelist.xml en chemin Windows (None si hors partition)."""
    raw = (raw or "").strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith("./"):
        return os.path.normpath(os.path.join(sysdir, raw[2:]))
    m = re.match(r"^/roms2?/(.*)$", raw)
    if m:
        return os.path.normpath(os.path.join(root, m.group(1)))
    if raw.startswith(("/", "~")):
        return None
    return os.path.normpath(os.path.join(sysdir, raw))


def components(path):
    """Fichiers référencés par un .cue / .gdi / .m3u (pistes .bin, disques...)."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".cue", ".gdi", ".m3u") or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    if ext == ".cue":
        names = re.findall(r'^\s*FILE\s+"?(.+?)"?\s+\w+\s*$', text, re.M | re.I)
    elif ext == ".gdi":
        names = []
        for line in text.splitlines()[1:]:
            m = re.match(r'\s*\d+\s+\d+\s+\d+\s+\d+\s+(?:"([^"]+)"|(\S+))', line)
            if m:
                names.append(m.group(1) or m.group(2))
    else:
        names = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    out = []
    folder = os.path.dirname(path)
    for n in names:
        p = os.path.normpath(os.path.join(folder, n))
        if os.path.exists(p) and not same(p, path):
            out.append(p)
            if ext == ".m3u":  # chaque disque, avec ses pistes et ses .img/.sub
                out += components(p) + siblings(p)
    return out


def is_not_game(name):
    return (name.startswith(".") or name.lower().startswith("scan_for_new_games")
            or os.path.splitext(name)[1].lower() in NOT_GAME_EXT or bool(SAVE_RE.search(name)))


_listing_cache = {}


def listing(folder):
    """Noms des fichiers d'un dossier (mis en cache, vidé après une suppression)."""
    key = os.path.normcase(folder)
    if key not in _listing_cache:
        try:
            _listing_cache[key] = [e.name for e in os.scandir(folder) if e.is_file()]
        except OSError:
            _listing_cache[key] = []
    return _listing_cache[key]


def clear_cache():
    _listing_cache.clear()
    _cover_cache.clear()
    _port_cache.clear()


def siblings(path):
    """Fichiers du même dossier portant le même nom (ex. jeu.ccd -> jeu.img, jeu.sub)."""
    folder, base = os.path.split(path)
    prefix = os.path.splitext(base)[0].lower() + "."
    return [os.path.join(folder, n) for n in listing(folder)
            if n.lower().startswith(prefix) and n.lower() != base.lower() and not is_not_game(n)]


_port_cache = {}


def port_manifests(ports_folder):
    """{nom du script .sh en minuscules: (dossier du port, port.json)} d'après les port.json de PortMaster
    (leur liste « items » donne exactement les fichiers du port, ex. ["AM2R.sh", "am2r/"])."""
    key = os.path.normcase(ports_folder)
    if key not in _port_cache:
        found = {}
        try:
            dirs = [e.path for e in os.scandir(ports_folder) if e.is_dir()]
        except OSError:
            dirs = []
        for d in dirs:
            try:
                with open(os.path.join(d, "port.json"), encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            items = data.get("items") or []
            folders = [os.path.join(ports_folder, i.strip("/")) for i in items if i.endswith("/")]
            for script in (i for i in items if i.lower().endswith(".sh")):
                found[script.lower()] = (folders[0] if folders else d, data)
        _port_cache[key] = found
    return _port_cache[key]


def port_info(path):
    """Contenu du port.json du port (titre, description, instructions…), ou {}."""
    entry = port_manifests(os.path.dirname(path)).get(os.path.basename(path).lower())
    return entry[1] if entry else {}


def port_dir(path):
    """Dossier de données d'un port PortMaster : d'après son port.json, sinon d'après la ligne
    GAMEDIR= / GAME_DIR= du script (« $PORTDIR/augustus », « ${PORTDIR}/Half-Life »…)."""
    if not path.lower().endswith(".sh") or not os.path.isfile(path):
        return None
    folder = os.path.dirname(path)
    entry = port_manifests(folder).get(os.path.basename(path).lower())
    if entry and os.path.isdir(entry[0]):
        return entry[0]
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    existing = {n.lower(): n for n in os.listdir(folder) if os.path.isdir(os.path.join(folder, n))}
    for value in re.findall(r'^\s*(?:GAMEDIR|GAME_DIR)="?([^"\n]+?)"?\s*$', text, re.M):
        last = value.rstrip("/").split("/")[-1].strip("{}$ ")
        if last.lower() in existing and last.lower() not in ("ports", "portmaster"):
            return os.path.join(folder, existing[last.lower()])
    return None


def primary_rank(path):
    ext = os.path.splitext(path)[1].lower()
    return PRIMARY_EXT.index(ext) if ext in PRIMARY_EXT else len(PRIMARY_EXT)


def candidate_files(sysdir, root_only=False):
    """Fichiers pouvant être des jeux : racine du système + sous-dossiers (1 niveau)."""
    out = []
    try:
        entries = list(os.scandir(sysdir))
    except OSError:
        return out
    for e in entries:
        if e.is_file():
            out.append(e.path)
        elif (not root_only and e.is_dir() and e.name.lower() not in NOT_GAME_SUBDIRS
              and not e.name.startswith(".")):  # dossiers cachés ignorés, comme sur la console
            try:
                out += [s.path for s in os.scandir(e.path) if s.is_file()]
            except OSError:
                pass
    return out


def path_size(p):
    if os.path.isdir(p):
        total = 0
        for dirpath, _x, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
        return total
    try:
        return os.path.getsize(p)
    except OSError:
        return 0


def in_data_dir(path, sysdir):
    """True si le fichier est dans un dossier qui ne contient pas de jeux (media, saves…)."""
    parts = os.path.relpath(path, sysdir).split(os.sep)[:-1]
    return any(p.lower() in NOT_GAME_SUBDIRS for p in parts)


def _gamelist_games(root, system, sysdir):
    """Jeux décrits dans le gamelist.xml dont la ROM existe."""
    gl = os.path.join(sysdir, "gamelist.xml")
    if not os.path.isfile(gl):
        return []
    try:
        entries = ET.parse(gl).getroot().findall("game")
    except ET.ParseError:
        return []
    games, known = [], set()
    for el in entries:
        p = resolve_path(root, sysdir, el.findtext("path"))
        if not p or not os.path.exists(p) or os.path.normcase(p) in known:
            continue  # entrée orpheline (ROM absente) ou doublon
        if in_data_dir(p, sysdir):
            continue  # ex. sauvegarde PSP (ppsspp/SAVEDATA) inscrite par erreur par un scraper
        known.add(os.path.normcase(p))
        media = {tag: mp for tag in MEDIA_TAGS
                 if (mp := resolve_path(root, sysdir, el.findtext(tag)))}
        info = {t: (el.findtext(t) or "").strip() for t in INFO_TAGS}
        name = (el.findtext("name") or "").strip() or os.path.splitext(os.path.basename(p))[0]
        fav = (el.findtext("favorite") or "").strip().lower() == "true"
        games.append(Game(system, name, p, sysdir, media, info, True, favorite=fav))
    return games


def _unlisted_games(system, sysdir, listed):
    """Jeux présents sur la carte mais absents du gamelist.xml."""
    only_ext = ROOT_ONLY_SYSTEMS.get(system.lower())
    files = sorted(candidate_files(sysdir, only_ext is not None), key=lambda f: (primary_rank(f), f.lower()))  # même ordre sous Windows et Linux
    if only_ext:
        files = [f for f in files if os.path.splitext(f)[1].lower() in only_ext]
    used = {os.path.normcase(p) for g in listed for p in game_files(g)}
    for f in files:
        used.update(os.path.normcase(c) for c in components(f))
    games = []
    for f in files:
        if os.path.normcase(f) in used or is_not_game(os.path.basename(f)):
            continue
        g = Game(system, os.path.splitext(os.path.basename(f))[0], f, sysdir, in_gamelist=False)
        games.append(g)
        used.update(os.path.normcase(p) for p in game_files(g))
    return games


def load_system(root, system):
    sysdir = os.path.join(root, system)
    games = _gamelist_games(root, system, sysdir)
    games += _unlisted_games(system, sysdir, games)
    for g in games:
        g.size = sum(path_size(p) for p in game_files(g))
    return games


def list_systems(root):
    try:
        return sorted((e.name for e in os.scandir(root)
                       if e.is_dir() and e.name.lower() not in NOT_SYSTEMS
                       and not e.name.startswith(".")), key=str.lower)
    except OSError:
        return []


MEDIA_DIRS = {"media", "downloaded_images", "downloaded_videos", "images", "image", "videos",
              "snap", "boxart", "cartart", "wheel", "manuals"}
VIDEO_EXT = {".mp4", ".avi", ".mkv", ".webm", ".mov"}


def media_usage(root):
    """Place occupée par les images et les vidéos (dossiers de médias de chaque système)."""
    usage = {"images": 0, "videos": 0}
    for system in list_systems(root):
        try:
            subdirs = [e.path for e in os.scandir(os.path.join(root, system))
                       if e.is_dir() and e.name.lower() in MEDIA_DIRS]
        except OSError:
            continue
        for sub in subdirs:
            for dirpath, _x, files in os.walk(sub):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    kind = "images" if ext in IMAGE_EXT else "videos" if ext in VIDEO_EXT else None
                    if kind:
                        try:
                            usage[kind] += os.path.getsize(os.path.join(dirpath, f))
                        except OSError:
                            pass
    return usage


def load_all(root):
    """{système: [Game]} pour les systèmes qui contiennent au moins un jeu."""
    clear_cache()
    result = {}
    for system in list_systems(root):
        games = load_system(root, system)
        if games:
            result[system] = games
    return result


# ---------------------------------------------------------------- fichiers d'un jeu

def game_files(game):
    """La ROM et ce qui va avec : pistes d'un .cue, .img/.sub de même nom, dossier d'un port."""
    if os.path.isdir(game.path):
        return [game.path]
    files = [game.path] + components(game.path) + siblings(game.path)
    pdir = port_dir(game.path)
    if pdir:
        files.append(pdir)
    unique = {}
    for p in files:
        unique.setdefault(os.path.normcase(os.path.normpath(p)), p)
    return list(unique.values())


_SKRAPER_HASH = re.compile(r" [0-9A-Fa-f]{32}$")  # Skraper : « Jeu (USA) 61410ADC…AFF.mp4 »


def _by_stem(folder, stem):
    """Fichiers nommés comme la ROM, avec ou sans l'empreinte ajoutée par Skraper."""
    stem = stem.lower()
    return [os.path.join(folder, n) for n in listing(folder)
            if _SKRAPER_HASH.sub("", os.path.splitext(n)[0]).lower() == stem]


def fallback_media(game):
    out = []
    for sub in FALLBACK_MEDIA_DIRS:
        out += _by_stem(os.path.join(game.sysdir, sub), game.stem)
    return out


_cover_cache = {}


def cover_for(game):
    """Jaquette (boîte) en priorité, pour la vue grille (mise en cache)."""
    if game.path not in _cover_cache:
        _cover_cache[game.path] = image_for(game, COVER_TAGS)
    return _cover_cache[game.path]


def image_for(game, tags=None):
    for tag in tags or IMAGE_TAGS:
        p = game.media.get(tag)
        if p and os.path.isfile(p) and os.path.splitext(p)[1].lower() in IMAGE_EXT:
            return p
    for p in fallback_media(game):
        if os.path.splitext(p)[1].lower() in IMAGE_EXT:
            return p
    return None


def video_for(game):
    """Vidéo de présentation du jeu (fiche du gamelist, sinon fichier nommé comme la ROM)."""
    p = game.media.get("video")
    if p and os.path.isfile(p):
        return p
    return next((p for p in fallback_media(game) if os.path.splitext(p)[1].lower() in VIDEO_EXT), None)


def save_files(game):
    if os.path.isdir(game.path):
        return []
    folder = os.path.dirname(game.path)
    try:
        return [e.path for e in os.scandir(folder)
                if e.is_file() and e.name.lower().startswith(game.stem.lower() + ".")
                and SAVE_RE.search(e.name)]
    except OSError:
        return []


def files_to_delete(game, system_games, with_saves=False):
    """Liste des fichiers qui seront supprimés avec ce jeu."""
    # ce qui appartient aussi à un autre jeu (sa ROM, ses médias, son dossier de port) est protégé
    protected = set()
    for g in system_games:
        if not same(g.path, game.path):  # même jeu (même chargé deux fois) : pas protégé
            protected.add(os.path.normcase(g.path))
            protected.update(os.path.normcase(p) for p in g.media.values())
            pdir = port_dir(g.path)
            if pdir:
                protected.add(os.path.normcase(pdir))
    files = game_files(game) + [p for p in game.media.values() if os.path.isfile(p)]
    files += fallback_media(game)
    if with_saves:
        files += save_files(game)
    seen, out = set(), []
    for p in map(os.path.normpath, files):
        k = os.path.normcase(p)
        if k not in seen and k not in protected and os.path.exists(p):
            seen.add(k)
            out.append(p)
    # inutile de lister un fichier situé dans un dossier déjà supprimé
    dirs = [os.path.normcase(p) + os.sep for p in out if os.path.isdir(p)]
    return [p for p in out if not any(os.path.normcase(p).startswith(d) for d in dirs)]


# ---------------------------------------------------------------- suppression

def remove_from_gamelist(root, game):
    gl = os.path.join(game.sysdir, "gamelist.xml")
    if not os.path.isfile(gl):
        return
    tree = ET.parse(gl)
    top = tree.getroot()
    removed = False
    for el in top.findall("game"):
        p = resolve_path(root, game.sysdir, el.findtext("path"))
        if p and same(p, game.path):
            top.remove(el)
            removed = True
    if removed:
        _write_gamelist(gl, tree)


def _write_gamelist(gl, tree):
    """Enregistre un gamelist.xml (l'ancienne version est gardée par le journal : annulable)."""
    ET.indent(tree, "\t")
    journal.write_file(gl, lambda p: tree.write(p, encoding="utf-8", xml_declaration=True))


# ---------------------------------------------------------------- modification des gamelist

def _key_of(path):
    return os.path.normcase(os.path.normpath(path))


def edit_gamelist(root, sysdir, fn):
    """Ouvre le gamelist.xml du système (créé s'il manque), appelle fn(racine_xml, entrées)
    où entrées = {chemin ROM normalisé: élément <game>}, puis l'enregistre (annulable).
    Retourne la liste des erreurs."""
    gl = os.path.join(sysdir, "gamelist.xml")
    try:
        tree = ET.parse(gl) if os.path.isfile(gl) else ET.ElementTree(ET.Element("gameList"))
        top = tree.getroot()
        entries = {}
        for el in top.findall("game"):
            p = resolve_path(root, sysdir, el.findtext("path"))
            if p:
                entries[_key_of(p)] = el
        fn(top, entries)
        _write_gamelist(gl, tree)
    except (OSError, ET.ParseError) as e:
        return [f"{gl} : {e}"]
    return []


def update_gamelist(root, games, apply, create=True):
    """Modifie l'entrée <game> de chaque jeu : apply(element, jeu).
    Un jeu absent du gamelist.xml y est ajouté si create. Un seul écrit par système.
    Retourne la liste des erreurs."""
    errors = []
    by_system = {}
    for g in games:
        by_system.setdefault(g.sysdir, []).append(g)
    for sysdir, group in by_system.items():
        def fn(top, entries, group=group, sysdir=sysdir):
            for g in group:
                el = entries.get(_key_of(g.path))
                if el is None:
                    if not create:
                        continue
                    el = ET.SubElement(top, "game")
                    ET.SubElement(el, "path").text = "./" + _rel(g.path, sysdir)
                    ET.SubElement(el, "name").text = g.name
                    g.in_gamelist = True
                apply(el, g)
        errors += edit_gamelist(root, sysdir, fn)
    return errors


def _rel(path, sysdir):
    return os.path.relpath(path, sysdir).replace(os.sep, "/")


def _set_tag(el, tag, text):
    for old in el.findall(tag):
        el.remove(old)
    if text is not None:
        ET.SubElement(el, tag).text = text


def set_favorites(root, games, value):
    """Ajoute (value=True) ou retire des favoris, comme le fait EmulationStation :
    balise <favorite>true</favorite> dans le gamelist.xml du système."""
    def apply(el, g):
        _set_tag(el, "favorite", "true" if value else None)
        g.favorite = value
    return update_gamelist(root, games, apply, create=value)


def set_media(root, updates):
    """Inscrit des images dans le gamelist.xml. updates = [(jeu, {balise: chemin})]."""
    media = {id(g): m for g, m in updates}

    def apply(el, g):
        for tag, path in media[id(g)].items():
            _set_tag(el, tag, "./" + _rel(path, g.sysdir))
            g.media[tag] = path
    errors = update_gamelist(root, [g for g, m in updates if m], apply)
    clear_cache()
    return errors


def set_info(root, game, values):
    """Modifie la fiche du jeu. values : name, rating (0..1 ou None), year, genre,
    developer, publisher, players, desc. Une valeur vide retire la balise."""
    old_year = game.info.get("releasedate", "")[:4]

    def apply(el, g):
        for tag in ("name", "genre", "developer", "publisher", "players", "desc"):
            if tag in values:
                text = (values[tag] or "").strip()
                _set_tag(el, tag, text or None)
                if tag == "name":
                    g.name = text or g.stem
                else:
                    g.info[tag] = text
        if "rating" in values:
            r = values["rating"]
            text = None if r is None else f"{r:g}"
            _set_tag(el, "rating", text)
            g.info["rating"] = text or ""
        year = (values.get("year") or "").strip()
        if "year" in values and year != old_year:
            date = f"{year}0101T000000" if re.fullmatch(r"\d{4}", year) else None
            _set_tag(el, "releasedate", date)
            g.info["releasedate"] = date or ""
    return update_gamelist(root, [game], apply)


# ---------------------------------------------------------------- déplacement

def move_game(root, game, target_system, system_games):
    """Déplace un jeu (ROM + fichiers liés + sauvegardes + médias) vers un autre système
    et transfère sa fiche d'un gamelist.xml à l'autre. Retourne la liste des erreurs."""
    dest_dir = os.path.join(root, target_system)
    rom_dir = os.path.dirname(game.path)
    protected = {_key_of(p) for g in system_games if not same(g.path, game.path) for p in g.media.values()}

    # ROM et ce qui l'accompagne : même position relative par rapport au dossier de la ROM
    plan = [(p, os.path.join(dest_dir, os.path.relpath(p, rom_dir)))
            for p in dict.fromkeys(game_files(game) + save_files(game))]
    # médias : même chemin relatif dans le dossier du système (media/images/…)
    media = {}
    for tag, p in game.media.items():
        if os.path.isfile(p):
            media[tag] = (p, os.path.join(dest_dir, os.path.relpath(p, game.sysdir)))
    known = {_key_of(src) for src, _x in media.values()}
    extra = [(p, os.path.join(dest_dir, os.path.relpath(p, game.sysdir)))
             for p in fallback_media(game) if _key_of(p) not in known]

    clash = [d for _x, d in plan + list(media.values()) + extra if os.path.exists(d)]
    if clash:
        return [_("{file} : existe déjà dans {system}", file=os.path.basename(clash[0]), system=target_system)]

    errors = []
    for src, dst in plan + extra + list(media.values()):
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if _key_of(src) in protected:
                journal.copy(src, dst)  # image partagée avec un autre jeu : on la copie
            else:
                journal.move(src, dst)
        except OSError as e:
            errors.append(f"{src} : {e}")
    clear_cache()
    if errors or not game.in_gamelist:
        return errors

    new_rom = os.path.join(dest_dir, os.path.basename(game.path))
    moved = {}

    def take(top, entries):
        el = entries.get(_key_of(game.path))
        if el is not None:
            top.remove(el)
            moved["el"] = el
    errors += edit_gamelist(root, game.sysdir, take)

    def put(top, entries):
        el = moved.get("el")
        if el is None:
            return
        old = entries.get(_key_of(new_rom))
        if old is not None:
            top.remove(old)
        _set_tag(el, "path", "./" + _rel(new_rom, dest_dir))
        for tag, (_x, dst) in media.items():
            _set_tag(el, tag, "./" + _rel(dst, dest_dir))
        top.append(el)
    errors += edit_gamelist(root, dest_dir, put)
    return errors


# ---------------------------------------------------------------- doublons

def title_key(name):
    """Titre simplifié pour comparer deux jeux : sans (région) [tags], ponctuation, « The »."""
    t = re.sub(r"\(.*?\)|\[.*?\]", "", name).lower().replace(", the", "").replace("&", "and")
    t = re.sub(r"^\s*the\s+", "", t)
    return re.sub(r"[^a-z0-9]", "", t)


ARCADE_SYSTEMS = {"neogeo", "cps1", "cps2", "cps3", "mame", "mame2003", "mame2010", "fbneo", "arcade",
                  "atomiswave", "naomi", "daphne"}
DISC_RE = re.compile(r"\s*-?\s*[\(\[]\s*(?:disc|disk|cd|disque)\s*(\d+)(?:\s*(?:of|sur|/)\s*\d+)?\s*[\)\]]", re.I)


def find_duplicates(games_by_system):
    """Jeux présents plusieurs fois dans un même système (même titre, autre version ou nom).
    Les disques d'un même jeu ne comptent pas comme des doublons."""
    dups = []
    for system, games in games_by_system.items():
        if system.lower() in ARCADE_SYSTEMS:
            continue  # en arcade, deux versions = souvent parent + clone, dont l'un a besoin de l'autre
        groups = {}
        for g in games:
            if DISC_RE.search(g.stem):
                continue
            key = title_key(g.stem)
            if key:
                groups.setdefault(key, []).append(g)
        dups += [g for group in groups.values() if len(group) > 1 for g in group]
    return dups


# ---------------------------------------------------------------- vidéos

def video_files(root, system):
    """Vidéos de présentation d'un système (dans ses dossiers de médias)."""
    sysdir = os.path.join(root, system)
    out = []
    try:
        subdirs = [e.path for e in os.scandir(sysdir) if e.is_dir() and e.name.lower() in MEDIA_DIRS]
    except OSError:
        return out
    for sub in subdirs:
        for dirpath, _x, files in os.walk(sub):
            out += [os.path.join(dirpath, f) for f in files if os.path.splitext(f)[1].lower() in VIDEO_EXT]
    return out


def delete_videos(root, system, games):
    """Supprime les vidéos d'un système et retire les balises <video> de son gamelist."""
    errors = []
    for p in video_files(root, system):
        try:
            journal.remove(p)
        except OSError as e:
            errors.append(f"{p} : {e}")

    def strip(top, entries):
        for el in top.findall("game"):
            for v in el.findall("video"):
                el.remove(v)
    if os.path.isfile(os.path.join(root, system, "gamelist.xml")):
        errors += edit_gamelist(root, os.path.join(root, system), strip)
    for g in games:
        g.media.pop("video", None)
    return errors


def delete_game(root, game, files):
    """Supprime les fichiers puis l'entrée du gamelist. Retourne la liste des erreurs."""
    errors = []
    for p in files:
        try:
            if os.path.lexists(p):
                journal.remove(p)
        except OSError as e:
            errors.append(f"{p} : {e}")
    clear_cache()
    if game.in_gamelist and not os.path.exists(game.path):
        try:
            remove_from_gamelist(root, game)
        except (OSError, ET.ParseError) as e:
            errors.append(f"gamelist.xml ({game.system}) : {e}")
    return errors
