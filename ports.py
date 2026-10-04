"""PortMaster : ports installés (infos locales) et catalogue en ligne (installation, mises à jour).

- Chaque port installé a un port.json (titre, description, instructions, images, et dans
  « status » l'empreinte md5 de la version installée).
- Le catalogue officiel (ports.json, ~1400 ports) donne pour chaque port sa description, son
  image, s'il est « prêt à jouer » (rtr : aucun fichier du jeu original à fournir), sa taille,
  son lien de téléchargement et l'empreinte de sa dernière version.
- Installer = déposer le .zip dans ports/PortMaster/autoinstall : PortMaster l'installe lui-même
  au prochain lancement sur la console (il ajoute aussi les bibliothèques dont le port a besoin).
"""
import json
import os
import re
import time
from dataclasses import dataclass

import core
import journal
import net
import paths

CATALOG_URL = "https://github.com/PortsMaster/PortMaster-New/releases/latest/download/ports.json"
IMAGE_URL = "https://raw.githubusercontent.com/PortsMaster/PortMaster-New/main/ports/{dir}/{file}"
CACHE = paths.data("cache", "portmaster-ports.json")
CACHE_HOURS = 12
ARCHS = {"aarch64", "armhf"}  # processeurs que la R36S sait faire tourner
IGNORED_DIRS = {"portmaster", "autoinstall"} | core.MEDIA_DIRS


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
                        IMAGE_URL.format(dir=name[:-4], file=shot) if shot else "", a.get("runtime") or []))
    return sorted(out, key=lambda p: p.title.lower())


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
    if not _fetch(url, dest, report, cancel):
        return None
    journal.write_file(dest + ".md5", lambda p: _write_text(p, f"{md5}  {name}\n"))
    return dest


def _write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _fetch(url, dest, report=None, cancel=None):
    """Télécharge url vers dest (via un fichier .part, annulable). True si terminé."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    done = 0
    with net.open_url(url, timeout=60) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            if cancel is not None and cancel.is_set():
                break
            f.write(chunk)
            done += len(chunk)
            if report:
                report(done)
    if cancel is not None and cancel.is_set():
        os.remove(part)
        return False
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
    try:
        return {f.lower() for f in os.listdir(autoinstall_dir(root)) if f.lower().endswith(".zip")}
    except OSError:
        return set()


def download(root, port, report=None, cancel=None):
    """Dépose le .zip du port dans autoinstall (annulable via le journal). Retourne son chemin."""
    dest = os.path.join(autoinstall_dir(root), port.zip)
    return dest if _fetch(port.url, dest, report, cancel) else None


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


def folder_files(source):
    """[(chemin, chemin relatif)] de tous les fichiers d'un dossier."""
    out = []
    for top, _dirs, files in os.walk(source):
        out += [(os.path.join(top, f), os.path.relpath(os.path.join(top, f), source)) for f in files]
    return sorted(out, key=lambda x: x[1].lower())


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
