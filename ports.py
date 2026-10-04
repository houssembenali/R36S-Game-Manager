"""PortMaster : ports installés (infos locales) et catalogue en ligne (installation, mises à jour).

- Chaque port installé a un port.json (titre, description, instructions, images, et dans
  « status » l'empreinte md5 de la version installée).
- Le catalogue officiel (ports.json, ~1400 ports) donne pour chaque port sa description, son
  image, s'il est « prêt à jouer » (rtr : aucun fichier du jeu original à fournir), sa taille,
  son lien de téléchargement et l'empreinte de sa dernière version.
- Installer = déposer le .zip dans ports/PortMaster/autoinstall : PortMaster l'installe lui-même
  au prochain lancement sur la console (il ajoute aussi les bibliothèques dont le port a besoin).
"""
import hashlib
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field

import core
import journal
import net
import paths

CATALOG_URL = "https://github.com/PortsMaster/PortMaster-New/releases/latest/download/ports.json"
GUI_RELEASE = "https://api.github.com/repos/PortsMaster/PortMaster-GUI/releases/latest"
STATS_URL = "https://raw.githubusercontent.com/PortsMaster/PortMaster-Info/main/port_stats.json"
STATS_CACHE = paths.data("cache", "portmaster-stats.json")
IMAGE_URL = "https://raw.githubusercontent.com/PortsMaster/PortMaster-New/main/ports/{dir}/{file}"
CACHE = paths.data("cache", "portmaster-ports.json")
CACHE_HOURS = 12
ARCHS = {"aarch64", "armhf"}  # processeurs que la R36S sait faire tourner
IGNORED_DIRS = {"portmaster", "autoinstall"} | core.MEDIA_DIRS
# exigences du catalogue que la R36S (RK3326, 1 Go, ArkOS, OpenGL ES) ne remplit pas
UNSUITED = ("power", "ultra", "2gb", "opengl", "!arkos")
STORES = {"steam": "Steam", "gog": "GOG", "itch.io": "itch.io", "itch": "itch.io", "github": "GitHub"}


@dataclass
class Port:
    zip: str           # nom du .zip, identifiant du port (ex. « sprout.zip »)
    title: str
    desc: str
    inst: str          # instructions (fichiers du jeu à fournir…)
    genres: list
    porter: list
    rtr: bool          # prêt à jouer
    paid: bool         # le jeu original est payant
    size: int
    url: str
    md5: str
    updated: str       # date de la dernière version
    added: str         # date d'arrivée du port dans PortMaster
    screenshot: str    # URL de la capture
    runtimes: list     # bibliothèques nécessaires (ex. « dotnet-8.0.12.squashfs »)
    stores: list = field(default_factory=list)  # [(boutique, lien)] où trouver le jeu original
    reqs: list = field(default_factory=list)    # exigences (« power », « 2gb »…)
    exp: bool = False                           # port expérimental
    downloads: int = 0                          # nombre de téléchargements (popularité)
    rating: float = 0.0                         # note du jeu original (LaunchBox), sur 5
    votes: int = 0

    @property
    def unsuited(self):
        """Exigences que la R36S ne remplit pas (voir UNSUITED)."""
        return [r for r in self.reqs if r.lower() in UNSUITED]

    @property
    def key(self):
        return self.zip.lower()


# ---------------------------------------------------------------- catalogue

def _parse(data):
    out = []
    for name, p in data.get("ports", {}).items():
        a, src = p.get("attr", {}), p.get("source", {})
        if a.get("arch") and not ARCHS & set(a["arch"]):
            continue  # port réservé à d'autres processeurs (x86…)
        shot = (a.get("image") or {}).get("screenshot")
        out.append(Port(name, a.get("title") or name, a.get("desc") or "", a.get("inst") or "", a.get("genres") or [],
                        a.get("porter") or [], bool(a.get("rtr")), a.get("availability") == "paid",
                        src.get("size") or 0, src.get("url") or "", src.get("md5") or "", src.get("date_updated") or "",
                        src.get("date_added") or src.get("date_updated") or "",
                        IMAGE_URL.format(dir=name[:-4], file=shot) if shot else "", a.get("runtime") or [],
                        _stores(a), [r for r in a.get("reqs") or [] if r], bool(a.get("exp"))))
    return sorted(out, key=lambda p: p.title.lower())


