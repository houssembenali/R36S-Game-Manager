"""Nettoyage de la carte : détection et suppression des fichiers obsolètes ou incohérents.

Catégories (voir CATEGORIES) :
  media     images / vidéos / manuels qui n'appartiennent plus à aucun jeu
  entry     fiches du gamelist.xml dont la ROM n'existe plus
  save      sauvegardes (.srm, .state…) dont le jeu n'existe plus
  misplaced ROM dont l'extension ne correspond pas à la console du dossier
  oldlist   anciennes copies de gamelist (gamelist.xml.old, .bak…)
"""
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import core
import ports
import journal
import systems
from i18n import _

def categories():
    """clé -> (titre, explication, cochée par défaut), dans la langue de l'interface."""
    return {
        "media": (_("Médias orphelins"), _("Images, vidéos et manuels de jeux qui ne sont plus sur la carte."), True),
        "entry": (_("Fiches sans jeu"), _("Entrées du gamelist.xml dont la ROM a été supprimée."), True),
        "save": (_("Sauvegardes sans jeu"),
                 _("Sauvegardes (.srm, .state…) de jeux qui ne sont plus sur la carte."), False),
        "misplaced": (_("Jeux dans le mauvais dossier"),
                      _("ROM dont le format ne correspond pas à la console du dossier : la console ne la lancera pas."),
                      False),
        "portdir": (_("Dossiers de ports sans script"),
                    _("Dossiers de ports PortMaster dont le jeu a été supprimé (son script .sh n'existe plus). "
                      "Ils peuvent contenir les fichiers d'un jeu que tu voudrais réinstaller."), False),
        "oldlist": (_("Anciennes copies de gamelist"),
                    "gamelist.xml.old, gamelist.backup.xml, gamelist.xml.bak…", False),
    }


CATEGORIES = categories()  # clés des catégories (les libellés sont relus via categories())

# suffixes ajoutés par les scrapers d'EmulationStation (« jeu-image.png »)
_SCRAPER_SUFFIX = re.compile(r"-(image|thumb|thumbnail|marquee|video|box|fanart|screenshot)$", re.I)
_OLD_LISTS = re.compile(r"^gamelist(\.xml\.(old|bak)|\.backup\.xml|\.old\.xml)$", re.I)
_SAVE_DIRS = {"savestates", "saves", "fba", "fbneo"}
# sauvegardes N64 nommées d'après le nom interne de la ROM (pas le fichier) : invérifiables
_UNMATCHABLE_SAVES = (".sra", ".eep", ".fla", ".mpk")


@dataclass
class Issue:
    kind: str
    system: str
    path: str            # fichier concerné (ou ROM pour « entry » / « misplaced »)
    size: int = 0
    note: str = ""       # précision affichée (ex. console probable)
    game: object = None  # Game pour « misplaced »


def _media_stem(name):
    stem = _SCRAPER_SUFFIX.sub("", os.path.splitext(name)[0]).lower()
    return stem, stem.rsplit(" ", 1)[0]  # Skraper ajoute « <empreinte> » après le nom


def _orphan_media(system, sysdir, games):
    used = {os.path.normcase(os.path.normpath(p)) for g in games for p in g.media.values()}
    stems = {g.stem.lower() for g in games}
    for entry in os.scandir(sysdir):
        if not (entry.is_dir() and entry.name.lower() in core.MEDIA_DIRS):
            continue
        for dirpath, _x, files in os.walk(entry.path):
            for f in files:
                p = os.path.normpath(os.path.join(dirpath, f))
                if os.path.normcase(p) in used or any(s in stems for s in _media_stem(f)):
                    continue
                yield Issue("media", system, p, core.path_size(p))


def _orphan_entries(root, system, sysdir):
    gl = os.path.join(sysdir, "gamelist.xml")
    if not os.path.isfile(gl):
        return
    try:
        entries = ET.parse(gl).getroot().findall("game")
    except ET.ParseError:
        return
    for el in entries:
        p = core.resolve_path(root, sysdir, el.findtext("path"))
        if p and not os.path.exists(p):
            name = (el.findtext("name") or "").strip()
            yield Issue("entry", system, p, note=name)


