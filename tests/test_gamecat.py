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
