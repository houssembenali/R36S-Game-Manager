"""Vérification des BIOS : fichiers système dont certaines consoles ont besoin pour démarrer.

REQUIREMENTS : système -> [(description, niveau, [noms possibles])]
Il suffit qu'UN des noms possibles soit présent dans le dossier bios (sous-dossiers compris).
Niveaux : « requis » (le jeu ne démarre pas sans), « recommandé » (meilleure compatibilité),
« optionnel ».
"""
import os

REQUIRED, RECOMMENDED, OPTIONAL = "requis", "recommandé", "optionnel"

REQUIREMENTS = {
    "psx": [("BIOS PlayStation", RECOMMENDED,
             ["scph5501.bin", "scph5500.bin", "scph5502.bin", "scph1001.bin", "scph7001.bin",
              "scph101.bin", "psxonpsp660.bin"])],
    "segacd": [("BIOS Sega CD / Mega-CD", REQUIRED,
                ["bios_CD_E.bin", "bios_CD_U.bin", "bios_CD_J.bin"])],
    "saturn": [("BIOS Saturn", REQUIRED, ["sega_101.bin", "mpr-17933.bin", "saturn_bios.bin"])],
    "dreamcast": [("BIOS Dreamcast", REQUIRED, ["dc/dc_boot.bin", "dc_boot.bin"]),
                  ("Flash Dreamcast", RECOMMENDED, ["dc/dc_flash.bin", "dc_flash.bin"])],
    "neogeo": [("BIOS Neo Geo", REQUIRED, ["neogeo.zip"])],
    "neogeocd": [("BIOS Neo Geo CD", REQUIRED, ["neocd/neocd.bin", "neocd.bin", "neocd/front-sp1.bin"])],
    "pcenginecd": [("Carte système CD", REQUIRED, ["syscard3.pce"])],
    "pcengine": [("Carte système CD (jeux CD)", OPTIONAL, ["syscard3.pce"])],
    "fds": [("BIOS Famicom Disk System", REQUIRED, ["disksys.rom"])],
    "atari5200": [("BIOS Atari 5200", REQUIRED, ["5200.rom"])],
    "atari7800": [("BIOS Atari 7800", OPTIONAL, ["7800 BIOS (U).rom", "7800 BIOS (E).rom"])],
    "atarilynx": [("BIOS Lynx", REQUIRED, ["lynxboot.img"])],
    "3do": [("BIOS 3DO", REQUIRED, ["panafz10.bin", "panafz1.bin", "panafz10e-anvil.bin", "goldstar.bin"])],
    "coleco": [("BIOS ColecoVision", REQUIRED, ["colecovision.rom", "coleco.rom"])],
    "intellivision": [("Exec Intellivision", REQUIRED, ["exec.bin"]),
                      ("GROM Intellivision", REQUIRED, ["grom.bin"])],
    "n64dd": [("IPL 64DD", REQUIRED, ["64DD_IPL.bin", "IPL.n64"])],
    "msx": [("BIOS MSX", REQUIRED, ["MSX.ROM"])],
    "msx2": [("BIOS MSX2", REQUIRED, ["MSX2.ROM"]), ("Extension MSX2", REQUIRED, ["MSX2EXT.ROM"])],
    "gba": [("BIOS Game Boy Advance", OPTIONAL, ["gba_bios.bin"])],
    "gb": [("BIOS Game Boy", OPTIONAL, ["gb_bios.bin"])],
    "gbc": [("BIOS Game Boy Color", OPTIONAL, ["gbc_bios.bin"])],
    "nds": [("BIOS Nintendo DS (ARM7)", OPTIONAL, ["bios7.bin"]),
            ("BIOS Nintendo DS (ARM9)", OPTIONAL, ["bios9.bin"]),
            ("Firmware Nintendo DS", OPTIONAL, ["firmware.bin"])],
    "sega32x": [("BIOS 32X", OPTIONAL, ["32X_M_BIOS.BIN", "32X_G_BIOS.BIN"])],
    "pokemini": [("BIOS Pokémon Mini", OPTIONAL, ["bios.min"])],
}


def _available(root):
    """Noms de fichiers présents dans bios/ (minuscules, avec et sans sous-dossier)."""
    found = set()
    base = os.path.join(root, "bios")
    for dirpath, _x, files in os.walk(base):
        rel = os.path.relpath(dirpath, base).replace(os.sep, "/")
        for f in files:
            found.add(f.lower())
            if rel != ".":
                found.add(f"{rel}/{f}".lower())
    return found


def check(root, system_names):
    """[(système, description, niveau, fichier trouvé ou None, noms possibles)]."""
    found = _available(root)
    results = []
    for s in sorted(system_names, key=str.lower):
        for desc, level, names in REQUIREMENTS.get(s.lower(), []):
            here = [n for n in names if n.lower() in found]
            if s.lower() == "neogeo" and not here and os.path.isfile(os.path.join(root, s, "neogeo.zip")):
                here = ["neogeo/neogeo.zip"]  # le BIOS Neo Geo peut aussi être avec les jeux
            results.append((s, desc, level, here[0] if here else None, names))
    return results
