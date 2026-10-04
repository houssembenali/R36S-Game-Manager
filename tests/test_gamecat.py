"""Catalogue de jeux : liste des jeux sortis, jeux présents sur la carte, jeux gratuits installables."""
import contextlib
import io
import json
import os

import core
import gamecat
import metadata
from conftest import write

DAT = """clrmamepro (
\tname "Nintendo - Super Nintendo Entertainment System"
)

game (
\tname "Legend of Zelda, The - A Link to the Past (Europe)"
\trom ( name "x.sfc" size 1 crc 00000001 )
)
game (
\tname "Legend of Zelda, The - A Link to the Past (USA)"
\trom ( name "y.sfc" size 1 crc 00000002 )
)
game (
\tname "Super Mario World (USA) (Beta)"
\trom ( name "z.sfc" size 1 crc 00000003 )
)
game (
\tname "F-Zero (Japan)"
\trom ( name "f.sfc" size 1 crc 00000004 )
)
"""


def test_commercial_list_groups_versions_and_finds_owned(card, monkeypatch):
    monkeypatch.setattr(gamecat, "_dat_text", lambda name: DAT)
    genre = {"name": {"Legend of Zelda, The - A Link to the Past (USA)": "Action"}, "crc": {}}
    monkeypatch.setattr(metadata, "_dat", lambda field, name: genre if field == "genre" else {"name": {}, "crc": {}})
    entries = gamecat.commercial("snes")
    assert [e.title for e in entries] == ["F-Zero", "The Legend of Zelda - A Link to the Past"]  # sans la Beta
    zelda = entries[1]
    assert zelda.names[0].endswith("(Europe)") and zelda.regions == ["eu", "us"] and zelda.genre == "Action"
    write(card, "snes/Legend of Zelda, The - A Link to the Past (France).sfc")
    core.clear_cache()
    keys = gamecat.owned_keys(core.load_all(card)["snes"])
    assert [gamecat.owned(e, keys) for e in entries] == [False, True]


def test_homebrew_list_and_install(card, tmp_path, monkeypatch):
    monkeypatch.setattr(gamecat, "CACHE_DIR", str(tmp_path / "cache"))
    pages = {1: {"page_total": 2, "entries": [{
        "title": " Star Game ", "slug": "star", "basepath": "database-gba", "developer": [{"name": "Ann"}],
        "tags": ["event:jam", "2d", "platformer"], "license": "MIT", "date": "2024-05-01",
        "files": [{"filename": "files/star.gba", "default": True, "playable": True}],
        "screenshots": ["cover.png"], "description": "A game."}]},
        2: {"page_total": 2, "entries": [{"title": "No Rom", "slug": "x", "files": []}]}}
    asked = []

    def fake_get(url, timeout=30):
        asked.append(url)
        return json.dumps(pages[int(url.rsplit("=", 1)[1])]).encode()
    monkeypatch.setattr(gamecat.net, "get", fake_get)
    entries = gamecat.free_games("gba")
    assert len(asked) == 2 and [e.title for e in entries] == ["Star Game"]
    e = entries[0]
    assert e.free and e.filename == "Star Game.gba" and e.genre == "Plateforme" and e.developer == "Ann"
    assert e.url.endswith("/database-gba/entries/star/files/star.gba") and e.image.endswith("/star/cover.png")
    gamecat.free_games("gba")
    assert len(asked) == 2  # deuxième fois : depuis le cache
    monkeypatch.setattr(gamecat.net, "open_url", lambda url, timeout=60: contextlib.closing(io.BytesIO(b"ROM")))
    path = gamecat.install(card, e)
    assert path == os.path.join(card, "gba", "Star Game.gba") and open(path, "rb").read() == b"ROM"
    assert "Licence : MIT" in gamecat.card_values(e)["desc"]
    assert gamecat.owned(e, set(), {"star game.gba"})


def test_freedoom_wad_is_extracted(card, monkeypatch):
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("freedoom-0.13.0/freedoom1.wad", b"WAD1")
        z.writestr("freedoom-0.13.0/freedoom2.wad", b"WAD2")
    monkeypatch.setattr(gamecat.net, "open_url", lambda url, timeout=60: contextlib.closing(io.BytesIO(buf.getvalue())))
    e = gamecat.Entry("Freedoom: Phase 2", "doom", free=True, url="u", filename="freedoom2.wad")
    assert open(gamecat.install(card, e), "rb").read() == b"WAD2"


def test_display_title():
    assert gamecat.display_title("Legend of Zelda, The - A Link to the Past") == \
        "The Legend of Zelda - A Link to the Past"
    assert gamecat.display_title("Tetris") == "Tetris"


LAUNCHBOX_XML = b"""<?xml version="1.0"?>
<LaunchBox>
  <Game><Name>Castlevania: Aria of Sorrow</Name><Platform>Nintendo Game Boy Advance</Platform>
    <CommunityRating>4.61</CommunityRating><CommunityRatingCount>378</CommunityRatingCount><DatabaseID>7</DatabaseID></Game>
  <Game><Name>Obscure Game</Name><Platform>Nintendo Game Boy Advance</Platform>
    <CommunityRating>5</CommunityRating><CommunityRatingCount>1</CommunityRatingCount><DatabaseID>8</DatabaseID></Game>
  <Game><Name>Halo</Name><Platform>Xbox</Platform>
    <CommunityRating>4</CommunityRating><CommunityRatingCount>99</CommunityRatingCount><DatabaseID>10</DatabaseID></Game>
  <Game><Name>Half-Life</Name><Platform>Windows</Platform>
    <CommunityRating>4</CommunityRating><CommunityRatingCount>99</CommunityRatingCount><DatabaseID>9</DatabaseID></Game>
  <GameAlternateName><AlternateName>Castlevania: Akatsuki no Minuet</AlternateName><DatabaseID>7</DatabaseID></GameAlternateName>
  <GameImage><DatabaseID>7</DatabaseID><FileName>x.png</FileName></GameImage>
</LaunchBox>"""


