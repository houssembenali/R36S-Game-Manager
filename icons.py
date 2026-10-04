"""Icônes pixel-art dessinées en texte (aucun fichier image à maintenir).

Chaque icône est une grille de caractères :
  .  transparent
  X  couleur principale (passée à icon())    o  principale assombrie    h  éclaircie
  k w r g b y c m  couleurs fixes (voir FIXED)
Pour ajouter une icône, il suffit d'ajouter une entrée dans ART.
"""
from PIL import Image, ImageTk

FIXED = {"k": "#0d0b18", "w": "#ece9ff", "r": "#ff4d6d", "g": "#8bd450", "b": "#3e8bff",
         "y": "#ffd93e", "c": "#3ef0ff", "m": "#ff3ea5",
         # couleurs « vraies » des drapeaux
         "n": "#2a3f9d", "W": "#f4f4f4", "R": "#e0313a", "Y": "#ffcc00", "G": "#1a9a4a", "K": "#222222",
         "s": "#3a8de0"}

ART = {
    "gamepad": [
        "..XXXXXXXXXXXX..",
        ".XXXXXXXXXXXXXX.",
        "XXXwXXXXXXXXyXXX",
        "XXwwwXXXXXXbXrXX",
        "XXXwXXXXXXXXgXXX",
        "XXXXXXXXXXXXXXXX",
        "XXXXXX....XXXXXX",
        ".XXXX......XXXX.",
        "..XX........XX..",
    ],
    "search": [
        "..XXXX......",
        ".X....X.....",
        "X..h...X....",
        "X.h....X....",
        "X......X....",
        "X......X....",
        ".X....X.....",
        "..XXXX.X....",
        ".......XX...",
        "........XX..",
        ".........XX.",
        "..........XX",
    ],
    "close": [
        "XX......XX",
        ".XX....XX.",
        "..XX..XX..",
        "...XXXX...",
        "....XX....",
        "...XXXX...",
        "..XX..XX..",
        ".XX....XX.",
        "XX......XX",
    ],
    "trash": [
        "....XXXX....",
        "XXXXXXXXXXXX",
        "............",
        ".XXXXXXXXXX.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        ".X..X..X..X.",
        "..XXXXXXXX..",
    ],
    "folder": [
        ".XXXX.......",
        "XhhhhXXXXXXX",
        "XooooooooooX",
        "XXXXXXXXXXXX",
        "XhhhhhhhhhhX",
        "XhhhhhhhhhhX",
        "XhhhhhhhhhhX",
        "XhhhhhhhhhhX",
        "XhhhhhhhhhhX",
        "XXXXXXXXXXXX",
    ],
    "refresh": [
        "....XXXX....",
        "..XX....XX.X",
        ".X........XX",
        ".X.......XXX",
        "X...........",
        "X...........",
        "...........X",
        "...........X",
        "XXX.......X.",
        "XX........X.",
        "X.XX....XX..",
        "....XXXX....",
    ],
    "grid": [
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "............",
        "............",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
    ],
    "list": [
        "XX.XXXXXXXXX",
        "XX.XXXXXXXXX",
        "............",
        "............",
        "XX.XXXXXXXXX",
        "XX.XXXXXXXXX",
        "............",
        "............",
        "XX.XXXXXXXXX",
        "XX.XXXXXXXXX",
    ],
    "star": [
        ".....XX.....",
        ".....XX.....",
        "....XXXX....",
        "XXXXXhhXXXXX",
        ".XXXXhhXXXX.",
        "..XXXXXXXX..",
        "...XXXXXX...",
        "..XXXXXXXX..",
        "..XXX..XXX..",
        ".XXX....XXX.",
        ".XX......XX.",
    ],
    "star_outline": [
        ".....XX.....",
        ".....XX.....",
        "....X..X....",
        "XXXXX..XXXXX",
        ".X........X.",
        "..X......X..",
        "...X....X...",
        "..X......X..",
        "..X..XX..X..",
        ".X..X..X..X.",
        ".XXX....XXX.",
    ],
    "sound_on": [
        "....X.......",
        "...XX....X..",
        "..XXX..X..X.",
        "XXXXX...X..X",
        "XXXXX.X.X..X",
        "XXXXX.X.X..X",
        "XXXXX...X..X",
        "..XXX..X..X.",
        "...XX....X..",
        "....X.......",
    ],
    "sound_off": [
        "....X.......",
        "...XX.......",
        "..XXX.r...r.",
        "XXXXX..r.r..",
        "XXXXX...r...",
        "XXXXX..r.r..",
        "XXXXX.r...r.",
        "..XXX.......",
        "...XX.......",
        "....X.......",
    ],
    "filter": [
        "XXXXXXXXXXXX",
        ".XXXXXXXXXX.",
        "..XXXXXXXX..",
        "...XXXXXX...",
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        "....XXX.....",
        "....XX......",
    ],
    "undo": [
        "...X........",
        "..XX........",
        ".XXXXXXXX...",
        "XXXXXXXXXX..",
        ".XXXXXXXXXX.",
        "..XX.....XX.",
        "...X......XX",
        "..........XX",
        "..........XX",
        ".........XX.",
        "....XXXXXX..",
        "....XXXXX...",
    ],
    "plus": [
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
    ],
    "edit": [
        ".........XX.",
        "........XXXX",
        ".......XhXX.",
        "......XhXX..",
        ".....XhXX...",
        "....XhXX....",
        "...XhXX.....",
        "..XhXX......",
        ".XXXX.......",
        ".yXX........",
        "yy..........",
    ],
    "menu": [
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "............",
        "............",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "............",
        "............",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
    ],
    "chip": [
        "..X..X..X...",
        "..X..X..X...",
        ".XXXXXXXXXX.",
        "XXkkkkkkkkXX",
        ".XkcckkkkkX.",
        "XXkcckkkkkXX",
        ".XkkkkkkkkX.",
        "XXkkkkkkkkXX",
        ".XXXXXXXXXX.",
        "..X..X..X...",
        "..X..X..X...",
    ],
    "copy": [
        "XXXXXXX.....",
        "X.....X.....",
        "X..XXXXXXX..",
        "X..X.....X..",
        "X..X.....X..",
        "XXXX.....X..",
        "...X.....X..",
        "...X.....X..",
        "...XXXXXXX..",
    ],
    "compress": [
        "X..........X",
        ".X........X.",
        "..X......X..",
        "...XX..XX...",
        "...XX..XX...",
        "............",
        "............",
        "...XX..XX...",
        "...XX..XX...",
        "..X......X..",
        ".X........X.",
        "X..........X",
    ],
    "move": [
        "......X.....",
        "......XX....",
        "XXXXXXXXX...",
        "XXXXXXXXXX..",
        "XXXXXXXXX...",
        "......XX....",
        "......X.....",
    ],
    "broom": [
        "..........XX",
        ".........XX.",
        "........XX..",
        ".......XX...",
        "......XX....",
        "....yXy.....",
        "...yyyyy....",
        "..yyyyyy....",
        ".yyyyyyy....",
        "yy.y.y.y....",
        "y.y.y.y.....",
    ],
    "download": [
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        "....XXXX....",
        ".XXXXXXXXXX.",
        "..XXXXXXXX..",
        "...XXXXXX...",
        "....XXXX....",
        ".....XX.....",
        "X..........X",
        "X..........X",
        "XXXXXXXXXXXX",
    ],
    "sd": [
        "XXXXXXXX....",
        "XyXyXyXXX...",
        "XyXyXyXXXX..",
        "XXXXXXXXXXX.",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "XXwwwwwwwwXX",
        "XXwwwwwwwwXX",
        "XXwwwwwwwwXX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
    ],
    "save": [
        "XXXXXXXXXX..",
        "XXwwwwwwXXX.",
        "XXwwwwkwXXXX",
        "XXwwwwkwXXXX",
        "XXwwwwwwXXXX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        "XXwwwwwwwwXX",
        "XXwkkkkkkwXX",
        "XXwwwwwwwwXX",
        "XXwkkkkkwwXX",
        "XXXXXXXXXXXX",
    ],
    "warning": [
        ".....XX.....",
        "....XXXX....",
        "....XXXX....",
        "...XXkkXX...",
        "...XXkkXX...",
        "..XXXkkXXX..",
        "..XXXkkXXX..",
        ".XXXXkkXXXX.",
        ".XXXXXXXXXX.",
        "XXXXXkkXXXXX",
        "XXXXXXXXXXXX",
    ],
    "check_off": [
        "XXXXXXXXXX",
        "X........X",
        "X........X",
        "X........X",
        "X........X",
        "X........X",
        "X........X",
        "X........X",
        "X........X",
        "XXXXXXXXXX",
    ],
    "check_on": [
        "XXXXXXXXXX",
        "X........X",
        "X......g.X",
        "X.....gg.X",
        "Xg...gg..X",
        "Xgg.gg...X",
        "X.ggg....X",
        "X..g.....X",
        "X........X",
        "XXXXXXXXXX",
    ],
    # --- familles de systèmes (voir systems.py)
    "cart": [
        "XXXXXXXXXXXX",
        "XooooooooooX",
        "XowwwwwwwwoX",
        "XowmmmmmmwoX",
        "XowwwwwwwwoX",
        "XooooooooooX",
        "XXXXXXXXXXXX",
        "XXXXXXXXXXXX",
        ".XXXXXXXXXX.",
        ".XkXkXkXkXX.",
    ],
    "disc": [
        "....XXXX....",
        "..XXhhXXXX..",
        ".XhhXXXXXXX.",
        ".XhXXXXXXXX.",
        "XXXXXXXXXXXX",
        "XXXXX..XXXXX",
        "XXXXX..XXXXX",
        "XXXXXXXXXXXX",
        ".XXXXXXXXoX.",
        ".XXXXXXXooX.",
        "..XXXXooXX..",
        "....XXXX....",
    ],
    "handheld": [
        "..XXXXXXXX..",
        "..XkkkkkkX..",
        "..XkggggkX..",
        "..XkggggkX..",
        "..XkggggkX..",
        "..XkkkkkkX..",
        "..XXXXXXXX..",
        "..XwXXXXrX..",
        "..wwwXXrXX..",
        "..XwXXXXXX..",
        "..XXXXooXX..",
        "...XXXXXX...",
    ],
    "arcade": [
        "....rrr.....",
        "...rrrrr....",
        "...rrrrr....",
        "....rrr.....",
        ".....X......",
        ".....X......",
        ".....X......",
        ".XXXXXXXXXX.",
        "XXXXXXXXXXXX",
        "XXyXXXXXbXrX",
        "XooooooooooX",
        "XXXXXXXXXXXX",
    ],
    "pc": [
        "XXXXXXXXXXXX",
        "XkkkkkkkkkkX",
        "XkcccckkkkkX",
        "XkkkkkkkkkkX",
        "XkcckkkkkkkX",
        "XkkkkkkkkkkX",
        "XkkkkkkkkkkX",
        "XXXXXXXXXXXX",
        "....XXXX....",
        "....XXXX....",
        "..XXXXXXXX..",
    ],
    "film": [
        "XXXXXXXXXXXX",
        "X.XX.XX.XX.X",
        "XXXXXXXXXXXX",
        "XccccccccccX",
        "XccccccccccX",
        "XccccccccccX",
        "XccccccccccX",
        "XXXXXXXXXXXX",
        "X.XX.XX.XX.X",
        "XXXXXXXXXXXX",
    ],
}


