"""Téléchargement des images manquantes depuis libretro-thumbnails.

Base d'images utilisée par RetroArch : gratuite, sans compte. Les images sont rangées par
système et nommées comme les ROMs No-Intro, ex. :
  https://thumbnails.libretro.com/Nintendo - Game Boy Advance/Named_Boxarts/<nom>.png
Pour ajouter un système : ajouter son dossier ArkOS et son nom libretro dans LIBRETRO.
"""
import difflib
import html
import io
import os
import re
import urllib.error
import urllib.parse

import net

from PIL import Image

import core
import journal

BASE ="https://thumbnails.libretro.com"
MAX_SIZE = (480, 480)  # taille max des images enregistrées sur la carte

LIBRETRO = {
    "3do": "The 3DO Company - 3DO",
    "amiga": "Commodore - Amiga",
    "atari2600": "Atari - 2600",
    "atari5200": "Atari - 5200",
    "atari7800": "Atari - 7800",
    "atarijaguar": "Atari - Jaguar",
    "atarilynx": "Atari - Lynx",
    "atarist": "Atari - ST",
    "c64": "Commodore - 64",
    "coleco": "Coleco - ColecoVision",
    "cps1": "MAME", "cps2": "MAME", "cps3": "MAME", "mame": "MAME", "mame2003": "MAME",
    "fbneo": "FBNeo - Arcade Games", "arcade": "MAME",
    "dos": "DOS",
    "dreamcast": "Sega - Dreamcast",
    "famicom": "Nintendo - Nintendo Entertainment System",
    "fds": "Nintendo - Family Computer Disk System",
    "gameandwatch": "Handheld Electronic Game",
    "gamegear": "Sega - Game Gear",
    "gb": "Nintendo - Game Boy",
    "gba": "Nintendo - Game Boy Advance",
    "gbc": "Nintendo - Game Boy Color",
    "genesis": "Sega - Mega Drive - Genesis",
    "intellivision": "Mattel - Intellivision",
    "mastersystem": "Sega - Master System - Mark III",
    "megadrive": "Sega - Mega Drive - Genesis",
    "msx": "Microsoft - MSX",
    "msx2": "Microsoft - MSX2",
    "n64": "Nintendo - Nintendo 64",
    "nds": "Nintendo - Nintendo DS",
    "neogeo": "SNK - Neo Geo",
    "neogeocd": "SNK - Neo Geo CD",
    "nes": "Nintendo - Nintendo Entertainment System",
    "ngp": "SNK - Neo Geo Pocket",
    "ngpc": "SNK - Neo Geo Pocket Color",
    "pcengine": "NEC - PC Engine - TurboGrafx 16",
    "pcenginecd": "NEC - PC Engine CD - TurboGrafx-CD",
    "pcfx": "NEC - PC-FX",
    "pokemini": "Nintendo - Pokemon Mini",
    "psp": "Sony - PlayStation Portable",
    "psx": "Sony - PlayStation",
    "saturn": "Sega - Saturn",
    "scummvm": "ScummVM",
    "sega32x": "Sega - 32X",
    "segacd": "Sega - Mega-CD - Sega CD",
    "sfc": "Nintendo - Super Nintendo Entertainment System",
    "sg-1000": "Sega - SG-1000",
    "snes": "Nintendo - Super Nintendo Entertainment System",
    "tg16": "NEC - PC Engine - TurboGrafx 16",
    "vectrex": "GCE - Vectrex",
    "virtualboy": "Nintendo - Virtual Boy",
    "wonderswan": "Bandai - WonderSwan",
    "wonderswancolor": "Bandai - WonderSwan Color",
    "zxspectrum": "Sinclair - ZX Spectrum",
}

# dossier libretro -> (balise gamelist, dossier de destination)
KINDS = (("Named_Boxarts", "thumbnail", "media/boxes"),
         ("Named_Snaps", "image", "media/images"))

_index = {}  # (système libretro, dossier) -> [noms sans .png]


def supported(system):
    return system.lower() in LIBRETRO


def missing_images(games):
    """Jeux sans aucune image, pour lesquels libretro a un dossier."""
    return [g for g in games if supported(g.system) and not core.cover_for(g)]


def _get(url):
    return net.get(url)


def _url(*parts):
    return BASE + "/" + "/".join(urllib.parse.quote(p) for p in parts)


def _listing(system_name, kind):
    key = (system_name, kind)
    if key not in _index:
        try:
            text = _get(_url(system_name, kind) + "/").decode("utf-8", "replace")
        except (urllib.error.URLError, OSError):
            text = ""
        _index[key] = [html.unescape(urllib.parse.unquote(h))[:-4]
                       for h in re.findall(r'href="([^"/?][^"]*\.png)"', text)]
    return _index[key]


