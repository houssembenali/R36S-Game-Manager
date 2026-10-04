"""Noms lisibles, famille d'icône et couleur des systèmes ArkOS.

Familles : cart (cartouche), disc, handheld (portable), arcade, pc, film.
Un dossier absent de la table s'affiche en majuscules avec l'icône cartouche.
"""
import os
import zlib

import theme as T
from i18n import _

SYSTEMS = {
    "3do": ("3DO", "disc"),
    "amiga": ("Amiga", "pc"),
    "arcade": ("Arcade", "arcade"),
    "arduboy": ("Arduboy", "handheld"),
    "astrocde": ("Bally Astrocade", "cart"),
    "atari2600": ("Atari 2600", "cart"),
    "atari5200": ("Atari 5200", "cart"),
    "atari7800": ("Atari 7800", "cart"),
    "atari800": ("Atari 800", "pc"),
    "atarijaguar": ("Atari Jaguar", "cart"),
    "atarilynx": ("Atari Lynx", "handheld"),
    "atarist": ("Atari ST", "pc"),
    "atarixegs": ("Atari XEGS", "pc"),
    "atomiswave": ("Atomiswave", "arcade"),
    "bbcmicro": ("BBC Micro", "pc"),
    "c16": ("Commodore 16", "pc"),
    "c64": ("Commodore 64", "pc"),
    "c128": ("Commodore 128", "pc"),
    "cavestory": ("Cave Story", "pc"),
    "channelf": ("Channel F", "cart"),
    "coco3": ("TRS-80 CoCo 3", "pc"),
    "coleco": ("ColecoVision", "cart"),
    "cps1": ("Capcom CPS-1", "arcade"),
    "cps2": ("Capcom CPS-2", "arcade"),
    "cps3": ("Capcom CPS-3", "arcade"),
    "daphne": ("Daphne", "arcade"),
    "doom": ("Doom", "pc"),
    "dos": ("MS-DOS", "pc"),
    "dreamcast": ("Dreamcast", "disc"),
    "easyrpg": ("EasyRPG", "pc"),
    "enterprise": ("Enterprise", "pc"),
    "famicom": ("Famicom", "cart"),
    "fds": ("Famicom Disk System", "cart"),
    "fbneo": ("FinalBurn Neo", "arcade"),
    "gameandwatch": ("Game & Watch", "handheld"),
    "gamegear": ("Game Gear", "handheld"),
    "gb": ("Game Boy", "handheld"),
    "gba": ("Game Boy Advance", "handheld"),
    "gbc": ("Game Boy Color", "handheld"),
    "genesis": ("Genesis", "cart"),
    "gx4000": ("Amstrad GX4000", "cart"),
    "intellivision": ("Intellivision", "cart"),
    "j2me": ("J2ME", "handheld"),
    "love2d": ("LÖVE", "pc"),
    "lowresnx": ("LowRes NX", "pc"),
    "mame": ("MAME", "arcade"),
    "mame2003": ("MAME 2003", "arcade"),
    "mastersystem": ("Master System", "cart"),
    "megadrive": ("Mega Drive", "cart"),
    "megaduck": ("Mega Duck", "handheld"),
    "movies": ("Vidéos", "film"),
    "msumd": ("MSU-MD", "cart"),
    "msx": ("MSX", "pc"),
    "msx2": ("MSX2", "pc"),
    "mv": ("Mega Vision", "arcade"),
    "n64": ("Nintendo 64", "cart"),
    "n64dd": ("Nintendo 64DD", "disc"),
    "naomi": ("Naomi", "arcade"),
    "nds": ("Nintendo DS", "handheld"),
    "neogeo": ("Neo Geo", "arcade"),
    "neogeocd": ("Neo Geo CD", "disc"),
    "nes": ("NES", "cart"),
    "ngp": ("Neo Geo Pocket", "handheld"),
    "ngpc": ("Neo Geo Pocket Color", "handheld"),
    "odyssey2": ("Odyssey²", "cart"),
    "openbor": ("OpenBOR", "pc"),
    "pcengine": ("PC Engine", "cart"),
    "pcenginecd": ("PC Engine CD", "disc"),
    "pcfx": ("PC-FX", "disc"),
    "pico-8": ("PICO-8", "pc"),
    "pokemini": ("Pokémon Mini", "handheld"),
    "ports": ("Ports", "pc"),
    "psp": ("PSP", "handheld"),
    "psx": ("PlayStation", "disc"),
    "satellaview": ("Satellaview", "cart"),
    "saturn": ("Saturn", "disc"),
    "scummvm": ("ScummVM", "pc"),
    "sega32x": ("Sega 32X", "cart"),
    "segacd": ("Sega CD", "disc"),
    "sfc": ("Super Famicom", "cart"),
    "sg-1000": ("SG-1000", "cart"),
    "snes": ("Super Nintendo", "cart"),
    "supervision": ("Supervision", "handheld"),
    "tg16": ("TurboGrafx-16", "cart"),
    "tic80": ("TIC-80", "pc"),
    "vectrex": ("Vectrex", "cart"),
    "videopac": ("Videopac", "cart"),
    "virtualboy": ("Virtual Boy", "handheld"),
    "wolf": ("Wolfenstein 3D", "pc"),
    "wonderswan": ("WonderSwan", "handheld"),
    "wonderswancolor": ("WonderSwan Color", "handheld"),
    "x68000": ("X68000", "pc"),
    "zx81": ("ZX81", "pc"),
    "zxspectrum": ("ZX Spectrum", "pc"),
}

