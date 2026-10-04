"""Fausse carte EASYROMS reproduisant les cas réels rencontrés sur la R36S.

Lancer les tests :  python -m pytest -q        (depuis le dossier du programme)
"""
import hashlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import journal  # noqa: E402

CD_SIZE = 2352 * 150  # piste CD valide pour chdman


def write(root, rel, data=b"x"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else
                                                                    {"encoding": "utf-8"})) as f:
        f.write(data)
    return path


def cue(name):
    return f'FILE "{name}.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'


def gamelist(*games):
    return '<?xml version="1.0"?>\n<gameList>\n' + "\n".join(games) + "\n</gameList>\n"


@pytest.fixture
def card(tmp_path):
    root = str(tmp_path / "EASYROMS")
    # --- Game Boy Advance : fiche Skraper complète, doublon, sauvegarde, médias orphelins
    write(root, "gba/Zelda (USA).gba")
    write(root, "gba/Zelda (Europe) (En,Fr,De).gba")
    write(root, "gba/Wario Land 4 (USA, Europe).gba")
    write(root, "gba/Wario Land 4 (USA, Europe).srm", b"save")
    write(root, "gba/Ace Combat (USA).srm", b"orphan save")
    write(root, "gba/media/images/Zelda (USA) ABC.png")
    write(root, "gba/media/box3d/Zelda (USA).png")
    write(root, "gba/media/videos/Zelda (USA).mp4", b"video" * 100)
    write(root, "gba/downloaded_images/Gone (USA).png", b"orphan")
    write(root, "gba/gamelist.xml.old", b"old")
    write(root, "gba/gamelist.xml", gamelist(
        '<game id="1" source="ScreenScraper.fr"><path>./Zelda (USA).gba</path><name>Zelda</name>'
        '<desc>Un jeu</desc><rating>0.75</rating><releasedate>20040101T000000</releasedate>'
        '<playcount>14</playcount><lastplayed>20250101T120000</lastplayed>'
        '<image>./media/images/Zelda (USA) ABC.png</image><thumbnail>./media/box3d/Zelda (USA).png</thumbnail>'
        '<video>./media/videos/Zelda (USA).mp4</video></game>',
        '<game><path>./Gone (USA).gba</path><name>Gone</name></game>'))
    # --- PlayStation : jeux multi-disques (.cue/.bin et .ccd/.img/.sub)
    for n in (1, 2, 3):
        name = f"Final Fantasy VII (France) (Disc {n})"
        write(root, f"psx/# HOOS #/{name}.cue", cue(name))
        write(root, f"psx/# HOOS #/{name}.bin", bytes(CD_SIZE))
    write(root, "psx/# HOOS #/Final Fantasy VII (France) (Disc 1).srm", b"memcard")
    for n in (1, 2):
        base = f"psx/# HOOS #/Metal Gear Solid (EU) - (Disc {n} of 2)"
        for ext in (".ccd", ".img", ".sub"):
            write(root, base + ext)
    write(root, "psx/media/videos/ff7.mp4", b"v" * 50)
    write(root, "psx/gamelist.xml", gamelist(
        '<game><path>./# HOOS #/Final Fantasy VII (France) (Disc 1).cue</path><name>Final Fantasy VII</name>'
        '<rating>0.9</rating><favorite>true</favorite></game>'))
    # --- Sega CD : ROM Mega Drive mal rangée
    write(root, "segacd/Tintin au Tibet (Europe).md")
    write(root, "segacd/media/images/Tintin au Tibet (Europe).png")
    write(root, "segacd/gamelist.xml", gamelist(
        '<game><path>./Tintin au Tibet (Europe).md</path><name>Tintin</name>'
        '<image>./media/images/Tintin au Tibet (Europe).png</image></game>'))
    os.makedirs(os.path.join(root, "megadrive"))
    # --- Ports : seuls les .sh comptent, le dossier du port part avec
    write(root, "ports/Foo.sh", "#!/bin/bash\nGAMEDIR=/$directory/ports/foo\n")
    write(root, "ports/foo/data.bin")
    write(root, "ports/README.md")
    # --- PSP : sauvegarde PPSSPP inscrite par erreur dans le gamelist (ne doit pas être un jeu)
    write(root, "psp/Game (Europe).iso")
    write(root, "psp/ppsspp/PSP/SAVEDATA/ULES001/DATA.BIN", b"psp save")
    write(root, "psp/gamelist.xml", gamelist(
        '<game><path>./ppsspp/PSP/SAVEDATA/ULES001/DATA.BIN</path><name>DATA</name></game>'))
    # --- N64 : sauvegarde nommée d'après la ROM interne (ne doit pas être orpheline)
    write(root, "n64/Super Smash Bros..n64")
    write(root, "n64/Super Smash Bros. (E) (M3) [!]-5E54C6C5.sra", b"n64 save")
    # --- BIOS
    write(root, "bios/dc/dc_boot.bin")
    write(root, "bios/scph5501.bin")
    return root


def snapshot(root):
    """Contenu de la carte (hors corbeille) : {chemin relatif: empreinte}."""
    out = {}
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != journal.TRASH]
        for f in files:
            p = os.path.join(dirpath, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.md5(fh.read()).hexdigest()
    return out


def undo_last(root):
    """Annule la dernière opération et retourne les erreurs."""
    op_id = journal.history(root)[0][0]
    return journal.undo(root, op_id)
