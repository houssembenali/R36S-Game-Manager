"""Jeux d'arcade (FinalBurn Neo) qui ne se lanceront pas faute d'un autre fichier.

En arcade, un jeu est souvent découpé :
  - une version (« clone », ex. mslugh.zip) ne contient que ce qui diffère du jeu principal
    (« parent », mslug.zip) : sans lui, elle ne démarre pas ;
  - beaucoup de systèmes ont besoin d'un BIOS (neogeo.zip, pgm.zip…) dans le dossier du jeu
    ou dans bios/.
La liste FinalBurn Neo donne l'empreinte (CRC) de chaque ROM d'un jeu : on vérifie qu'on les
trouve toutes dans le .zip du jeu, de son parent ou de son BIOS.
"""
import os
import re
import zipfile

import gamecat
import metadata

SYSTEMS = set(gamecat.ARCADE_SOURCES)  # dossiers lus par FinalBurn Neo sur ArkOS
_db = {}


def database():
    """{nom de code: {"parent", "bios", "roms": {crc: nom}, "isbios"}} depuis la liste FinalBurn Neo."""
    if not _db:
        text = metadata.fbneo_text()
        for m in re.finditer(r'<game ([^>]*)>(.*?)</game>', text, re.S):
            attrs, body = m.group(1), m.group(2)
            name = re.search(r'name="([^"]+)"', attrs)
            if not name:
                continue
            parent = re.search(r'cloneof="([^"]+)"', attrs)
            romof = re.search(r'romof="([^"]+)"', attrs)
            roms = {crc.lower(): rom for rom, crc in re.findall(r'<rom name="([^"]+)"[^>]*crc="([0-9a-fA-F]{8})"', body)}
            _db[name.group(1).lower()] = {"parent": parent.group(1).lower() if parent else "",
                                          "romof": romof.group(1).lower() if romof else "",
                                          "roms": roms, "isbios": 'isbios="yes"' in attrs}
        for info in _db.values():
            info["bios"] = _bios_of(info)
    return _db


def _bios_of(info):
    """BIOS du jeu : on remonte « romof » (clone -> parent -> BIOS) jusqu'à un BIOS."""
    seen, name = set(), info["romof"]
    while name and name not in seen and name in _db:
        if _db[name]["isbios"]:
            return name
        seen.add(name)
        name = _db[name]["romof"]
    return ""


def is_bios(game):
    """Fichier de BIOS (neogeo.zip…) rangé avec les jeux : ce n'est pas un jeu."""
    info = database().get(game.stem.lower())
    return bool(info and info["isbios"])


def _crcs(path):
    try:
        with zipfile.ZipFile(path) as z:
            return {f"{i.CRC:08x}" for i in z.infolist() if not i.is_dir()}
    except (OSError, zipfile.BadZipFile):
        return set()


def _find(root, folder, name):
    """Chemin de name.zip dans le dossier du jeu ou dans bios/, sinon None."""
    for d in (folder, os.path.join(root, "bios")):
        p = os.path.join(d, name + ".zip")
        if os.path.isfile(p):
            return p
    return None


_checked = {}  # (chemin, taille, date) -> résultat : les .zip ne sont relus que s'ils changent


def missing(root, game):
    """Fichiers qui manquent pour lancer ce jeu d'arcade : [(nom.zip, « parent » | « bios »)], [] si
    rien ne manque (ou si le jeu n'est pas connu de FinalBurn Neo)."""
    if game.system.lower() not in SYSTEMS or not game.path.lower().endswith(".zip"):
        return []
    db = database()
    info = db.get(game.stem.lower())
    if not info or info["isbios"]:
        return []
    try:
        st = os.stat(game.path)
    except OSError:
        return []
    key = (os.path.normcase(game.path), st.st_size, st.st_mtime)
    if key not in _checked:
        _checked[key] = _missing(root, game, info, db)
    return _checked[key]


def _missing(root, game, info, db):
    have = _crcs(game.path)
    if not have:
        return []
    folder, out = os.path.dirname(game.path), []
    for kind, name in (("bios", info["bios"]), ("parent", info["parent"])):  # le BIOS d'abord : le parent
        # liste aussi les ROM du BIOS
        if not name or name not in db:
            continue
        needed = set(info["roms"]) & set(db[name]["roms"])  # ROM du jeu qui viennent du parent / du BIOS
        if needed - have:  # pas toutes dans le .zip du jeu : il faut le fichier à côté
            path = _find(root, folder, name)
            if not path:
                out.append((name + ".zip", kind))
            else:
                have |= _crcs(path)
    return out
