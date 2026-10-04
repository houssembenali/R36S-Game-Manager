"""Réglages mémorisés entre deux lancements (langue, vue, tri, son des vidéos, taille des panneaux…).

Fichier JSON dans le dossier des données (voir paths.data). get() renvoie la valeur par défaut
si le réglage n'existe pas ou si le fichier est illisible : le programme ne plante jamais pour ça.
"""
import json
import os

import paths

FILE = paths.data("settings.json")
DEFAULTS = {
    "language": "",          # "" = langue du système
    "view": "grid",
    "sort": "name_asc",
    "port_sort": "name",     # tri du catalogue PortMaster
    "port_seen": "",         # date du port le plus récent vu dans le catalogue (badge « nouveau »)
    "video_muted": False,
    "panes": [],             # positions des séparateurs (liste des systèmes / détails)
    "drive": "",
}
_values = None


def _load():
    global _values
    if _values is None:
        try:
            with open(FILE, encoding="utf-8") as f:
                _values = json.load(f)
        except (OSError, ValueError):
            _values = {}
    return _values


def get(key):
    return _load().get(key, DEFAULTS.get(key))


def set(key, value):  # noqa: A001 - nom court, utilisé comme settings.set(...)
    _load()[key] = value


def save():
    try:
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(_load(), f, ensure_ascii=False, indent=1)
    except OSError:
        pass