def _stores(attr):
    """[(nom de la boutique, lien)] d'après « store » d'un port.json ou du catalogue."""
    out = []
    for s in attr.get("store") or []:
        url = (s or {}).get("gameurl") or ""
        if url.startswith("http"):
            name = (s.get("name") or "").strip()
            out.append((STORES.get(name.lower(), name or url.split("/")[2]), url))
    return out


_cached = {}


def cached_catalog():
    """Catalogue déjà téléchargé (sans réseau), [] s'il n'y en a pas encore."""
    try:
        mtime = os.path.getmtime(CACHE)
        if _cached.get("mtime") != mtime:
            with open(CACHE, encoding="utf-8") as f:
                _cached.update(mtime=mtime, ports=_parse(json.load(f)))
        return _cached["ports"]
    except (OSError, ValueError):
        return []


def store_links(game):
    """[(boutique, lien)] du jeu original d'un port installé : port.json, sinon catalogue déjà téléchargé."""
    info = core.port_info(game.path)
    links = _stores(info.get("attr") or {})
    if links or not info.get("name"):
        return links
    entry = next((p for p in cached_catalog() if p.key == info["name"].lower()), None)
    return entry.stores if entry else []


def _read_catalog(force=False):
    """ports.json du catalogue (téléchargé, puis gardé en cache quelques heures)."""
    fresh = os.path.isfile(CACHE) and time.time() - os.path.getmtime(CACHE) < CACHE_HOURS * 3600
    if force or not fresh:
        try:
            data = net.get(CATALOG_URL, timeout=60)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "wb") as f:
                f.write(data)
        except OSError:
            if not os.path.isfile(CACHE):
                raise
    with open(CACHE, encoding="utf-8") as f:
        return json.load(f)


def load_catalog(force=False):
    """Catalogue PortMaster : liste de Port."""
    return _parse(_read_catalog(force))


def load_stats():
    """{nom du zip: nombre de téléchargements} publié par PortMaster (gardé quelques heures)."""
    fresh = os.path.isfile(STATS_CACHE) and time.time() - os.path.getmtime(STATS_CACHE) < CACHE_HOURS * 3600
    if not fresh:
        try:
            data = net.get(STATS_URL, timeout=30)
            os.makedirs(os.path.dirname(STATS_CACHE), exist_ok=True)
            with open(STATS_CACHE, "wb") as f:
                f.write(data)
        except OSError:
            pass
    try:
        with open(STATS_CACHE, encoding="utf-8") as f:
            return {k.lower(): v for k, v in (json.load(f).get("ports") or {}).items() if isinstance(v, int)}
    except (OSError, ValueError, AttributeError):
        return {}


def add_popularity(catalog, table=None):
    """Ajoute téléchargements et note du jeu original (LaunchBox, plateformes PC) aux ports."""
    stats = load_stats()
    found = {}
    for platform in ("Android", "MS-DOS", "Linux", "Windows"):  # le dernier a le dernier mot
        found.update((table or {}).get(platform, {}))
    for p in catalog:
        p.downloads = stats.get(p.key, 0)
        hit = found.get(core.title_key(p.title))
        if hit:
            p.rating, p.votes = hit[0], hit[1]
    return catalog


def taste(games):
    """{genre: poids} d'après les ports auxquels tu joues (nombre de parties), pour les recommandations."""
    out = {}
    for g in games:
        if g.playcount:
            for genre in (core.port_info(g.path).get("attr") or {}).get("genres") or []:
                out[genre.lower()] = out.get(genre.lower(), 0) + g.playcount
    return out


