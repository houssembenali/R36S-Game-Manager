"""Statistiques de la collection : parties, consoles préférées, jeux jamais lancés, genres."""
from collections import Counter
from dataclasses import dataclass, field

import filters


@dataclass
class Stats:
    total: int = 0
    systems: int = 0
    size: int = 0
    favorites: int = 0
    played: int = 0                 # jeux lancés au moins une fois
    plays: int = 0                  # nombre total de parties
    never_size: int = 0             # place des jeux jamais lancés
    top_played: list = field(default_factory=list)    # [jeu] les plus joués
    recent: list = field(default_factory=list)        # [jeu] derniers joués
    by_system: list = field(default_factory=list)     # [(console, jeux, taille, jeux joués, parties)]
    genres: list = field(default_factory=list)        # [(genre, jeux)]
    biggest_never: list = field(default_factory=list)  # [jeu] gros jeux jamais lancés


def compute(games_by_system, top=10):
    games = [g for lst in games_by_system.values() for g in lst
             if (g.info.get("hidden") or "").lower() != "true"]
    played = [g for g in games if g.playcount]
    never = [g for g in games if not g.playcount]
    by_system = []
    for system, lst in games_by_system.items():
        by_system.append((system, len(lst), sum(g.size for g in lst), sum(1 for g in lst if g.playcount),
                          sum(g.playcount for g in lst)))
    by_system.sort(key=lambda r: (-r[4], -r[1]))
    genres = Counter(filters.main_genre(g) for g in games if filters.main_genre(g))
    return Stats(
        total=len(games), systems=len(games_by_system), size=sum(g.size for g in games),
        favorites=sum(1 for g in games if g.favorite), played=len(played),
        plays=sum(g.playcount for g in played), never_size=sum(g.size for g in never),
        top_played=sorted(played, key=lambda g: (-g.playcount, g.name.lower()))[:top],
        recent=sorted((g for g in games if g.lastplayed), key=lambda g: g.lastplayed, reverse=True)[:top],
        by_system=by_system, genres=genres.most_common(top),
        biggest_never=sorted(never, key=lambda g: -g.size)[:top])
