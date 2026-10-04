"""Fiches importées à nettoyer.

  - descriptions copiées-collées : le même texte sur au moins 8 jeux différents de la carte
    (ex. « 游戏资源来自网路… », « ressources trouvées sur internet ») n'est pas une description ;
  - fichiers qui ne sont pas des jeux (BIOS d'arcade, entrées « ZZZ(notgame) ») : on les masque
    dans EmulationStation (balise <hidden>), sans les supprimer, car l'émulateur peut en avoir besoin.
"""
import re

import arcade
import core

JUNK_MIN = 8  # nombre de jeux différents (sur toute la carte) portant la même description


def _norm(text):
    return re.sub(r"\s+", "", text or "")


def junk_descriptions(games_by_system):
    """{console: (texte, [jeux])} : descriptions identiques (espaces non comptés) sur au moins JUNK_MIN
    jeux différents de la carte. Les versions d'un même jeu partageant leur description ne comptent qu'une fois."""
    groups = {}
    for games in games_by_system.values():
        for g in games:
            desc = _norm(g.info.get("desc"))
            if desc:
                groups.setdefault(desc, []).append(g)
    out = {}
    for group in groups.values():
        if len({(g.system, core.title_key(g.name) or g.stem.lower()) for g in group}) >= JUNK_MIN:
            for g in group:
                text, games = out.get(g.system, (g.info["desc"], []))
                out[g.system] = (text, games + [g])
    return out


NOT_GAME = re.compile(r"^zzz\s*\(notgame\)|\bnotgame\b", re.I)


def non_games(games_by_system):
    """Jeux à masquer : BIOS rangés avec les jeux et entrées marquées « notgame »."""
    out = []
    for system, games in games_by_system.items():
        for g in games:
            if g.info.get("hidden", "").lower() == "true":
                continue
            if NOT_GAME.search(g.name) or (system.lower() in arcade.SYSTEMS and arcade.is_bios(g)):
                out.append(g)
    return out