def recommend_score(port, likes):
    """Plus c'est haut, plus le port te correspond : genres que tu joues × popularité."""
    import math
    match = sum(likes.get(g.lower(), 0) for g in port.genres)
    return (1 + match) * math.log10(port.downloads + 10) * (1.3 if port.rtr else 1)


def load_runtimes():
    """{nom du runtime: (url, md5, taille)} : bibliothèques communes à plusieurs ports."""
    utils = _read_catalog().get("utils", {})
    return {name: (u["url"], u.get("md5", ""), u.get("size", 0)) for name, u in utils.items()
            if name.endswith(".squashfs") and u.get("url")}


def libs_dir(root):
    return os.path.join(ports_folder(root), "PortMaster", "libs")


def _missing(root, names):
    """[(nom, url, md5, taille)] des runtimes de names absents de PortMaster/libs et connus du catalogue."""
    available = load_runtimes()
    have = set(installed_runtimes(root))
    return [(name,) + available[name] for name in dict.fromkeys(names)
            if name in available and name.lower() not in have]


def missing_runtimes(root, chosen):
    """Runtimes nécessaires aux ports choisis et absents de la carte : [(nom, url, md5, taille)].
    PortMaster les téléchargerait sur la console, mais la R36S n'a pas de Wi-Fi : on les installe ici."""
    return _missing(root, [r for p in chosen for r in p.runtimes])


def installed_runtimes(root):
    """{nom en minuscules: chemin} des runtimes (.squashfs) présents dans PortMaster/libs."""
    try:
        return {e.name.lower(): e.path for e in os.scandir(libs_dir(root))
                if e.is_file() and e.name.lower().endswith(".squashfs")}
    except OSError:
        return {}


_RUNTIME_RE = re.compile(r"""^\s*runtime=["']?([\w.+-]+?)["']?\s*$""", re.M)


def _script_texts(root):
    """Contenu (en minuscules) des scripts .sh des ports présents."""
    texts = []
    for name in _scripts(root):
        try:
            with open(os.path.join(ports_folder(root), name), encoding="utf-8", errors="replace") as f:
                texts.append(f.read().lower())
        except OSError:
            pass
    return texts


def needed_runtimes(root):
    """Runtimes demandés par les ports présents : « runtime » de leur port.json et ligne runtime="…" des scripts."""
    scripts = _scripts(root)
    names = [r for script, (_f, data) in core.port_manifests(ports_folder(root)).items() if script in scripts
             for r in (data.get("attr") or {}).get("runtime") or []]
    for text in _script_texts(root):
        names += [n if n.endswith(".squashfs") else n + ".squashfs" for n in _RUNTIME_RE.findall(text)]
    return list(dict.fromkeys(names))


def missing_installed_runtimes(root):
    """Runtimes manquants aux ports déjà installés : [(nom, url, md5, taille)]."""
    return _missing(root, needed_runtimes(root))


def unused_runtimes(root):
    """Runtimes de PortMaster/libs qu'aucun port présent n'utilise (ni port.json, ni mention dans un script)."""
    needed = {n.lower() for n in needed_runtimes(root)}
    texts = _script_texts(root)
    return [path for name, path in sorted(installed_runtimes(root).items())
            if name not in needed and not any(name[:-len(".squashfs")] in t for t in texts)]