def _orphan_saves(system, sysdir, games):
    all_stems = {g.stem.lower() for g in games}
    local = {(os.path.normcase(os.path.dirname(g.path)), g.stem.lower()) for g in games}
    folders = [sysdir]
    if system.lower() not in core.ROOT_ONLY_SYSTEMS:
        folders += [e.path for e in os.scandir(sysdir) if e.is_dir()
                    and (e.name.lower() not in core.NOT_GAME_SUBDIRS or e.name.lower() in _SAVE_DIRS)]
    for folder in folders:
        try:
            files = [e for e in os.scandir(folder) if e.is_file()]
        except OSError:
            continue
        in_save_dir = os.path.basename(folder).lower() in _SAVE_DIRS
        for e in files:
            m = core.SAVE_RE.search(e.name)
            if not m or e.name.lower().endswith(_UNMATCHABLE_SAVES):
                continue
            base = e.name[:m.start()].lower()
            # une sauvegarde à côté de la ROM, ou rangée dans fba/, savestates/… (tout le système)
            owned = (os.path.normcase(folder), base) in local or (in_save_dir and base in all_stems)
            if not owned:
                yield Issue("save", system, e.path, e.stat().st_size)


def _misplaced(system, games):
    for g in games:
        if os.path.isdir(g.path) or systems.valid_extension(system, g.path):
            continue
        targets = [systems.name(s) for s in systems.systems_for_extension(g.path) if s != system.lower()]
        note = (_("plutôt pour : {systems}", systems=", ".join(dict.fromkeys(targets))) if targets
                else _("format non pris en charge par cette console"))
        yield Issue("misplaced", system, g.path, g.size, note, g)


def _old_lists(system, sysdir):
    for e in os.scandir(sysdir):
        if e.is_file() and _OLD_LISTS.match(e.name):
            yield Issue("oldlist", system, e.path, e.stat().st_size)


def scan(root, games_by_system):
    """Liste de tous les problèmes trouvés sur la carte."""
    issues = []
    for system in core.list_systems(root):
        sysdir = os.path.join(root, system)
        games = games_by_system.get(system, [])
        try:
            issues += _orphan_media(system, sysdir, games)
            issues += _orphan_entries(root, system, sysdir)
            issues += _orphan_saves(system, sysdir, games)
            issues += _misplaced(system, games)
            issues += _old_lists(system, sysdir)
            if system.lower() == "ports":
                issues += [Issue("portdir", system, d, core.path_size(d)) for d in ports.orphan_dirs(root, games)]
        except OSError:
            continue
    return issues


def clean(root, issues, games_by_system, progress=None, cancel=None):
    """Supprime ce qui est listé. progress(fait, texte) suit l'avancement ; cancel (Event)
    arrête entre deux éléments. Retourne (jeux supprimés, erreurs, nombre traité)."""
    errors, removed_games = [], []
    entries = {}   # dossier système -> ROM absentes dont il faut retirer la fiche
    done = 0
    for it in issues:
        if cancel is not None and cancel.is_set():
            break
        done += 1
        if progress and (done % 10 == 0 or it.kind == "misplaced"):
            progress(done, "Suppression : " + os.path.basename(it.path))
        if it.kind == "entry":
            entries.setdefault(os.path.join(root, it.system), set()).add(os.path.normcase(it.path))
        elif it.kind == "misplaced":
            files = core.files_to_delete(it.game, games_by_system.get(it.system, []))
            errors += core.delete_game(root, it.game, files)
            if not os.path.exists(it.game.path):
                removed_games.append(it.game)
        else:
            errors += _remove_file(it.path)
    if progress and entries:
        progress(done, "Mise à jour des gamelist.xml…")
    for sysdir, paths in entries.items():
        errors += _remove_entries(root, sysdir, paths)
    core.clear_cache()
    return removed_games, errors, done


def _remove_file(path):
    try:
        if os.path.lexists(path):
            journal.remove(path)
    except OSError as e:
        return [f"{path} : {e}"]
    return []


def _remove_entries(root, sysdir, paths):
    gl = os.path.join(sysdir, "gamelist.xml")
    try:
        tree = ET.parse(gl)
        top = tree.getroot()
        for el in top.findall("game"):
            p = core.resolve_path(root, sysdir, el.findtext("path"))
            if p and os.path.normcase(p) in paths and not os.path.exists(p):
                top.remove(el)
        core._write_gamelist(gl, tree)
    except (OSError, ET.ParseError) as e:
        return [f"{gl} : {e}"]
    return []
