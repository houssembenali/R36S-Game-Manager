"""Arcade incomplets, fiches à nettoyer, statistiques, copie de carte, thèmes."""
import io
import os
import zipfile

import arcade
import cardcopy
import cardfix
import core
import metadata
import stats
import themes
from conftest import gamelist, write

DAT = """<datafile>
<game isbios="yes" name="neogeo" sourcefile="neogeo/d_neogeo.cpp"><description>Neo Geo</description>
<rom name="sp-s2.sp1" size="4" crc="11111111"/></game>
<game name="mslug" romof="neogeo" sourcefile="neogeo/d_neogeo.cpp"><description>Metal Slug</description>
<rom name="201-p1.p1" size="4" crc="22222222"/><rom name="sp-s2.sp1" merge="sp-s2.sp1" size="4" crc="11111111"/></game>
<game name="mslugj" cloneof="mslug" romof="mslug" sourcefile="neogeo/d_neogeo.cpp"><description>Metal Slug (Japan)</description>
<rom name="201-pj.p1" size="4" crc="33333333"/><rom name="201-p1.p1" merge="201-p1.p1" size="4" crc="22222222"/>
<rom name="sp-s2.sp1" merge="sp-s2.sp1" size="4" crc="11111111"/></game>
</datafile>"""


def rom_zip(path, *crcs):
    """.zip dont les fichiers ont exactement ces CRC (contenu fabriqué pour les obtenir)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for i, crc in enumerate(crcs):
            info = zipfile.ZipInfo(f"rom{i}")
            z.writestr(info, crc.encode())
    data = bytearray(open(path, "rb").read())
    with zipfile.ZipFile(io.BytesIO(bytes(data))) as z:  # remplace le CRC calculé par celui voulu
        for info, crc in zip(z.infolist(), crcs):
            real = info.CRC.to_bytes(4, "little")
            data = data.replace(real, int(crc, 16).to_bytes(4, "little"))
    open(path, "wb").write(bytes(data))


def test_arcade_missing_parent_and_bios(card, monkeypatch):
    monkeypatch.setattr(metadata, "fbneo_text", lambda: DAT)
    arcade._db.clear()
    arcade._checked.clear()
    rom_zip(os.path.join(card, "neogeo", "mslugj.zip"), "33333333")
    core.clear_cache()
    game = {g.stem: g for g in core.load_all(card)["neogeo"]}["mslugj"]
    assert arcade.missing(card, game) == [("neogeo.zip", "bios"), ("mslug.zip", "parent")]
    rom_zip(os.path.join(card, "bios", "neogeo.zip"), "11111111")
    rom_zip(os.path.join(card, "neogeo", "mslug.zip"), "22222222")
    arcade._checked.clear()
    assert arcade.missing(card, game) == []
    rom_zip(os.path.join(card, "neogeo", "neogeo.zip"), "11111111")  # BIOS rangé avec les jeux
    core.clear_cache()
    bios = {g.stem: g for g in core.load_all(card)["neogeo"]}
    assert arcade.is_bios(bios["neogeo"]) and not arcade.is_bios(bios["mslug"])
    arcade._db.clear()


def test_cardfix_junk_and_non_games(card):
    junk = "游 戏 资 源 来 自 网 路"
    entries = [f"<game><path>./g{i}.zip</path><name>Game {i}</name><desc>{junk}</desc></game>" for i in range(8)]
    entries.append("<game><path>./bios.zip</path><name>ZZZ(notgame):#bios</name></game>")
    for i in range(8):
        write(card, f"cps1/g{i}.zip")
    write(card, "cps1/bios.zip")
    write(card, "cps1/gamelist.xml", gamelist(*entries))
    core.clear_cache()
    games = core.load_all(card)
    found = cardfix.junk_descriptions(games)
    assert list(found) == ["cps1"] and len(found["cps1"][1]) == 8
    hide = cardfix.non_games(games)
    assert [g.name for g in hide] == ["ZZZ(notgame):#bios"]
    core.clear_descriptions(card, found["cps1"][1])
    core.set_hidden(card, hide, True)
    core.clear_cache()
    games = core.load_all(card)
    assert cardfix.junk_descriptions(games) == {} and cardfix.non_games(games) == []
    text = open(os.path.join(card, "cps1", "gamelist.xml"), encoding="utf-8").read()
    assert "<hidden>true</hidden>" in text and junk not in text


def test_stats(card):
    s = stats.compute(core.load_all(card))
    assert s.total > 0 and s.systems > 0 and s.played == len(s.top_played) or len(s.top_played) == 10
    assert all(a.playcount >= b.playcount for a, b in zip(s.top_played, s.top_played[1:]))


def test_cardcopy_is_incremental(tmp_path):
    src, dst = str(tmp_path / "card"), str(tmp_path / "backup")
    write(src, "gba/a.gba", b"A" * 10)
    write(src, "gba/b.gba", b"B" * 20)
    write(src, ".r36s-corbeille/x/old.gba", b"x")  # la corbeille n'est pas copiée
    items = cardcopy.plan(src, dst)
    assert sorted(os.path.basename(s) for s, _d, _n in items) == ["a.gba", "b.gba"]
    assert cardcopy.copy(items) == (2, [])
    assert cardcopy.plan(src, dst) == []  # tout est déjà copié
    write(src, "gba/b.gba", b"B" * 21)
    assert [os.path.basename(s) for s, _d, _n in cardcopy.plan(src, dst)] == ["b.gba"]


def test_themes_list_and_install(card, tmp_path):
    write(card, "themes/full/theme.xml", "<theme/>")
    write(card, "themes/full/preview.png", b"png")
    write(card, "themes/partial/dragon32/theme.xml", "<theme/>")
    listed = {t.name: t for t in themes.list_themes(card)}
    assert listed["full"].generic and listed["full"].preview.endswith("preview.png")
    assert listed["partial"].systems == {"dragon32"} and listed["partial"].missing(["gba", "dragon32"]) == ["gba"]
    archive = tmp_path / "cool-theme.zip"
    with zipfile.ZipFile(archive, "w") as z:  # dossier en trop dans l'archive, comme sur GitHub
        z.writestr("cool-theme-main/theme.xml", "<theme/>")
        z.writestr("cool-theme-main/gba/theme.xml", "<theme/>")
    dest = themes.install(card, str(archive))
    assert os.path.isfile(os.path.join(dest, "gba", "theme.xml")) and os.path.basename(dest) == "cool-theme-main"
    bad = tmp_path / "nope.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("readme.txt", "x")
    import pytest
    with pytest.raises(ValueError):
        themes.install(card, str(bad))
