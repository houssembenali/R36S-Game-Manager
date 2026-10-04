"""Thèmes d'EmulationStation (dossier themes/ de la carte).

Un thème est un dossier : un theme.xml par console (themes/<thème>/<console>/theme.xml), et
souvent un theme.xml à la racine qui sert aux consoles sans dossier propre.
"""
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field

import core
import journal
import systems

IMAGE = re.compile(r"\.(png|jpe?g)$", re.I)
PREVIEW = re.compile(r"preview|screenshot|capture", re.I)


@dataclass
class Theme:
    name: str
    path: str
    size: int = 0
    systems: set = field(default_factory=set)  # consoles qui ont leur propre theme.xml
    generic: bool = False                       # theme.xml à la racine : sert à toutes les consoles
    preview: str = ""

    def missing(self, card_systems):
        """Consoles de la carte que le thème ne dessine pas."""
        return [] if self.generic else sorted(s for s in card_systems if s.lower() not in self.systems)


def themes_dir(root):
    return os.path.join(root, "themes")


def _preview(folder):
    """Image d'aperçu : un fichier « preview » / « screenshot », sinon une image à la racine du thème."""
    found = []
    for top, dirs, files in os.walk(folder):
        if top != folder:
            dirs[:] = []  # racine et premier niveau seulement : un thème a des milliers d'images
        found += [os.path.join(top, f) for f in files if IMAGE.search(f)]
    named = [p for p in found if PREVIEW.search(os.path.basename(p))]
    roots = [p for p in found if os.path.dirname(p) == folder]
    common = [p for s in ("snes", "gba", "nes", "megadrive", "psx", "_art", "art")
              for p in found if os.path.basename(os.path.dirname(p)).lower() == s]
    return (named or roots or common or found or [""])[0]


def list_themes(root):
    out = []
    try:
        entries = sorted((e for e in os.scandir(themes_dir(root)) if e.is_dir()), key=lambda e: e.name.lower())
    except OSError:
        return []
    for e in entries:
        try:
            subs = [s for s in os.scandir(e.path) if s.is_dir()]
        except OSError:
            subs = []
        out.append(Theme(e.name, e.path, core.path_size(e.path),
                         {s.name.lower() for s in subs if os.path.isfile(os.path.join(s.path, "theme.xml"))},
                         os.path.isfile(os.path.join(e.path, "theme.xml")), _preview(e.path)))
    return out


def _theme_root(folder):
    """Dossier qui contient vraiment le thème (une archive ajoute souvent un dossier en trop,
    ex. « mon-theme-main/ ») ; None s'il n'y a pas de thème."""
    while True:
        entries = os.listdir(folder)
        dirs = [d for d in entries if os.path.isdir(os.path.join(folder, d))]
        if "theme.xml" in entries:
            return folder
        if len(dirs) == 1 and dirs[0].lower() not in systems.SYSTEMS:  # dossier en trop : on descend
            folder = os.path.join(folder, dirs[0])
            continue
        return folder if any(os.path.isfile(os.path.join(folder, d, "theme.xml")) for d in dirs) else None


def install(root, source):
    """Ajoute un thème depuis un dossier ou un .zip. Retourne le dossier créé.
    ValueError si ce n'est pas un thème, FileExistsError s'il y en a déjà un du même nom."""
    with tempfile.TemporaryDirectory() as tmp:
        if os.path.isfile(source):
            with zipfile.ZipFile(source) as z:
                for m in z.infolist():  # pas de chemin qui sortirait du dossier
                    if not os.path.normpath(m.filename).startswith(".."):
                        z.extract(m, tmp)
            folder = _theme_root(tmp)
            if not folder:
                raise ValueError("pas de theme.xml")
            name = os.path.splitext(os.path.basename(source))[0] if folder == tmp else os.path.basename(folder)
        else:
            folder = _theme_root(source)
            if not folder:
                raise ValueError("pas de theme.xml")
            name = os.path.basename(folder)
        dest = os.path.join(themes_dir(root), name)
        if os.path.exists(dest):
            raise FileExistsError(name)
        shutil.copytree(folder, dest)
    journal.created(dest)
    return dest
