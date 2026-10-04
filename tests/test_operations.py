"""Opérations qui modifient la carte : chacune doit marcher ET s'annuler à l'identique."""
import io
import os

import pytest
from PIL import Image

import chd
import cleanup
import core
import importer
import journal
import multidisc
import saves
import scraper
from conftest import CD_SIZE, snapshot, undo_last, write


def game(card, system, part):
    return next(g for g in core.load_all(card)[system] if part in g.path)


def run(card, label, fn):
    """Exécute fn() dans une opération annulable et retourne le résultat."""
    with journal.operation(card, label):
        return fn()


def assert_undo_restores(card, before):
    assert undo_last(card) == []
    assert snapshot(card) == before


def test_delete_game_then_undo(card):
    before = snapshot(card)
    d = core.load_all(card)
    zelda = game(card, "gba", "Zelda (USA)")
    files = core.files_to_delete(zelda, d["gba"])
    assert run(card, "Suppression", lambda: core.delete_game(card, zelda, files)) == []
    assert not os.path.exists(zelda.path)
    assert "Zelda (USA).gba" not in open(os.path.join(card, "gba", "gamelist.xml"), encoding="utf-8").read()
    assert journal.trash_size(card) > 0
    assert_undo_restores(card, before)


def test_favorites_and_info_then_undo(card):
    before = snapshot(card)
    g = game(card, "gba", "Wario")  # absent du gamelist : sa fiche est créée
    run(card, "Favori", lambda: core.set_favorites(card, [g], True))
    run(card, "Fiche", lambda: core.set_info(card, g, {"name": "Wario 4", "rating": 0.5, "year": "2001"}))
    again = game(card, "gba", "Wario")
    assert again.favorite and again.name == "Wario 4" and again.rating == 0.5
    assert again.info["releasedate"] == "20010101T000000"
    assert undo_last(card) == [] and undo_last(card) == []
    assert snapshot(card) == before


def test_move_game_then_undo(card):
    before = snapshot(card)
    tintin = game(card, "segacd", "Tintin")
    assert run(card, "Déplacement", lambda: core.move_game(card, tintin, "megadrive", [tintin])) == []
    moved = core.load_all(card)["megadrive"][0]
    assert moved.name == "Tintin" and os.path.isfile(moved.media["image"])
    assert_undo_restores(card, before)


def test_multidisc_then_undo(card):
    before = snapshot(card)
    groups = multidisc.find_groups(core.load_all(card))
    assert sorted((g.name, len(g.discs)) for g in groups) == [("Final Fantasy VII", 3), ("Metal Gear Solid (EU)", 2)]
    for gr in groups:
        assert run(card, "Multi-disques", lambda gr=gr: multidisc.create_m3u(card, gr))[1] == []
    psx = core.load_all(card)["psx"]
    ff7 = next(g for g in psx if "Final" in g.path)
    assert len(psx) == 2 and ff7.path.endswith(".m3u") and ff7.rating == 0.9 and ff7.favorite
    assert os.path.isfile(os.path.join(os.path.dirname(ff7.path), "Final Fantasy VII (France).srm"))
    assert undo_last(card) == [] and undo_last(card) == []
    assert snapshot(card) == before


@pytest.mark.skipif(not chd.find_chdman(), reason="chdman absent (tools/chdman.exe)")
def test_chd_compression_then_undo(card):
    before = snapshot(card)
    ff7 = game(card, "psx", "(Disc 2).cue")
    assert run(card, "CHD", lambda: chd.convert_game(card, chd.find_chdman(), ff7)) == []
    assert ff7.path.endswith(".chd") and 0 < os.path.getsize(ff7.path) < CD_SIZE
    assert not os.path.exists(ff7.path[:-4] + ".bin")
    assert_undo_restores(card, before)