# Drapeaux 15×10 (codes de regions.py)
_STRIPES = lambda a, b, c: [a * 5 + b * 5 + c * 5] * 10  # noqa: E731 - bandes verticales
FLAGS = {
    "fr": _STRIPES("n", "W", "R"),
    "it": _STRIPES("G", "W", "R"),
    "de": ["K" * 15] * 3 + ["R" * 15] * 4 + ["Y" * 15] * 3,
    "es": ["R" * 15] * 2 + ["Y" * 15] * 6 + ["R" * 15] * 2,
    "nl": ["R" * 15] * 3 + ["W" * 15] * 4 + ["n" * 15] * 3,
    "us": ["nWnWnWnRRRRRRRR", "nnnnnnnWWWWWWWW", "nWnWnWnRRRRRRRR", "nnnnnnnWWWWWWWW",
           "nWnWnWnRRRRRRRR", "W" * 15, "R" * 15, "W" * 15, "R" * 15, "W" * 15],
    "eu": ["n" * 15, "nnnnnnnYnnnnnnn", "nnnnnYnnnYnnnnn", "n" * 15, "nnnnYnnnnnYnnnn",
           "n" * 15, "nnnnnYnnnYnnnnn", "nnnnnnnYnnnnnnn", "n" * 15, "n" * 15],
    "jp": ["W" * 15, "W" * 15, "WWWWWWRRRWWWWWW", "WWWWWRRRRRWWWWW", "WWWWWRRRRRWWWWW",
           "WWWWWRRRRRWWWWW", "WWWWWWRRRWWWWWW", "W" * 15, "W" * 15, "W" * 15],
    "kr": ["W" * 15, "W" * 15, "WWWWWWRRRWWWWWW", "WWWWWRRRRRWWWWW", "WWWWWRRRRRWWWWW",
           "WWWWWnnnnnWWWWW", "WWWWWWnnnWWWWWW", "W" * 15, "W" * 15, "W" * 15],
    "gb": ["nnnnnnWRWnnnnnn"] * 3 + ["WWWWWWWRWWWWWWW", "R" * 15, "R" * 15, "WWWWWWWRWWWWWWW"]
          + ["nnnnnnWRWnnnnnn"] * 3,
    "se": ["nnnnYYnnnnnnnnn"] * 4 + ["Y" * 15] * 2 + ["nnnnYYnnnnnnnnn"] * 4,
    "ca": ["RRRRWWWWWWWRRRR"] * 2 + ["RRRRWWWRWWWRRRR", "RRRRWWRRRWWRRRR", "RRRRWRRRRRWRRRR",
                                      "RRRRWWWRWWWRRRR"] + ["RRRRWWWWWWWRRRR"] * 4,
    "cn": ["R" * 15, "RRYRRRRRRRRRRRR", "RYYYRRYRRRRRRRR", "RRYRRRRRRRRRRRR", "RYRYRRYRRRRRRRR"]
          + ["R" * 15] * 5,
    "tw": ["nnnnnnRRRRRRRRR", "nnWnnnRRRRRRRRR", "nWWWnnRRRRRRRRR", "nnWnnnRRRRRRRRR",
           "nnnnnnRRRRRRRRR"] + ["R" * 15] * 5,
    "br": ["G" * 15, "GGGGGGYYYGGGGGG", "GGGGYYYYYYYGGGG", "GGYYYYnnnYYYYGG", "GYYYYnnnnnYYYYG",
           "GYYYYnnnnnYYYYG", "GGYYYYnnnYYYYGG", "GGGGYYYYYYYGGGG", "GGGGGGYYYGGGGGG", "G" * 15],
    "au": ["WWRWWnnnnnnnnnn", "RRRRRnnnnnnWnnn", "WWRWWnnnnnnnnnn", "nnnnnnnnnWnnnWn", "n" * 15,
           "nnWnnnnnnnnWnnn", "n" * 15, "nnnnnnnnnnnWnnn", "n" * 15, "n" * 15],
    "world": [".....sssss.....", "...ssGGssssss..", "..ssGGGssGGsss.", ".sssGGsssGGGsss",
              ".ssssGssssGGGss", ".sssssssssGGsss", ".sssGGssssGssss", "..ssGGGGsssss..",
              "...ssGGssssss..", ".....sssss....."],
}
FLAGS["asia"] = FLAGS["world"]
ART.update({"flag_" + k: v for k, v in FLAGS.items()})


