"""Thème rétro : couleurs, polices pixel et styles ttk."""
import ctypes
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import paths

# Palette « néon arcade »
BG = "#0f0d1a"
PANEL = "#171427"
PANEL2 = "#221d38"
BORDER = "#3a3260"
SELECT = "#33245e"
TEXT = "#ece9ff"
MUTED = "#8b85b5"
CYAN = "#3ef0ff"
MAGENTA = "#ff3ea5"
YELLOW = "#ffd93e"
GREEN = "#5dff8a"
ORANGE = "#ff8a3e"
RED = "#ff4d6d"
DANGER_BG = "#2a1020"

FONT_DIR = paths.asset("fonts")
SCROLL = "Retro.Vertical.TScrollbar"

# Rempli par apply() : nom -> (famille, taille). Tailles négatives = pixels.
F = {}


def load_fonts():
    """Rend les polices de assets/fonts utilisables (à appeler avant de créer la fenêtre).
    Windows : chargées pour ce programme seulement. Linux : copiées dans ~/.local/share/fonts."""
    if not os.path.isdir(FONT_DIR):
        return
    fonts = [f for f in os.listdir(FONT_DIR) if f.lower().endswith(".ttf")]
    if paths.WINDOWS:
        for name in fonts:
            try:
                ctypes.windll.gdi32.AddFontResourceExW(os.path.join(FONT_DIR, name), 0x10, 0)
            except (AttributeError, OSError):
                pass
        return
    target = os.path.expanduser("~/.local/share/fonts/r36s-game-manager")
    missing = [f for f in fonts if not os.path.isfile(os.path.join(target, f))]
    if missing:
        os.makedirs(target, exist_ok=True)
        for name in missing:
            shutil.copy2(os.path.join(FONT_DIR, name), target)
        try:  # fontconfig doit connaître les nouvelles polices avant que Tk démarre
            subprocess.run(["fc-cache", "-f", target], check=False, capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass


def _fonts(root):
    families = set(tkfont.families(root))
    def pick(*names):
        return next((n for n in names if n in families), "Segoe UI")

    pixel = pick("Press Start 2P")                              # logo uniquement
    text = pick("Chakra Petch")
    strong = pick("Chakra Petch SemiBold", "Chakra Petch")
    F.update({
        "logo": (pixel, -24),                                    # nette en multiples de 8 px
        "h1": (strong, 16, "bold"), "h2": (strong, 10, "bold"), "btn": (strong, 10, "bold"),
        "tiny": (strong, 9, "bold"), "big": (text, 14), "body": (text, 12), "small": (text, 11),
        "card": (text, 10),                                     # noms dans la grille
    })


def apply(root):
    _fonts(root)
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL2, bordercolor=BORDER,
                lightcolor=PANEL2, darkcolor=PANEL2, troughcolor=BG, focuscolor=CYAN,
                selectbackground=SELECT, selectforeground=TEXT, insertcolor=CYAN, font=F["body"])

    # Tableaux
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    s.layout("Treeview.Item", [("Treeitem.padding", {"sticky": "nswe", "children": [
        ("Treeitem.image", {"side": "left", "sticky": ""}),
        ("Treeitem.text", {"side": "left", "sticky": ""})]})])
    s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                rowheight=34, borderwidth=0, font=F["body"])
    s.configure("Treeview.Item", padding=(8, 0))
    s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", CYAN)])
    s.configure("Treeview.Heading", background=PANEL2, foreground=CYAN, font=F["tiny"],
                relief="flat", borderwidth=0, padding=(8, 10))
    s.map("Treeview.Heading", background=[("active", BORDER)], foreground=[("active", YELLOW)])
    s.configure("Side.Treeview", background=BG, fieldbackground=BG, rowheight=38)

    # Barres de défilement fines, sans flèches
    s.layout(SCROLL, [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
        ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure(SCROLL, troughcolor=BG, background=BORDER, bordercolor=BG, lightcolor=BORDER,
                darkcolor=BORDER, gripcount=0, width=10)
    s.map(SCROLL, background=[("active", MAGENTA), ("pressed", MAGENTA)])

    # Listes déroulantes
    s.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2, foreground=TEXT,
                arrowcolor=CYAN, bordercolor=BORDER, lightcolor=PANEL2, darkcolor=PANEL2,
                padding=6, arrowsize=16)
    s.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXT)],
          selectbackground=[("readonly", PANEL2)], selectforeground=[("readonly", TEXT)],
          bordercolor=[("focus", CYAN), ("hover", MAGENTA)], arrowcolor=[("hover", MAGENTA)])
    root.option_add("*TCombobox*Listbox.background", PANEL2)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", MAGENTA)
    root.option_add("*TCombobox*Listbox.selectForeground", BG)
    root.option_add("*TCombobox*Listbox.font", F["body"])
    root.option_add("*TCombobox*Listbox.relief", "flat")
    return s


def px(text):
    """Style des titres et boutons : en majuscules."""
    return str(text).upper()


def neon_line(master):
    """Double liseré cyan / magenta façon borne d'arcade."""
    tk.Frame(master, bg=CYAN, height=2).pack(fill="x")
    tk.Frame(master, bg=MAGENTA, height=2).pack(fill="x")