def download_runtime(root, runtime, report=None, cancel=None):
    """Installe un runtime dans PortMaster/libs (avec son fichier .md5, comme PortMaster)."""
    name, url, md5, _size = runtime
    dest = os.path.join(libs_dir(root), name)
    if not _fetch(url, dest, report, cancel, md5):
        return None
    journal.write_file(dest + ".md5", lambda p: _write_text(p, f"{md5}  {name}\n"))
    return dest


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _fetch(url, dest, report=None, cancel=None, md5=""):
    """Télécharge url vers dest (via un fichier .part, annulable). True si terminé.
    md5 : empreinte attendue ; un fichier abîmé pendant le téléchargement n'arrive jamais sur la carte."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    done, digest = 0, hashlib.md5()
    with net.open_url(url, timeout=60) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            if cancel is not None and cancel.is_set():
                break
            f.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if report:
                report(done)
    if cancel is not None and cancel.is_set():
        os.remove(part)
        return False
    if md5 and digest.hexdigest().lower() != md5.lower():
        os.remove(part)
        raise OSError("téléchargement abîmé (empreinte md5 différente), réessaie")
    journal.write_file(dest, lambda p: os.replace(part, p))
    return True


# ---------------------------------------------------------------- ports installés

def ports_folder(root):
    return os.path.join(root, "ports")


def _scripts(root):
    """Noms (minuscules) des scripts .sh présents dans ports/."""
    try:
        return {n.lower() for n in os.listdir(ports_folder(root)) if n.lower().endswith(".sh")}
    except OSError:
        return set()


def installed(root):
    """{nom du zip en minuscules: md5 de la version installée} d'après les port.json des ports
    dont le script existe encore (un dossier resté après suppression ne compte pas)."""
    out, scripts = {}, _scripts(root)
    for script, (_folder, data) in core.port_manifests(ports_folder(root)).items():
        if script not in scripts:
            continue
        name = (data.get("name") or "").lower()
        if name:
            out[name] = (data.get("status") or {}).get("md5", "")
    return out


def updates(root, catalog):
    """Ports installés dont une version plus récente existe dans le catalogue."""
    have = installed(root)
    return [p for p in catalog if p.key in have and have[p.key] and p.md5 and have[p.key] != p.md5]


def autoinstall_dir(root):
    """Dossier surveillé par PortMaster : les .zip déposés y sont installés au prochain lancement."""
    pm = os.path.join(ports_folder(root), "PortMaster")
    return os.path.join(pm, "autoinstall") if os.path.isdir(pm) else os.path.join(ports_folder(root), "autoinstall")


def pending(root):
    """Ports déjà déposés en attente d'installation par PortMaster."""
    return {os.path.basename(p).lower() for p in pending_files(root)}


def pending_files(root):
    """Chemins des .zip déposés dans autoinstall (ports et PortMaster.zip)."""
    folder = autoinstall_dir(root)
    try:
        return sorted((e.path for e in os.scandir(folder) if e.is_file() and e.name.lower().endswith(".zip")),
                      key=str.lower)
    except OSError:
        return []


def download(root, port, report=None, cancel=None):
    """Dépose le .zip du port dans autoinstall (annulable via le journal). Retourne son chemin."""
    dest = os.path.join(autoinstall_dir(root), port.zip)
    return dest if _fetch(port.url, dest, report, cancel, port.md5) else None


def is_port_zip(path):
    """Archive de port PortMaster (un script .sh à la racine ou un port.json) ou PortMaster.zip."""
    if os.path.basename(path).lower() == "portmaster.zip":
        return True
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
    except (OSError, zipfile.BadZipFile):
        return False
    return any(n.lower().endswith("/port.json") or ("/" not in n and n.lower().endswith(".sh")) for n in names)


def add_zip(root, path):
    """Dépose une archive de port déjà téléchargée dans autoinstall. Retourne son nouveau chemin."""
    dest = os.path.join(autoinstall_dir(root), os.path.basename(path))
    journal.copy(path, dest)
    return dest


# ---------------------------------------------------------------- PortMaster lui-même