# Extensions de ROM acceptées par système (d'après ArkOS). Les archives .zip / .7z sont
# toujours acceptées. Un système absent de la table n'est pas vérifié.
_CD = {".cue", ".chd", ".iso", ".m3u", ".ccd", ".img", ".bin", ".toc", ".mds"}
_ARCADE = {".zip", ".7z"}
EXTENSIONS = {
    "gb": {".gb"}, "gbc": {".gbc", ".gb"}, "gba": {".gba"},
    "nes": {".nes", ".unf", ".unif", ".fds"}, "famicom": {".nes", ".unf", ".unif", ".fds"},
    "fds": {".fds"},
    "snes": {".smc", ".sfc", ".fig", ".swc", ".bs", ".st"},
    "sfc": {".smc", ".sfc", ".fig", ".swc", ".bs", ".st"},
    "n64": {".n64", ".v64", ".z64"}, "nds": {".nds"},
    "gamegear": {".gg"}, "mastersystem": {".sms"}, "sega32x": {".32x"},
    "megadrive": {".md", ".gen", ".smd", ".bin", ".sg"}, "genesis": {".md", ".gen", ".smd", ".bin", ".sg"},
    "segacd": _CD, "saturn": _CD, "pcenginecd": _CD | {".pce"},
    "psx": _CD | {".pbp", ".ecm", ".exe"},
    "dreamcast": {".cdi", ".gdi", ".chd", ".m3u", ".cue"},
    "psp": {".iso", ".cso", ".pbp", ".chd"},
    "pcengine": {".pce", ".cue", ".chd", ".ccd", ".sgx"},
    "ngp": {".ngp"}, "ngpc": {".ngc", ".ngp"},
    "wonderswan": {".ws"}, "wonderswancolor": {".wsc", ".ws"},
    "atarilynx": {".lnx"}, "atari2600": {".a26", ".bin"},
    "neogeo": _ARCADE, "cps1": _ARCADE, "cps2": _ARCADE, "cps3": _ARCADE,
    "mame": _ARCADE, "mame2003": _ARCADE, "fbneo": _ARCADE,
    "ports": {".sh"},
}
_GENERIC = {".zip", ".7z", ".bin", ".cue", ".chd", ".iso", ".m3u", ".img", ".ccd", ".toc", ".mds"}


def valid_extension(system, path):
    """True si l'extension convient au système (ou si le système n'est pas vérifié)."""
    allowed = EXTENSIONS.get(system.lower())
    ext = os.path.splitext(path)[1].lower()
    return allowed is None or ext in allowed or ext in {".zip", ".7z"}


def systems_for_extension(path):
    """Systèmes qui acceptent cette extension (vide si elle est trop générique, ex. .zip),
    dans l'ordre de la table : le dossier ArkOS standard d'abord (nes avant famicom…)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in _GENERIC:
        return []
    return [s for s, exts in EXTENSIONS.items() if ext in exts]


PALETTE = (T.CYAN, T.MAGENTA, T.YELLOW, T.GREEN, T.ORANGE, "#a77bff", "#3e8bff", T.RED)


def name(key):
    return _(SYSTEMS.get(key.lower(), (key.upper(), "cart"))[0])  # seul « Vidéos » se traduit


def kind(key):
    return SYSTEMS.get(key.lower(), (key, "cart"))[1]


def color(key):
    """Couleur stable propre à chaque système."""
    return PALETTE[zlib.crc32(key.lower().encode()) % len(PALETTE)]
