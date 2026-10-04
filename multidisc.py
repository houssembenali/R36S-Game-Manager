"""Regroupement des jeux multi-disques dans un fichier .m3u.

« Final Fantasy VII (Disc 1).cue », « (Disc 2) », « (Disc 3) » deviennent un seul jeu
« Final Fantasy VII.m3u » : la console n'affiche qu'une entrée et on change de disque dans
le menu RetroArch. Les disques sont rangés dans un sous-dossier caché « .multidisc »
(EmulationStation ignore les dossiers qui commencent par un point).
"""
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import core
import journal

HIDDEN_DIR = ".multidisc"
DISC_EXT = {".cue", ".ccd", ".chd", ".pbp", ".iso", ".cdi", ".gdi", ".mds", ".toc"}


@dataclass
class Group:
    system: str
    folder: str                                   # dossier des disques
    title: str                                    # nom du futur .m3u (sans extension)
    discs: list = field(default_factory=list)     # [(numéro, Game)] triés

    @property
    def name(self):
        """Nom affiché : celui de la fiche du disque 1, sans « (Disc 1) »."""
        return clean_title(self.discs[0][1].name)


def clean_title(name):
    t = core.DISC_RE.sub("", name)
    return re.sub(r"\s{2,}", " ", t).strip(" -")


def find_groups(games_by_system):
    groups = []
    for system, games in games_by_system.items():
        buckets = {}
        for g in games:
            m = core.DISC_RE.search(g.stem)
            if not m or os.path.splitext(g.path)[1].lower() not in DISC_EXT:
                continue
            key = (os.path.normcase(os.path.dirname(g.path)), clean_title(g.stem).lower())
            buckets.setdefault(key, {}).setdefault(int(m.group(1)), g)  # un fichier par disque
        for (_, _), discs in buckets.items():
            if len(discs) < 2:
                continue
            ordered = sorted(discs.items())
            first = ordered[0][1]
            groups.append(Group(system, os.path.dirname(first.path), clean_title(first.stem), ordered))
    return sorted(groups, key=lambda gr: gr.title.lower())


def create_m3u(root, group):
    """Crée le .m3u, range les disques dans .multidisc et fusionne les fiches. Retourne (chemin m3u, erreurs)."""
    m3u = os.path.join(group.folder, group.title + ".m3u")
    if os.path.exists(m3u):
        return None, [f"{os.path.basename(m3u)} existe déjà"]
    hidden = os.path.join(group.folder, HIDDEN_DIR)
    os.makedirs(hidden, exist_ok=True)
    lines, errors = [], []
    for _, g in group.discs:
        for f in core.game_files(g):
            if os.path.isfile(f) and core.same(os.path.dirname(f), group.folder):
                try:
                    journal.move(f, os.path.join(hidden, os.path.basename(f)))
                except OSError as e:
                    errors.append(f"{f} : {e}")
        lines.append(f"{HIDDEN_DIR}/{os.path.basename(g.path)}")

    def write(path):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    journal.write_file(m3u, write)

    # la sauvegarde (carte mémoire) du disque 1 sert au jeu regroupé
    first = group.discs[0][1]
    for save in core.save_files(first):
        dest = os.path.join(group.folder, group.title + os.path.basename(save)[len(first.stem):])
        if not os.path.exists(dest):
            journal.copy(save, dest)

    errors += core.edit_gamelist(root, os.path.join(root, group.system),
                                 lambda top, entries: _merge_entries(top, entries, group, m3u, root))
    core.clear_cache()
    return m3u, errors


def _merge_entries(top, entries, group, m3u, root):
    els = [entries.get(core._key_of(g.path)) for _, g in group.discs]
    base = next((e for e in els if e is not None), None)
    new = ET.Element("game")
    if base is not None:
        for child in base:
            new.append(child)
    sysdir = os.path.join(root, group.system)
    core._set_tag(new, "path", "./" + core._rel(m3u, sysdir))
    core._set_tag(new, "name", group.name)
    for e in els:
        if e is not None and e in list(top):
            top.remove(e)
    top.append(new)
