"""Lecture de la carte : jeux, fichiers liés, régions, doublons, BIOS, correspondance d'images."""
import os

import bios
import core
import importer
import regions
import scraper


def names(games):
    return sorted(os.path.basename(g.path) for g in games)


def test_load_systems_and_games(card):
    d = core.load_all(card)
    assert set(d) == {"gba", "psx", "segacd", "ports", "psp", "n64"}
    assert names(d["gba"]) == ["Wario Land 4 (USA, Europe).gba", "Zelda (Europe) (En,Fr,De).gba", "Zelda (USA).gba"]
    zelda = next(g for g in d["gba"] if g.name == "Zelda")
    assert zelda.rating == 0.75 and zelda.playcount == 14 and zelda.lastplayed.year == 2025
    assert set(zelda.media) == {"image", "thumbnail", "video"}


def test_disc_files_are_grouped(card):
    psx = core.load_all(card)["psx"]
    mgs = [g for g in psx if "Metal Gear" in g.path]
    assert len(mgs) == 2  # .img / .sub rattachés au .ccd, pas de faux jeux
    files = names([type("G", (), {"path": p}) for p in core.game_files(next(g for g in mgs if "Disc 1" in g.path))])
    assert files == sorted(["Metal Gear Solid (EU) - (Disc 1 of 2)" + e for e in (".ccd", ".img", ".sub")])


def test_psp_savedata_is_not_a_game(card):
    assert names(core.load_all(card)["psp"]) == ["Game (Europe).iso"]


def test_ports_only_scripts_with_their_folder(card):
    ports = core.load_all(card)["ports"]
    assert names(ports) == ["Foo.sh"]
    assert any(p.endswith(os.path.join("ports", "foo")) for p in core.game_files(ports[0]))


def test_duplicates_and_arcade_exclusion(card):
    d = core.load_all(card)
    assert names(core.find_duplicates(d)) == ["Zelda (Europe) (En,Fr,De).gba", "Zelda (USA).gba"]
    d["neogeo"] = d.pop("gba")
    assert core.find_duplicates(d) == []


def test_regions():
    assert regions.describe("Zelda (USA, Europe) (En,Fr,De)") == (
        ["us", "eu"], "USA, Europe", "Anglais, Français, Allemand")
    assert regions.regions("Super Smash Bros. (E) (M3) [!]") == ["eu"]
    assert regions.languages("PES 6 (Europe) (EnFrDeEsIt)") == ["en", "fr", "de", "es", "it"]
    assert regions.regions("Tetris (World) (Rev A)") == ["world"]


def test_bios_check(card):
    found = {(s, desc): ok for s, desc, _, ok, _ in bios.check(card, ["psx", "dreamcast", "segacd"])}
    assert found[("psx", "BIOS PlayStation")] == "scph5501.bin"
    assert found[("dreamcast", "BIOS Dreamcast")] == "dc/dc_boot.bin"
    assert found[("segacd", "BIOS Sega CD / Mega-CD")] is None


def test_image_name_matching():
    names_ = ["Legend of Zelda, The - The Minish Cap (USA)", "Mario Kart - Super Circuit (USA)"]
    game = type("G", (), {"stem": "Legend of Zelda - The Minish Cap", "name": "Zelda"})()
    assert scraper.best_match(game, names_) == "Legend of Zelda, The - The Minish Cap (USA)"


def test_import_guess(card, tmp_path):
    pc = tmp_path / "pc"
    from conftest import cue, write
    write(str(pc), "a.gba")
    write(str(pc), "sub/Crash (USA).cue", cue("Crash (USA)"))
    write(str(pc), "sub/Crash (USA).bin")
    files = importer.expand([str(pc)])
    assert sorted(os.path.basename(f) for f in files) == ["Crash (USA).cue", "a.gba"]  # .bin rattaché
    available = core.list_systems(card)
    assert importer.guess_system(str(pc / "a.gba"), available) == "gba"
    assert importer.guess_system(str(pc / "sub" / "Crash (USA).cue"), available, "psx") == "psx"


def test_video_found_by_name_with_skraper_hash(card):
    from conftest import write
    write(card, "gba/media/videos/Wario Land 4 (USA, Europe) 61410ADC3AFEC234617D8BC895823AFF.mp4", b"v")
    wario = next(g for g in core.load_all(card)["gba"] if "Wario" in g.path)
    assert core.video_for(wario).endswith("61410ADC3AFEC234617D8BC895823AFF.mp4")


def test_easyroms_detection(card, tmp_path):
    assert core.looks_like_easyroms(card)
    other = tmp_path / "C_drive"
    for d in ("Windows", "Users", "Program Files"):
        (other / d).mkdir(parents=True)
    assert not core.looks_like_easyroms(str(other))
    assert not core.looks_like_easyroms(str(tmp_path / "absent"))
