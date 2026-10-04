"""Touches d'un port PortMaster : fichiers .gptk de gptokeyb (bouton de la console = touche du clavier).

    a = z            # le bouton A envoie la touche Z
    start = enter
    left_analog_up = up
Les commentaires et l'ordre des lignes sont gardés quand on modifie une touche.
"""
import os
import re

import core
import journal

# boutons de la R36S, dans l'ordre d'affichage
BUTTONS = ("a", "b", "x", "y", "l1", "l2", "r1", "r2", "start", "back", "guide", "up", "down", "left", "right",
           "left_analog_up", "left_analog_down", "left_analog_left", "left_analog_right",
           "right_analog_up", "right_analog_down", "right_analog_left", "right_analog_right", "l3", "r3")
# noms affichés des boutons
LABELS = {"a": "A", "b": "B", "x": "X", "y": "Y", "l1": "L1", "l2": "L2", "r1": "R1", "r2": "R2",
          "start": "START", "back": "SELECT", "guide": "FN", "up": "↑", "down": "↓", "left": "←", "right": "→",
          "left_analog_up": "STICK G ↑", "left_analog_down": "STICK G ↓", "left_analog_left": "STICK G ←",
          "left_analog_right": "STICK G →", "right_analog_up": "STICK D ↑", "right_analog_down": "STICK D ↓",
          "right_analog_left": "STICK D ←", "right_analog_right": "STICK D →", "l3": "L3", "r3": "R3"}
# touches proposées (on peut aussi en écrire une autre)
KEYS = (["", "esc", "enter", "space", "tab", "backspace", "up", "down", "left", "right", "shift", "leftshift",
         "ctrl", "leftctrl", "alt", "leftalt", "home", "end", "pageup", "pagedown", "insert", "delete",
         "mouse_left", "mouse_right", "mouse_middle", "mouse_movement_up", "mouse_movement_down",
         "mouse_movement_left", "mouse_movement_right", "add_alt", "add_ctrl", "add_shift"]
        + [chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(d) for d in range(10)]
        + [f"f{n}" for n in range(1, 13)])
LINE = re.compile(r"^(\s*)([a-z0-9_]+)(\s*=\s*)(.*?)(\s*(?:#.*)?)$", re.I)


def files(game):
    """Fichiers .gptk du port (dans ses dossiers, premier niveau)."""
    out = []
    for d in core.port_dirs(game.path):
        try:
            out += sorted(e.path for e in os.scandir(d) if e.is_file() and e.name.lower().endswith(".gptk"))
        except OSError:
            pass
    return out


def read(path):
    """{bouton: touche} d'un fichier .gptk."""
    out = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = LINE.match(line.rstrip("\n"))
                if m and not line.lstrip().startswith("#"):
                    out[m.group(2).lower()] = m.group(4).strip()
    except OSError:
        pass
    return out


def ordered(mapping):
    """[(bouton, touche)] dans l'ordre de la console, puis les autres réglages du fichier."""
    known = [(b, mapping[b]) for b in BUTTONS if b in mapping]
    return known + [(k, v) for k, v in mapping.items() if k not in BUTTONS]


def write(path, changes):
    """Change des touches {bouton: touche} en gardant le reste du fichier (annulable)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    done = set()
    for i, line in enumerate(lines):
        m = LINE.match(line)
        if m and not line.lstrip().startswith("#") and m.group(2).lower() in changes:
            key = m.group(2).lower()
            lines[i] = f"{m.group(1)}{m.group(2)}{m.group(3)}{changes[key]}{m.group(5)}"
            done.add(key)
    new = [f"{k} = {v}" for k, v in changes.items() if k not in done]
    if new:
        ending = []
        while lines and not lines[-1].strip():  # les nouvelles touches avant les lignes vides de la fin
            ending.append(lines.pop())
        lines += new + ending

    def save(p):
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
    journal.write_file(path, save)
