"""Filtres de la liste des jeux."""
import core
import filters


def g(stem, **info):
    game = core.Game("gba", stem, f"/x/{stem}.gba", "/x", info={k: str(v) for k, v in info.items()})
    return game


def test_main_genre_and_players():
    assert filters.main_genre(g("a", genre="Tir / 1ere Personne-Tir")) == "Tir"
    assert filters.main_genre(g("a", genre="Action-Plateforme")) == "Action"
    assert filters.main_genre(g("a", genre="sport / Golf,Sport")) == "Sport"
    assert filters.max_players(g("a", players="1-4")) == 4
    assert filters.max_players(g("a")) == 0


def test_apply_combined():
    games = [g("Street Fighter (USA)", genre="Combat", players="1-2", playcount=0),
             g("Tekken (Japan)", genre="Combat / 3D", players="1-2", playcount=3, rating=0.8),
             g("Zelda (Europe)", genre="Aventure", players="1"),
             g("Solo Fight (USA)", genre="Combat", players="1")]
    f = dict(filters.EMPTY, genre="Combat", players=2)
    assert [x.name for x in filters.apply(games, f)] == ["Street Fighter (USA)", "Tekken (Japan)"]
    f["never"] = True
    assert [x.name for x in filters.apply(games, f)] == ["Street Fighter (USA)"]
    assert filters.active_count(f) == 3
    one = dict(filters.EMPTY, players=1)
    assert [x.name for x in filters.apply(games, one)] == ["Zelda (Europe)", "Solo Fight (USA)"]
    jp = dict(filters.EMPTY, region="jp")
    assert [x.name for x in filters.apply(games, jp)] == ["Tekken (Japan)"]
    norating = dict(filters.EMPTY, norating=True)
    assert "Tekken (Japan)" not in [x.name for x in filters.apply(games, norating)]
    assert filters.apply(games, dict(filters.EMPTY)) is games
