"""Vérification de la carte SD et doublons sur toute la carte."""
import os
import zipfile

import core
import dupes
import health
import i18n
from conftest import gamelist, write


def test_card_check_finds_damaged_files(tmp_path):
    root = str(tmp_path / "card")
    write(root, "nes/Good.nes", b"rom" * 100)
    good_zip = os.path.join(root, "snes", "Good.zip")
    os.makedirs(os.path.dirname(good_zip))
    with zipfile.ZipFile(good_zip, "w", zipfile.ZIP_STORED) as z:
        z.writestr("good.sfc", b"A" * 5000)
    data = bytearray(open(good_zip, "rb").read())
    data[100] ^= 0xFF  # un octet change dans le contenu : l'empreinte (CRC) ne correspond plus
    write(root, "snes/Broken.zip", bytes(data))
    write(root, "gba/Empty.gba", b"")
    write(root, "gba/notes.txt", b"")  # fichier vide sans importance
    write(root, "gba/gamelist.xml", "<gameList><game>")
    write(root, ".r36s-corbeille/old/Broken.gba", b"")  # la corbeille n'est pas vérifiée
    r = health.check(root)
    found = sorted((p.kind, os.path.basename(p.path)) for p in r.problems)
    assert found == [("corrupt", "Broken.zip"), ("empty", "Empty.gba"), ("gamelist", "gamelist.xml")]
    assert r.files == 6 and r.read == r.total and not r.cancelled


def test_dupes_identical_copies_and_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n, "LANG", "fr")
    root = str(tmp_path / "card")
    write(root, "gb/Tetris (World).gb", b"T" * 300)
    write(root, "gbc/Tetris (World).gb", b"T" * 300)        # même fichier, mauvaise console
    write(root, "gbc/Other (USA).gbc", b"O" * 300)          # même taille, contenu différent
    write(root, "snes/Mario (USA).sfc", b"U" * 10)
    write(root, "snes/Mario (Europe) (Fr).sfc", b"E" * 10)
    write(root, "snes/Mario (Beta).sfc", b"B" * 10)
    write(root, "snes/Zelda (USA).sfc", b"Z1")
    write(root, "snes/Zelda (Europe).sfc", b"Z2")
    write(root, "snes/gamelist.xml", gamelist(
        "<game><path>./Zelda (USA).sfc</path><name>Zelda</name><playcount>4</playcount></game>"))
    write(root, "psx/FF7 (Disc 1).chd", b"1")
    write(root, "psx/FF7 (Disc 2).chd", b"2")
    core.clear_cache()
    found = {(d.game.system, d.game.stem): (d.keep.system, d.keep.stem, d.kind, d.checked)
             for d in dupes.find(core.load_all(root))}
    assert found == {
        ("gbc", "Tetris (World)"): ("gb", "Tetris (World)", "copy", True),
        ("snes", "Mario (USA)"): ("snes", "Mario (Europe) (Fr)", "version", True),
        ("snes", "Mario (Beta)"): ("snes", "Mario (Europe) (Fr)", "version", True),
        # la version jouée est gardée même si la région préférée est l'Europe ; l'autre n'a rien d'important
        ("snes", "Zelda (Europe)"): ("snes", "Zelda (USA)", "version", True),
    }
