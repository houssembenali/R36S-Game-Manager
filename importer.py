"""Ajout de jeux depuis le PC : devine la console d'après le fichier puis copie sur la carte."""
import os
import zipfile

import core
import journal
import systems


def expand(paths):
    """Fichiers à importer : les dossiers glissés sont parcourus ; les pistes d'un .cue,
    les .img/.sub d'un .ccd… sont rattachées à leur fichier principal."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for dirpath, _, names in os.walk(p):
                files += [os.path.join(dirpath, n) for n in names]
        elif os.path.isfile(p):
            files.append(p)
    # fichiers principaux d'abord (.m3u, .cue, .ccd…) : ils « absorbent » leurs pistes
    files = sorted(set(files), key=core.primary_rank)
    keep, parts = [], set()
    for f in files:
        if os.path.normcase(f) in parts or core.is_not_game(os.path.basename(f)):
            continue
        keep.append(f)
        parts.update(os.path.normcase(c) for c in core.components(f) + core.siblings(f))
    return keep


def guess_system(path, available, current=None):
    """Console la plus probable pour ce fichier, ou None si impossible à dire."""
    ext = os.path.splitext(path)[1].lower()
    inner = path
    if ext == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
            if len(names) == 1 or (names and not systems.systems_for_extension(path)):
                inner = names[0]
        except (OSError, zipfile.BadZipFile):
            pass
    candidates = systems.systems_for_extension(inner)
    # on préfère une console qui a déjà son dossier sur la carte
    for s in sorted(candidates, key=lambda s: s not in available):  # tri stable : ordre de la table
        return s
    return current if current in available else None


def files_of(path):
    """Le fichier et ses compagnons (pistes, .img/.sub…)."""
    return [path] + [p for p in dict.fromkeys(core.components(path) + core.siblings(path))]


def import_files(root, items, report=None, cancel=None):
    """Copie [(fichier, système)] sur la carte. Retourne (chemins copiés, erreurs)."""
    copied, errors = [], []
    for i, (path, system) in enumerate(items):
        if cancel is not None and cancel.is_set():
            break
        if report:
            report(i, "Copie : " + os.path.basename(path))
        dest_dir = os.path.join(root, system)
        src_dir = os.path.dirname(path)
        plan = [(f, os.path.join(dest_dir, os.path.relpath(f, src_dir))) for f in files_of(path)]
        if os.path.exists(plan[0][1]):
            errors.append(f"{os.path.basename(path)} : existe déjà dans {system}")
            continue
        try:
            for src, dst in plan:
                journal.copy(src, dst)
            copied.append(plan[0][1])
        except OSError as e:
            errors.append(f"{os.path.basename(path)} : {e}")
    core.clear_cache()
    return copied, errors


def total_size(paths):
    return sum(core.path_size(f) for p in paths for f in files_of(p))