def test_ratings_merge_versions_and_rank_by_score():
    table = gamecat.parse_launchbox(io.BytesIO(LAUNCHBOX_XML))
    assert set(table) == {"Nintendo Game Boy Advance", "Windows"}  # Windows : jeux originaux des ports
    entries = [gamecat.Entry("Castlevania - Akatsuki no Minuet", "gba", "castlevaniaakatsukinominuet",
                             ["Castlevania - Akatsuki no Minuet (Japan)"], ["jp"], year="2003"),
               gamecat.Entry("Castlevania - Aria of Sorrow", "gba", "castlevaniaariaofsorrow",
                             ["Castlevania - Aria of Sorrow (Europe)"], ["eu"], year="2003"),
               gamecat.Entry("Obscure Game", "gba", "obscuregame", ["Obscure Game (USA)"], ["us"])]
    merged = gamecat.apply_ratings(entries, table)
    assert [e.title for e in merged] == ["Castlevania - Aria of Sorrow", "Obscure Game"]
    cv = merged[0]
    assert (cv.rating, cv.votes) == (4.61, 378) and cv.regions == ["jp", "eu"] and len(cv.names) == 2
    assert cv.names[0].endswith("(Europe)")
    assert cv.score > merged[1].score  # 5/5 avec un seul vote passe derrière 4,6/5 avec 378 votes
    from dialogs import stars
    assert stars(4.61) == "★★★★☆ 4,6" and stars(4.8) == "★★★★★ 4,8"


def test_arcade_real_names(card, monkeypatch):
    import metadata
    from conftest import gamelist
    text = '<game name="ffight" sourcefile="cps1.cpp">\n\t\t<description>Final Fight (World, set 1)</description>'
    assert metadata.parse_fbneo(text) == {"ffight": "Final Fight (World, set 1)"}
    monkeypatch.setattr(metadata, "arcade_titles", lambda: {"ffight": "Final Fight (World, set 1)"})
    write(card, "cps1/ffight.zip")
    write(card, "cps1/wofsjc.zip")
    write(card, "cps1/strider.zip")
    write(card, "cps1/gamelist.xml", gamelist(
        "<game><path>./ffight.zip</path><name>010 ffight</name></game>",
        "<game><path>./wofsjc.zip</path><name>019 wofsjc</name></game>",
        "<game><path>./strider.zip</path><name>Strider</name></game>"))
    core.clear_cache()
    names = {g.stem: metadata.arcade_name(g) for g in core.load_all(card)["cps1"]}
    assert names == {"ffight": "Final Fight", "wofsjc": "wofsjc", "strider": None}


FBNEO = """<datafile>
\t<game name="mslug" romof="neogeo" sourcefile="neogeo/d_neogeo.cpp">
\t\t<description>Metal Slug - Super Vehicle-001</description>
\t\t<year>1996</year>
\t\t<manufacturer>Nazca</manufacturer>
\t</game>
\t<game name="mslugh" cloneof="mslug" romof="mslug" sourcefile="neogeo/d_neogeo.cpp">
\t\t<description>Metal Slug (Japan)</description>
\t\t<year>1996</year>
\t</game>
\t<game name="mslug3b6" cloneof="mslug" romof="mslug" sourcefile="neogeo/d_neogeo.cpp">
\t\t<description>Metal Slug 6 (bootleg of Metal Slug 3)</description>
\t</game>
\t<game name="aof" romof="neogeo" sourcefile="neogeo/d_neogeo.cpp">
\t\t<description>Art of Fighting / Ryuuko no Ken (NGM-044 ~ NGH-044)</description>
\t\t<year>1992</year>
\t</game>
\t<game name="ffight" sourcefile="capcom/d_cps1.cpp">
\t\t<description>Final Fight (World, set 1)</description>
\t</game>
</datafile>"""


def test_arcade_catalogue_from_fbneo(card, monkeypatch):
    monkeypatch.setattr(metadata, "fbneo_text", lambda: FBNEO)
    neogeo = gamecat.commercial("neogeo")
    assert [e.title for e in neogeo] == ["Art of Fighting", "Metal Slug - Super Vehicle-001"]  # ni CPS, ni bootleg
    ms = neogeo[1]
    assert ms.codes == ["mslug", "mslugh"] and ms.year == "1996" and ms.developer == "Nazca"
    assert ms.regions == ["jp"] and ms.thumbs == gamecat.ARCADE_THUMBS
    assert [e.title for e in gamecat.commercial("cps1")] == ["Final Fight"]
    write(card, "neogeo/mslugh.zip")  # la version japonaise suffit pour « sur ta carte »
    core.clear_cache()
    keys = gamecat.owned_keys(core.load_all(card)["neogeo"])
    assert [gamecat.owned(e, keys) for e in neogeo] == [False, True]
