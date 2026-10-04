"""Doublons sur toute la carte, avec la version à garder.

Deux sortes de doublons :
  copie     le même fichier, octet pour octet, présent deux fois (souvent sur deux consoles)
  version   le même jeu en plusieurs versions dans une console (USA, Europe, Rev 1, Beta…)
Pour chaque groupe, on garde la meilleure copie : celle qui a des parties, une note, qui est en
favori, puis la meilleure région pour la langue de l'interface, puis la révision la plus récente.
"""
import hashlib
import os
import re
from dataclasses import dataclass

import core
import i18n
import regions
import systems

BAD_TAGS = re.compile(r"\((?:[^)]*\b(?:beta|proto|prototype|demo|sample|hack|pirate|unl|unlicensed|aftermarket|"
                      r"homebrew|program)\b[^)]*)\)|\[(?:b|h|t|f|o|p)\d*[^\]]*\]", re.I)
REVISION = re.compile(r"\((?:rev\s*([0-9a-z]+)|v\s*([0-9.]+))\)", re.I)
REGION_ORDER = {"fr": ["fr", "eu", "world", "us", "gb", "ca", "au", "jp"],
                "en": ["us", "world", "eu", "gb", "ca", "au", "fr", "jp"]}
SKIP_SYSTEMS = {"ports"}  # un port est un script : ses « doublons » sont des lanceurs différents


@dataclass
class Duplicate:
    game: object   # copie à supprimer
    keep: object   # copie gardée
    kind: str      # « copy » (fichier identique) ou « version » (autre version du jeu)
    checked: bool  # proposé coché : rien d'important n'est perdu


def _hash(path, cancel=None, limit=None):
    """Empreinte md5 du fichier (ou de ses limit premiers octets)."""
    h, left = hashlib.md5(), limit
    with open(path, "rb") as f:
        while chunk := f.read(4 << 20 if left is None else min(4 << 20, left)):
            if left is not None:
                left -= len(chunk)
            if cancel is not None and cancel.is_set():
                return None
            h.update(chunk)
    return h.hexdigest()


def _revision(name):
    m = REVISION.search(name)
    if not m:
        return 0
    value = m.group(1) or m.group(2)
    if value.replace(".", "").isdigit():
        return sum(int(p) / 100 ** i for i, p in enumerate(value.split(".")) if p) + 1
    return ord(value[0].lower()) - ord("a") + 2  # Rev A, Rev B…


def precious(game):
    """Copie qui a de la valeur pour le joueur : parties, sauvegardes, note ou favori."""
    return bool(game.favorite or game.playcount or game.rating is not None or core.save_files(game))


def score(game):
    """Plus c'est haut, plus cette copie mérite d'être gardée."""
    s = 0
    if game.favorite:
        s += 1000
    if core.save_files(game):
        s += 800
    if game.playcount:
        s += 500 + min(game.playcount, 100)
    if game.rating is not None:
        s += 50
    if game.system in systems.systems_for_extension(game.path):
        s += 200  # bien rangé dans la console qui lit ce format
    s -= 300 * len(BAD_TAGS.findall(game.stem))
    order = REGION_ORDER.get(i18n.LANG, REGION_ORDER["en"])
    found = [order.index(c) for c in regions.regions(game.stem) if c in order]
    if found:
        s += (len(order) - min(found)) * 20
    if i18n.LANG == "fr" and re.search(r"\([^)]*\bFr\b[^)]*\)", game.stem):
        s += 60
    s += _revision(game.stem) * 5
    if game.in_gamelist:
        s += 5
    if game.media:
        s += 5
    return s


def best(games):
    return max(games, key=lambda g: (score(g), -len(g.stem), g.stem.lower()))


def _identical(games, report=None, cancel=None):
    """Groupes de jeux dont le fichier est identique (même taille, puis même empreinte)."""
    by_size = {}
    for g in games:
        if os.path.isfile(g.path) and g.size > 0:
            by_size.setdefault(os.path.getsize(g.path), []).append(g)
    candidates = []
    for grp in (g for g in by_size.values() if len(g) > 1):  # tri rapide sur le début des fichiers
        by_head = {}
        for g in grp:
            try:
                by_head.setdefault(_hash(g.path, limit=64 << 10), []).append(g)
            except OSError:
                pass
        candidates += [same for same in by_head.values() if len(same) > 1]
    groups, done, total = [], 0, sum(len(grp) for grp in candidates)
    for grp in candidates:
        by_hash = {}
        for g in grp:
            if cancel is not None and cancel.is_set():
                return groups
            if report:
                report(done, total, g.name)
            done += 1
            try:
                digest = _hash(g.path, cancel)
            except OSError:
                continue
            if digest:
                by_hash.setdefault(digest, []).append(g)
        groups += [same for same in by_hash.values() if len(same) > 1]
    return groups


def find(games_by_system, report=None, cancel=None):
    """[Duplicate] : copies identiques sur toute la carte, puis autres versions d'un même jeu."""
    games = [g for system, lst in games_by_system.items() if system.lower() not in SKIP_SYSTEMS for g in lst]
    out, removed = [], set()
    for group in _identical(games, report, cancel):
        keep = best(group)
        for g in group:
            if g is not keep:
                arcade = g.system.lower() in core.ARCADE_SYSTEMS and g.system != keep.system
                out.append(Duplicate(g, keep, "copy", not precious(g) and not arcade))
                removed.add(id(g))
    for system, lst in games_by_system.items():
        if system.lower() in SKIP_SYSTEMS | core.ARCADE_SYSTEMS:
            continue
        groups = {}
        for g in lst:
            if id(g) not in removed and not core.DISC_RE.search(g.stem) and (key := core.title_key(g.stem)):
                groups.setdefault(key, []).append(g)
        for group in groups.values():
            if len(group) > 1:
                keep = best(group)
                out += [Duplicate(g, keep, "version", not precious(g)) for g in group if g is not keep]
    return out