def test_cleanup_then_undo(card):
    before = snapshot(card)
    d = core.load_all(card)
    issues = cleanup.scan(card, d)
    found = {(i.kind, os.path.basename(i.path)) for i in issues}
    assert ("media", "Gone (USA).png") in found
    assert ("entry", "Gone (USA).gba") in found
    assert ("save", "Ace Combat (USA).srm") in found
    assert ("oldlist", "gamelist.xml.old") in found
    assert ("misplaced", "Tintin au Tibet (Europe).md") in found
    kinds = {i.kind for i in issues}
    assert not any("5E54C6C5" in i.path for i in issues)  # sauvegarde N64 gardée
    assert not any("SAVEDATA" in i.path for i in issues)  # sauvegarde PSP gardée
    assert kinds == {"media", "entry", "save", "oldlist", "misplaced"}
    removed, errors, count = run(card, "Nettoyage", lambda: cleanup.clean(card, issues, d))
    assert errors == [] and count == len(issues)
    assert cleanup.scan(card, core.load_all(card)) == []
    assert_undo_restores(card, before)


def test_set_image_then_undo(card):
    before = snapshot(card)
    d = core.load_all(card)
    zelda = next(g for g in d["gba"] if g.name == "Zelda")
    buf = io.BytesIO()
    Image.new("RGB", (1000, 800), "red").save(buf, "PNG")
    assert run(card, "Image", lambda: scraper.set_image(card, zelda, "image", buf.getvalue(), d["gba"])) == []
    new = game(card, "gba", "Zelda (USA)").media["image"]
    with Image.open(new) as im:
        assert im.format == "JPEG" and max(im.size) <= 480
    assert "./media/images/Zelda (USA).jpg" in open(os.path.join(card, "gba", "gamelist.xml"), encoding="utf-8").read()
    assert not os.path.exists(os.path.join(card, "gba", "media", "images", "Zelda (USA) ABC.png"))
    assert_undo_restores(card, before)


def test_delete_videos_then_undo(card):
    before = snapshot(card)
    d = core.load_all(card)
    assert len(core.video_files(card, "gba")) == 1
    assert run(card, "Vidéos", lambda: core.delete_videos(card, "gba", d["gba"])) == []
    assert core.video_files(card, "gba") == []
    assert "<video>" not in open(os.path.join(card, "gba", "gamelist.xml"), encoding="utf-8").read()
    assert_undo_restores(card, before)


def test_import_then_undo(card, tmp_path):
    before = snapshot(card)
    rom = write(str(tmp_path / "pc"), "New Game (USA).gba", b"rom")
    copied, errors = run(card, "Ajout", lambda: importer.import_files(card, [(rom, "gba")]))
    assert errors == [] and os.path.isfile(copied[0])
    assert_undo_restores(card, before)


def test_saves_backup_and_restore_then_undo(card, tmp_path):
    files = saves.collect(card)
    rels = sorted(os.path.relpath(f, card) for f in files)
    assert os.path.join("gba", "Wario Land 4 (USA, Europe).srm") in rels
    assert any("SAVEDATA" in r for r in rels) and any(r.endswith(".sra") for r in rels)
    archive = str(tmp_path / "saves.zip")
    assert saves.backup(card, files, archive) == len(files)
    wario = os.path.join(card, "gba", "Wario Land 4 (USA, Europe).srm")
    write(card, "gba/Wario Land 4 (USA, Europe).srm", b"newer progress")
    before = snapshot(card)
    restored, skipped = run(card, "Restauration", lambda: saves.restore(card, archive, True))
    assert restored == len(files) and open(wario, "rb").read() == b"save"
    assert_undo_restores(card, before)  # la sauvegarde plus récente revient


def test_history_keeps_last_operations(card):
    for i in range(journal.KEEP + 3):
        g = game(card, "gba", "Wario")
        run(card, f"op {i}", lambda g=g, i=i: core.set_favorites(card, [g], i % 2 == 0))
    hist = journal.history(card)
    assert len(hist) == journal.KEEP and hist[0][1] == f"op {journal.KEEP + 2}"
    journal.empty_trash(card)
    assert journal.history(card) == [] and journal.trash_size(card) == 0