def flags(codes, scale=2):
    """Drapeaux côte à côte (codes inconnus ignorés), ou None s'il n'y en a aucun."""
    codes = [c for c in codes if c in FLAGS]
    if not codes:
        return None
    key = ("flags", tuple(codes), scale)
    if key not in _cache:
        imgs = []
        for c in codes:
            rows = ART["flag_" + c]
            w, h = len(rows[0]), len(rows)
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            for y, row in enumerate(rows):
                for x, ch in enumerate(row):
                    if ch in FIXED:
                        img.putpixel((x, y), _rgb(FIXED[ch]) + (255,))
            imgs.append(img.resize((w * scale, h * scale), Image.NEAREST))
        gap = 3 * scale
        strip = Image.new("RGBA", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), imgs[0].height))
        x = 0
        for i in imgs:
            strip.paste(i, (x, 0))
            x += i.width + gap
        _cache[key] = ImageTk.PhotoImage(strip)
    return _cache[key]


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(rgb, target, f):
    return tuple(round(a + (b - a) * f) for a, b in zip(rgb, target))


def pil_icon(name, color, scale=2):
    """Image PIL carrée (RGBA) de l'icône, agrandie sans flou."""
    rows = ART[name]
    main = _rgb(color)
    colors = {"X": main, "o": _mix(main, (0, 0, 0), 0.45), "h": _mix(main, (255, 255, 255), 0.45)}
    colors.update({k: _rgb(v) for k, v in FIXED.items()})
    w = max(len(r) for r in rows)
    side = max(w, len(rows))
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ox, oy = (side - w) // 2, (side - len(rows)) // 2
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in colors:
                img.putpixel((ox + x, oy + y), colors[ch] + (255,))
    return img.resize((side * scale, side * scale), Image.NEAREST)