def _clean(name):
    """Libretro remplace ces caractères par _ dans les noms de fichiers."""
    return re.sub(r'[&*/:`<>?\\|"]', "_", name)


_key = core.title_key


def _tags(name):
    return {t.strip().lower() for tag in re.findall(r"\((.*?)\)", name) for t in tag.split(",")}


def best_match(game, names):
    """Nom libretro le plus proche du jeu, ou None."""
    candidates = [game.stem, game.name]
    exact = {n.lower(): n for n in names}
    for c in candidates:
        if _clean(c).lower() in exact:
            return exact[_clean(c).lower()]
    by_key = {}
    for n in names:
        by_key.setdefault(_key(n), []).append(n)
    tags = _tags(game.stem)
    for c in candidates:
        k = _key(c)
        if not k:
            continue
        if k not in by_key:
            close = difflib.get_close_matches(k, list(by_key), n=1, cutoff=0.88)
            if not close:
                continue
            k = close[0]
        # même région / langues de préférence, sinon USA ou Europe
        return max(by_key[k], key=lambda n: (len(_tags(n) & tags),
                                             bool(_tags(n) & {"usa", "europe", "world"}), -len(n)))
    return None


def fetch_bytes(game, tag):
    """Télécharge une seule image du jeu (tag « image » = capture, « thumbnail » = jaquette),
    sans l'enregistrer. Retourne les octets ou None."""
    system_name = LIBRETRO.get(game.system.lower())
    if not system_name:
        return None
    for kind, t, _x in KINDS:
        if t == tag:
            match = best_match(game, _listing(system_name, kind))
            if match:
                try:
                    return _get(_url(system_name, kind, match + ".png"))
                except (urllib.error.URLError, OSError):
                    return None
    return None


# balise -> (balises du gamelist à mettre à jour, dossier de destination)
SLOTS = {"image": (("image",), "media/images"),
         "thumbnail": (("thumbnail", "box"), "media/boxes")}


def set_image(root, game, tag, data, system_games):
    """Remplace (data = octets d'une image) ou retire (data = None) une image du jeu.
    L'image est réduite, enregistrée dans media/ et inscrite en chemin relatif dans le
    gamelist.xml, comme le fait Skraper : c'est ce que la console lit. Retourne les erreurs."""
    tags, folder = SLOTS[tag]
    tags = [t for t in tags if t == tag or t in game.media]  # <box> seulement s'il existait déjà
    old = {game.media[t] for t in tags if t in game.media}
    new = save_image(data, os.path.join(game.sysdir, os.path.normpath(folder), game.stem)) if data else None

    def apply(el, g):
        for t in tags:
            core._set_tag(el, t, "./" + core._rel(new, g.sysdir) if new else None)
            if new:
                g.media[t] = new
            else:
                g.media.pop(t, None)
    errors = core.update_gamelist(root, [game], apply)
    # anciennes images devenues inutiles (si aucun autre jeu ne s'en sert)
    used = {core._key_of(p) for g in system_games if not core.same(g.path, game.path) for p in g.media.values()}
    used |= {core._key_of(p) for t, p in game.media.items() if t not in tags}  # autres images du jeu
    for p in old:
        if new and core.same(p, new):
            continue
        if core._key_of(p) not in used and os.path.isfile(p):
            try:
                journal.remove(p)
            except OSError as e:
                errors.append(f"{p} : {e}")
    core.clear_cache()
    return errors


def save_image(data, base):
    """Réduit l'image (l'écran de la R36S fait 640×480) et l'enregistre : JPEG si opaque
    (bien plus léger), PNG si elle a de la transparence. Retourne le chemin."""
    os.makedirs(os.path.dirname(base), exist_ok=True)
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGBA")
        im.thumbnail(MAX_SIZE, Image.LANCZOS)
        if im.getchannel("A").getextrema()[0] < 255:
            dest, out, options = base + ".png", im.quantize(256, method=Image.Quantize.FASTOCTREE), {}
        else:
            dest, out, options = base + ".jpg", im.convert("RGB"), {"quality": 88}
        journal.write_file(dest, lambda p: out.save(p, optimize=True, **options))
    return dest


def fetch_images(game):
    """Télécharge jaquette et capture du jeu. Retourne {balise: chemin enregistré}."""
    system_name = LIBRETRO[game.system.lower()]
    saved = {}
    for kind, tag, folder in KINDS:
        match = best_match(game, _listing(system_name, kind))
        if not match:
            continue
        try:
            data = _get(_url(system_name, kind, match + ".png"))
        except (urllib.error.URLError, OSError):
            continue
        try:
            dest = save_image(data, os.path.join(game.sysdir, os.path.normpath(folder), game.stem))
        except OSError:
            continue
        saved[tag] = dest
    if "image" not in saved and "thumbnail" in saved:
        saved["image"] = saved["thumbnail"]  # la console affiche <image> en priorité
    return saved
