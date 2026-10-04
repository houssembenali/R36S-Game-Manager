"""Complément des fiches depuis internet (sans réseau : les sources sont simulées)."""
import core
import metadata

DAT = '''clrmamepro (
\tname "Nintendo - Game Boy Advance"
)

game (
\tcomment "Mario Kart - Super Circuit (USA)"
\tgenre "Racing"
\trom ( crc ED316E37 )
)

game (
\tcomment "Wario Land 4 (USA, Europe)"
\tusers 2
\trom ( crc 12345678 )
)
'''


def game(stem, **info):
    return core.Game("gba", stem, f"C:/nope/{stem}.gba", "C:/nope", info={k: str(v) for k, v in info.items()})


def test_parse_dat():
    genre = metadata.parse_dat(DAT, "genre")
    assert genre["crc"] == {"ED316E37": "Racing"}
    assert genre["name"] == {"Mario Kart - Super Circuit (USA)": "Racing"}
    assert metadata.parse_dat(DAT, "maxusers")["crc"] == {"12345678": "2"}


def test_genres_and_titles():
    assert metadata.french_genre("Racing") == "Course"
    assert metadata.french_genre("Jeu de plateforme en 3D") == "Plateforme"
    assert metadata.french_genre("jeu vidéo de rôle") == "Jeu de rôles"
    assert metadata.clean_title(game("Final Fantasy VII (France) (Disc 1)")) == "Final Fantasy VII"


def test_lookup_fills_only_missing_and_never_raises(monkeypatch):
    monkeypatch.setattr(metadata, "from_libretro", lambda g: {"genre": "Racing", "year": "2001", "players": "1-4"})

    def broken(*a):
        raise OSError("pas de réseau")
    monkeypatch.setattr(metadata, "from_wikidata", broken)
    g = game("Mario Kart - Super Circuit (USA)", year="", genre="Course perso", releasedate="")
    found = metadata.lookup(g)
    assert found["year"] == "2001" and found["players"] == "1-4"
    assert "genre" not in found          # déjà renseigné : jamais écrasé
    assert found["name"] == "Mario Kart - Super Circuit"
    assert "desc" not in found           # Wikipédia injoignable : on continue sans


def test_lookup_skips_complete_cards(monkeypatch):
    monkeypatch.setattr(metadata, "from_libretro", lambda g: {"genre": "Racing"})
    full = game("Zelda (USA)", desc="x", genre="Aventure", releasedate="20040101T000000",
                developer="Nintendo", publisher="Nintendo", players="1")
    full.name = "Zelda"
    assert metadata.lookup(full) == {}
