"""Filtres de la liste des jeux : genre, nombre de joueurs, région, jamais joué, sans image, sans note.

Fonctions pures (sans interface) : faciles à tester et à étendre. Pour ajouter un filtre :
une clé dans EMPTY, son test dans matches(), puis son contrôle dans la barre (app.py).
"""
import os
import re

import arcade
import core
import ports
import regions

EMPTY = {"genre": "", "players": 0, "region": "", "never": False, "noimage": False, "norating": False,
         "nofiles": False, "broken": False}

PLAYERS = {"Tous": 0, "1 joueur": 1, "2 joueurs et +": 2, "3 joueurs et +": 3, "4 joueurs et +": 4}


def main_genre(game):
    """Genre principal : « Tir / 1ere Personne-Tir » -> « Tir », « Action-Plateforme » -> « Action »."""
    g = (game.info.get("genre") or "").strip()
    for sep in (" / ", ",", "-"):
        g = g.split(sep)[0].strip()
    return g[:1].upper() + g[1:] if g else ""


def max_players(game):
    """Nombre maximum de joueurs : « 1-2 » -> 2, « 4 » -> 4, inconnu -> 0."""
    nums = [int(n) for n in re.findall(r"\d+", game.info.get("players") or "")]
    return max(nums) if nums else 0


def genres(games):
    """[(genre, nombre de jeux)] triés par nom ; « Shoot'em up » et « Shoot'em Up » ne font qu'un."""
    counts, label = {}, {}
    for g in games:
        name = main_genre(g)
        if name:
            key = name.lower()
            counts[key] = counts.get(key, 0) + 1
            label.setdefault(key, name)
    return sorted(((label[k], n) for k, n in counts.items()), key=lambda kv: kv[0].lower())


def region_codes(games):
    """Régions présentes parmi ces jeux, les plus fréquentes d'abord."""
    counts = {}
    for g in games:
        for c in regions.regions(g.stem):
            counts[c] = counts.get(c, 0) + 1
    return sorted(counts, key=lambda c: -counts[c])


def game_root(game):
    """Racine de la carte d'un jeu (le dossier qui contient le dossier de sa console)."""
    return os.path.dirname(game.sysdir)


def active_count(f):
    return sum(1 for k, v in f.items() if v != EMPTY[k])


def matches(game, f):
    if f["genre"] and main_genre(game).lower() != f["genre"].lower():
        return False
    if f["players"]:
        n = max_players(game)
        if n < f["players"] or (f["players"] == 1 and n != 1):
            return False
    if f["region"] and f["region"] not in regions.regions(game.stem):
        return False
    if f["never"] and game.playcount:
        return False
    if f["noimage"] and core.cover_for(game):
        return False
    if f["broken"] and not (game.system.lower() in arcade.SYSTEMS and arcade.missing(game_root(game), game)):
        return False
    if f["nofiles"] and (game.system.lower() != "ports" or ports.files_missing(game) is not True):
        return False
    return not (f["norating"] and game.rating is not None)


def apply(games, f):
    return games if not active_count(f) else [g for g in games if matches(g, f)]
