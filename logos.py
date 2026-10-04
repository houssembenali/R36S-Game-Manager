"""Logos officiels des consoles.

Ils sont copiés une fois depuis les thèmes EmulationStation de la carte (dossier themes/)
vers assets/logos/<système>.png, puis utilisés de là. Pour remplacer un logo, il suffit de
mettre son propre PNG dans assets/logos/ avec le nom du dossier système (ex. psx.png).
Sans logo, on affiche l'icône pixel de la famille (voir icons.py / systems.py).
"""
import os

from PIL import Image, ImageFilter, ImageTk

import icons
import paths
import systems

LOGO_DIR = paths.data("assets", "logos")  # importés depuis la carte (écrits par le programme)

# Où chercher dans <carte>/themes, dans l'ordre ({s} = dossier du système)
THEME_SOURCES = (
    "R36S-theme-nes-box/{s}/system.png",
    "es-theme-nes-box/{s}/system.png",
    "R36S-simplecomicbook/{s}/art/system.png",
)

_pil = {}   # système -> Image PIL préparée (ou None)
_tk = {}    # (système, w, h, align, fallback) -> PhotoImage


def import_from_card(root, system_names):
    """Copie dans assets/logos les logos absents, trouvés dans les thèmes de la carte."""
    os.makedirs(LOGO_DIR, exist_ok=True)
    for s in system_names:
        dest = os.path.join(LOGO_DIR, s.lower() + ".png")
        if os.path.exists(dest):
            continue
        for pattern in THEME_SOURCES:
            src = os.path.join(root, "themes", pattern.format(s=s))
            if not os.path.isfile(src):
                continue
            try:
                with Image.open(src) as im:
                    im = im.convert("RGBA")
                    if im.getbbox():
                        im = im.crop(im.getbbox())
                    im.thumbnail((600, 200), Image.LANCZOS)
                    im.save(dest)
                break
            except OSError:
                continue


def reset():
    _pil.clear()
    _tk.clear()


def _prepare(im):
    """Ajoute un halo clair autour des logos trop sombres pour le fond du thème."""
    opaque = [p for p in im.getdata() if p[3] > 128]
    if not opaque:
        return im
    lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b, _x in opaque) / len(opaque)
    if lum >= 85:
        return im
    halo_alpha = im.getchannel("A").filter(ImageFilter.MaxFilter(9)).point(lambda a: a * 0.75)
    halo = Image.new("RGBA", im.size, (236, 233, 255, 0))
    halo.putalpha(halo_alpha)
    return Image.alpha_composite(halo, im)


def _logo(system):
    s = system.lower()
    if s not in _pil:
        path = os.path.join(LOGO_DIR, s + ".png")
        im = None
        if os.path.isfile(path):
            try:
                with Image.open(path) as f:
                    im = _prepare(f.convert("RGBA"))
            except OSError:
                im = None
        _pil[s] = im
    return _pil[s]


def has(system):
    return _logo(system) is not None


def get(system, w, h, align="left", fallback=True):
    """PhotoImage de exactement w×h avec le logo (ou l'icône pixel si fallback)."""
    key = (system.lower(), w, h, align, fallback)
    if key in _tk:
        return _tk[key]
    im = _logo(system)
    if im is not None:
        im = im.copy()
        im.thumbnail((w, h), Image.LANCZOS)
    elif fallback:
        im = icons.pil_icon(systems.kind(system), systems.color(system), max(1, h // 12))
    else:
        _tk[key] = None
        return None
    box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x = 0 if align == "left" else (w - im.width) // 2
    box.paste(im, (x, (h - im.height) // 2), im)
    _tk[key] = ImageTk.PhotoImage(box)
    return _tk[key]