def portmaster_version(root):
    """Version de PortMaster installée sur la carte (« 2025.03.07-1324 »), ou ""."""
    try:
        with open(os.path.join(ports_folder(root), "PortMaster", "version"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def latest_portmaster():
    """(version, url, md5, taille) de la dernière version de PortMaster publiée."""
    data = json.loads(net.get(GUI_RELEASE, timeout=30))
    assets = {a["name"]: a for a in data.get("assets", [])}
    zip_asset = assets["PortMaster.zip"]
    md5 = ""
    if "PortMaster.zip.md5" in assets:
        md5 = net.get(assets["PortMaster.zip.md5"]["browser_download_url"]).decode("ascii", "ignore").split()[0]
    return data["tag_name"], zip_asset["browser_download_url"], md5, zip_asset.get("size", 0)


def portmaster_update(root):
    """Dernière version de PortMaster si elle est plus récente que celle de la carte, sinon None.
    PortMaster se met à jour lui-même avec un PortMaster.zip déposé dans autoinstall."""
    current = portmaster_version(root)
    if not current or "portmaster.zip" in pending(root):
        return None
    try:
        latest = latest_portmaster()
    except (OSError, ValueError, KeyError, IndexError):
        return None
    return latest if latest[0] > current else None  # versions datées : l'ordre du texte suffit


def download_portmaster(root, latest, report=None, cancel=None):
    dest = os.path.join(autoinstall_dir(root), "PortMaster.zip")
    return dest if _fetch(latest[1], dest, report, cancel, latest[2]) else None


def catalog_screenshot(game):
    """Capture d'un port installé, prise dans le catalogue en ligne (octets), ou None."""
    name = (core.port_info(game.path).get("name") or "").lower()
    if not name:
        return None
    try:
        entry = next((p for p in load_catalog() if p.key == name and p.screenshot), None)
        return net.get(entry.screenshot) if entry else None
    except (OSError, ValueError):
        return None


def requirements(game):
    """(prêt à jouer ?, instructions, auteurs du portage, jeu payant ?) d'un port installé, ou None."""
    attr = core.port_info(game.path).get("attr")
    if not attr:
        return None
    return bool(attr.get("rtr")), (attr.get("inst") or "").strip(), attr.get("porter") or [], \
        attr.get("availability") == "paid"


# ---------------------------------------------------------------- notice, lanceurs multiples

def readme(game):
    """Notice du port (README.md, readme.txt…) : chemin, ou None."""
    for d in core.port_dirs(game.path):
        try:
            names = sorted((e for e in os.scandir(d) if e.is_file() and e.name.lower().startswith("readme")),
                           key=lambda e: (not e.name.lower().endswith((".md", ".txt")), e.name.lower()))
        except OSError:
            continue
        if names:
            return names[0].path
    return None


def group_launchers(games):
    """Réunit les scripts d'un même port (Quake 2 et ses 4 extensions…) : le principal reçoit
    .variants = [autres scripts], qui sont retirés de la liste. Les autres jeux passent tels quels."""
    groups, out = {}, []
    for g in games:
        g.variants = []
        d = core.port_dir(g.path) if g.system.lower() == "ports" and g.path.lower().endswith(".sh") else None
        if d:
            groups.setdefault(os.path.normcase(d), []).append(g)
        else:
            out.append(g)
    for members in groups.values():
        main = min(members, key=lambda g: (len(g.name), g.name.lower()))  # « Quake 2 » avant « Quake 2 - Zaero »
        main.variants = [g for g in members if g is not main]
        out.append(main)
    return out


# ---------------------------------------------------------------- fichiers du jeu original

_DATA_DIRS = ("gamedata", "assets", "data")


def files_target(game):
    """Dossier où copier les fichiers du jeu original d'un port, d'après ses instructions
    (« place the game files in sprout/assets » -> ports/sprout/assets), sinon son dossier gamedata/assets."""
    folder = core.port_dir(game.path)
    if not folder:
        return None
    inst = ((core.port_info(game.path).get("attr") or {}).get("inst") or "")
    name = os.path.basename(folder)
    m = re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])((?:/[\w-]+)*)", inst, re.I)
    if m:  # le dossier du port est cité : on prend le sous-dossier indiqué, ou le dossier lui-même
        return os.path.join(folder, *filter(None, m.group(1).split("/")))
    for d in _DATA_DIRS:
        if re.search(rf"\b{d}\b", inst, re.I):
            return os.path.join(folder, d)
    existing = [d for d in _DATA_DIRS if os.path.isdir(os.path.join(folder, d))]
    return os.path.join(folder, existing[0]) if existing else folder