_cache = {}


def stars(rating, scale=1, on="#ffd93e", off="#3a3260"):
    """Rangée de 5 étoiles pour une note 0..1, arrondie à la demi-étoile (comme la console)."""
    halves = round((rating or 0) * 10)
    key = ("stars", halves, scale, on, off)
    if key not in _cache:
        full, empty = pil_icon("star", on, scale), pil_icon("star", off, scale)
        w, gap = full.width, scale * 2
        row = Image.new("RGBA", (5 * w + 4 * gap, full.height), (0, 0, 0, 0))
        for i in range(5):
            x = i * (w + gap)
            row.paste(empty, (x, 0), empty)
            filled = min(max(halves - 2 * i, 0), 2)  # 0 vide, 1 moitié, 2 pleine
            if filled:
                part = full.crop((0, 0, w * filled // 2, full.height))
                row.paste(part, (x, 0), part)
        _cache[key] = ImageTk.PhotoImage(row)
    return _cache[key]


def boxed(name, color, scale, w, h):
    """Icône centrée dans une case w×h (pour s'aligner avec les logos de console)."""
    key = (name, color, scale, w, h)
    if key not in _cache:
        box = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        im = pil_icon(name, color, scale)
        box.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
        _cache[key] = ImageTk.PhotoImage(box)
    return _cache[key]


def icon(name, color, scale=2):
    """PhotoImage Tk de l'icône (mise en cache)."""
    key = (name, color, scale)
    if key not in _cache:
        _cache[key] = ImageTk.PhotoImage(pil_icon(name, color, scale))
    return _cache[key]