_PLACEHOLDER = re.compile(r"(\.txt|\.md|\.gitkeep|readme[^/\\]*)$", re.I)
# fichiers du jeu cités dans les instructions (« data.win », « PINBALL.DAT », « oot.otr »…)
_GAME_FILE = re.compile(r"(?<![\w/.-])([\w-]+\.(?:otr|pck|dat|wad|pak|pk3|pk4|apk|obb|exe|win|bin|gob|grp|mpq|vpk|"
                        r"unx|ios|droid|assets|data))(?![\w.])", re.I)


def _has_files(folder):
    for _top, _dirs, files in os.walk(folder):
        if any(not _PLACEHOLDER.search(f) for f in files):
            return True
    return False


def files_missing(game):
    """Les fichiers du jeu original d'un port sont-ils absents ? True / False, ou None si on ne peut pas
    le savoir (port prêt à jouer, instructions sans dossier ni fichier précis)."""
    req = requirements(game)
    dirs = core.port_dirs(game.path) if req and not req[0] else []
    if not dirs:
        return None
    target = files_target(game)
    if os.path.normcase(target) != os.path.normcase(dirs[0]):  # un sous-dossier dédié (gamedata, assets…)
        return not _has_files(target)
    wanted = {n.lower() for n in _GAME_FILE.findall(req[1])}
    if not wanted:
        return None
    present = {f.lower() for d in dirs for _top, _dirs, files in os.walk(d) for f in files}
    return not wanted & present


def folder_files(source):
    """[(chemin, chemin relatif)] de tous les fichiers d'un dossier."""
    out = []
    for top, _dirs, files in os.walk(source):
        out += [(os.path.join(top, f), os.path.relpath(os.path.join(top, f), source)) for f in files]
    return sorted(out, key=lambda x: x[1].lower())


# ---------------------------------------------------------------- sauvegardes des ports

SAVE_DIRS = {"conf", "savedata", "save", "saves", "savegame", "savegames", "userdata"}
SAVE_EXTS = (".sav", ".srm", ".save", ".mps")
SAVE_MAX = 20 << 20  # au-delà ce sont des données du jeu, pas une sauvegarde


def save_files(root):
    """Sauvegardes et réglages des ports (dossiers conf/, savedata/, save/… et fichiers .sav),
    y compris ceux des dossiers de ports supprimés."""
    out = []
    try:
        dirs = [e.path for e in os.scandir(ports_folder(root)) if e.is_dir() and e.name.lower() not in IGNORED_DIRS]
    except OSError:
        return []
    for d in dirs:
        for top, _subdirs, files in os.walk(d):
            parts = {p.lower() for p in os.path.relpath(top, d).split(os.sep)}
            in_save = bool(parts & SAVE_DIRS)
            for f in files:
                p = os.path.join(top, f)
                if (in_save or f.lower().endswith(SAVE_EXTS)) and f.lower() not in ("port.json", ".gitkeep"):
                    try:
                        if os.path.getsize(p) <= SAVE_MAX:
                            out.append(p)
                    except OSError:
                        pass
    return out


# ---------------------------------------------------------------- dossiers orphelins

def orphan_dirs(root, games):
    """Dossiers de ports dont le script .sh n'existe plus (restes d'un port supprimé)."""
    folder = ports_folder(root)
    used = {os.path.normcase(d) for g in games if (d := core.port_dir(g.path))}
    try:
        dirs = [e for e in os.scandir(folder) if e.is_dir()]
    except OSError:
        return []
    return [e.path for e in dirs if e.name.lower() not in IGNORED_DIRS and not e.name.startswith(".")
            and os.path.normcase(e.path) not in used]
