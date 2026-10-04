"""Widgets rétro réutilisables : bouton, case à cocher, jauge, dialogue, grille de jaquettes."""
import os
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from PIL import Image, ImageTk

import core
import icons
import logos
import systems
import theme as T


class PixelButton(tk.Label):
    """Bouton plat avec icône pixel et effet néon au survol."""
    STYLES = {  # fond, texte, contour, fond survol, texte survol
        "normal": (T.PANEL2, T.TEXT, T.BORDER, T.BORDER, T.CYAN),
        "danger": (T.DANGER_BG, T.RED, T.RED, T.RED, T.BG),
        "toggle": (T.PANEL2, T.MUTED, T.BORDER, T.BORDER, T.CYAN),
        "fav": (T.PANEL2, T.YELLOW, T.BORDER, T.YELLOW, T.BG),
    }

    def __init__(self, master, text="", icon=None, command=None, style="normal", scale=2):
        self.colors = self.STYLES[style]
        bg, fg, outline, _, _ = self.colors
        super().__init__(master, text=text, font=T.F["btn"], bg=bg, fg=fg, bd=0, padx=12, pady=8,
                         highlightthickness=2, highlightbackground=outline, highlightcolor=outline,
                         cursor="hand2", compound="left")
        self.icon_name, self.scale, self.command = icon, scale, command
        self.enabled, self.active, self.hover = True, False, False
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self.set_text(text)
        self._paint()

    def set_text(self, text):
        text = T.px(text)
        self.configure(text=(" " + text) if text and self.icon_name else text)

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._paint()

    def set_active(self, active):
        self.active = active
        self._paint()

    def _set_hover(self, hover):
        self.hover = hover
        self._paint()

    def _click(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        if inside and self.enabled and self.command:
            self.command()

    def _paint(self):
        bg, fg, outline, hbg, hfg = self.colors
        if not self.enabled:
            bg, fg, outline = T.PANEL, T.BORDER, T.PANEL2
        elif self.hover or self.active:
            bg, fg, outline = hbg, hfg, (hfg if self.active else outline)
        img = icons.icon(self.icon_name, fg, self.scale) if self.icon_name else ""
        self.configure(bg=bg, fg=fg, highlightbackground=outline, highlightcolor=outline, image=img)


class Tooltip:
    """Bulle d'aide affichée au survol d'un widget."""

    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _):
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, font=T.F["small"], bg=T.PANEL2, fg=T.TEXT, padx=10, pady=6,
                 highlightthickness=1, highlightbackground=T.CYAN).pack()

    def hide(self, _):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class RetroCheck(tk.Label):
    """Case à cocher pixel liée à une BooleanVar."""

    def __init__(self, master, text, variable, command=None, bg=T.PANEL):
        super().__init__(master, text=" " + text, font=T.F["small"], bg=bg, fg=T.MUTED,
                         compound="left", cursor="hand2", bd=0)
        self.var, self.command = variable, command
        self.bind("<Button-1>", self._toggle)
        self._paint()

    def _toggle(self, _):
        self.var.set(not self.var.get())
        self._paint()
        if self.command:
            self.command()

    def _paint(self):
        on = self.var.get()
        self.configure(image=icons.icon("check_on" if on else "check_off", T.YELLOW if on else T.MUTED, 2),
                       fg=T.YELLOW if on else T.MUTED)


class HPBar(tk.Canvas):
    """Jauge segmentée façon barre de vie : occupation de la carte, par catégorie."""
    SEGMENTS, SEG_W, SEG_H, GAP = 36, 7, 14, 2

    def __init__(self, master, bg=T.PANEL):
        w = self.SEGMENTS * (self.SEG_W + self.GAP) + 4
        super().__init__(master, width=w, height=self.SEG_H + 6, bg=bg, highlightthickness=0)

    def set_parts(self, parts):
        """parts = [(fraction de la carte, couleur), ...] dans l'ordre d'affichage."""
        self.delete("all")
        self.create_rectangle(0, 0, int(self["width"]) - 1, self.SEG_H + 5, outline=T.BORDER, width=2)
        bounds, total = [], 0.0
        for ratio, color in parts:
            total += ratio
            bounds.append((total, color))
        for i in range(self.SEGMENTS):
            middle = (i + 0.5) / self.SEGMENTS
            color = next((c for limit, c in bounds if middle < limit), T.PANEL2)
            x = 3 + i * (self.SEG_W + self.GAP)
            self.create_rectangle(x, 3, x + self.SEG_W, 3 + self.SEG_H, width=0, fill=color)


def _dialog(parent, title, message, details, buttons, accent, icon_name):
    """Fenêtre modale rétro. buttons = [(texte, style, valeur)]. Retourne la valeur choisie."""
    d = tk.Toplevel(parent)
    d.withdraw()
    d.title(title)
    d.configure(bg=accent)
    d.resizable(False, False)
    d.transient(parent)
    box = tk.Frame(d, bg=T.PANEL, padx=28, pady=22)
    box.pack(fill="both", expand=True, padx=3, pady=3)

    head = tk.Frame(box, bg=T.PANEL)
    head.pack(fill="x")
    tk.Label(head, image=icons.icon(icon_name, accent, 4), bg=T.PANEL).pack(side="left")
    tk.Label(head, text=T.px(title), font=T.F["h1"], fg=accent, bg=T.PANEL).pack(side="left", padx=14)
    tk.Label(box, text=message, font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left",
             wraplength=520).pack(anchor="w", pady=(16, 8))
    if details:
        txt = tk.Text(box, height=min(10, details.count("\n") + 1), width=58, bg=T.BG, fg=T.MUTED,
                      font=T.F["small"], relief="flat", padx=10, pady=8, highlightthickness=0)
        txt.insert("1.0", details)
        txt.configure(state="disabled")
        txt.pack(fill="x", pady=(0, 8))

    result = {"value": None}

    def choose(value):
        result["value"] = value
        d.destroy()

    row = tk.Frame(box, bg=T.PANEL)
    row.pack(anchor="e", pady=(12, 0))
    for text, style, value in buttons:
        PixelButton(row, text, command=lambda v=value: choose(v), style=style).pack(side="left", padx=(10, 0))
    d.bind("<Escape>", lambda e: choose(buttons[0][2]))
    d.bind("<Return>", lambda e: choose(buttons[-1][2]))

    d.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - d.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - d.winfo_reqheight()) // 3
    d.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    d.deiconify()
    d.grab_set()
    d.focus_set()
    parent.wait_window(d)
    return result["value"]


def ask_delete(parent, message, details):
    return bool(_dialog(parent, "Supprimer ?", message, details,
                        [("ANNULER", "normal", False), ("SUPPRIMER", "danger", True)],
                        T.RED, "warning"))


def info(parent, title, message, details=""):
    _dialog(parent, title, message, details, [("OK", "normal", None)], T.YELLOW, "warning")


class CleanupDialog(tk.Toplevel):
    """Choix de ce qu'il faut nettoyer. self.result = problèmes cochés (None si annulé)."""

    def __init__(self, parent, root, categories, issues):
        super().__init__(parent, bg=T.CYAN)
        self.withdraw()
        self.title("Nettoyage de la carte")
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self.by_kind = {k: [i for i in issues if i.kind == k] for k in categories}
        self.vars = {}
        self._details = []   # (cadre du détail, lien) de chaque catégorie

        box = tk.Frame(self, bg=T.PANEL, padx=26, pady=20)
        box.pack(fill="both", expand=True, padx=3, pady=3)
        head = tk.Frame(box, bg=T.PANEL)
        head.pack(fill="x", pady=(0, 10))
        tk.Label(head, image=icons.icon("broom", T.CYAN, 3), bg=T.PANEL).pack(side="left")
        tk.Label(head, text="NETTOYAGE DE LA CARTE", font=T.F["h1"], fg=T.CYAN,
                 bg=T.PANEL).pack(side="left", padx=12)
        for kind, (title, explain, default) in categories.items():
            self._category(box, root, kind, title, explain, default)

        bottom = tk.Frame(box, bg=T.PANEL)
        bottom.pack(fill="x", pady=(16, 0))
        self.total = tk.Label(bottom, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
        self.total.pack(side="left")
        PixelButton(bottom, "NETTOYER", icon="broom", style="danger", command=self._ok).pack(side="right")
        PixelButton(bottom, "ANNULER", command=self.destroy).pack(side="right", padx=10)
        self.bind("<Escape>", lambda e: self.destroy())
        self._update_total()

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        parent.wait_window(self)

    def _category(self, box, root, kind, title, explain, default):
        items = self.by_kind[kind]
        frame = tk.Frame(box, bg=T.PANEL2, padx=14, pady=8)
        frame.pack(fill="x", pady=3)
        size = sum(i.size for i in items)
        if not items:
            tk.Label(frame, text=f"✓  {title} : rien à nettoyer", font=T.F["body"], fg=T.GREEN,
                     bg=T.PANEL2, anchor="w").pack(fill="x")
            return
        self.vars[kind] = tk.BooleanVar(value=default)
        row = tk.Frame(frame, bg=T.PANEL2)
        row.pack(fill="x")
        count = f"{title}  ·  {len(items)}" + (f"  ·  {human(size)}" if size else "")
        RetroCheck(row, count, self.vars[kind], command=self._update_total, bg=T.PANEL2).pack(side="left")
        link = tk.Label(row, text="▸ Voir le détail", font=T.F["small"], fg=T.CYAN, bg=T.PANEL2,
                        cursor="hand2")
        link.pack(side="right")
        tk.Label(frame, text=explain, font=T.F["small"], fg=T.MUTED, bg=T.PANEL2, anchor="w",
                 justify="left", wraplength=660).pack(fill="x", padx=(28, 0))

        details = tk.Frame(frame, bg=T.BG)
        text = tk.Text(details, height=min(7, len(items)), width=84, bg=T.BG, fg=T.MUTED,
                       font=T.F["small"], relief="flat", padx=8, pady=6, highlightthickness=0)
        sb = ttk.Scrollbar(details, orient="vertical", style=T.SCROLL, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        for i in items:
            text.insert("end", os.path.relpath(i.path, root) + (f"   ({i.note})" if i.note else "") + "\n")
        text.configure(state="disabled")
        self._details.append((details, link))

        def toggle(_):
            opened = details.winfo_ismapped()
            for d, lk in self._details:  # un seul détail ouvert à la fois
                d.pack_forget()
                lk.configure(text="▸ Voir le détail")
            if not opened:
                details.pack(fill="x", pady=(8, 0))
                link.configure(text="▾ Masquer le détail")
        link.bind("<Button-1>", toggle)

    def _selected(self):
        return [i for k, v in self.vars.items() if v.get() for i in self.by_kind[k]]

    def _update_total(self):
        sel = self._selected()
        size = sum(i.size for i in sel)
        self.total.configure(text=f"{len(sel)} élément{'s' if len(sel) > 1 else ''} à nettoyer"
                                  f"  ·  {human(size)} libérés" if sel else "Rien de coché")

    def _ok(self):
        self.result = self._selected()
        self.destroy()


class ProgressDialog(tk.Toplevel):
    """Fenêtre de progression avec barre segmentée et bouton Annuler."""
    SEGMENTS = 30

    def __init__(self, parent, title, on_cancel, icon="download"):
        super().__init__(parent, bg=T.CYAN)
        self._pulse = 0
        self.withdraw()
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", on_cancel)
        box = tk.Frame(self, bg=T.PANEL, padx=28, pady=22)
        box.pack(fill="both", expand=True, padx=3, pady=3)
        head = tk.Frame(box, bg=T.PANEL)
        head.pack(fill="x")
        tk.Label(head, image=icons.icon(icon, T.CYAN, 3), bg=T.PANEL).pack(side="left")
        tk.Label(head, text=T.px(title), font=T.F["h1"], fg=T.CYAN, bg=T.PANEL).pack(side="left", padx=12)
        self.label = tk.Label(box, font=T.F["body"], fg=T.TEXT, bg=T.PANEL, anchor="w", width=48)
        self.label.pack(fill="x", pady=(16, 8))
        self.bar = tk.Canvas(box, width=self.SEGMENTS * 15 + 4, height=22, bg=T.PANEL, highlightthickness=0)
        self.bar.pack(anchor="w")
        self.stats = tk.Label(box, font=T.F["small"], fg=T.MUTED, bg=T.PANEL, anchor="w")
        self.stats.pack(fill="x", pady=(8, 0))
        row = tk.Frame(box, bg=T.PANEL)
        row.pack(anchor="e", pady=(14, 0))
        PixelButton(row, "ANNULER", command=on_cancel).pack()
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()

    def set(self, done, total, text, stats=""):
        self.label.configure(text=text)
        self.stats.configure(text=stats)
        filled = round(done / max(total or 1, 1) * self.SEGMENTS)
        self._draw(lambda i: i < filled)

    def pulse(self):
        """Animation « chenille » quand la durée est inconnue."""
        self._pulse = (self._pulse + 1) % (self.SEGMENTS + 6)
        self._draw(lambda i: self._pulse - 6 <= i < self._pulse)

    def _draw(self, lit):
        self.bar.delete("all")
        for i in range(self.SEGMENTS):
            x = 2 + i * 15
            self.bar.create_rectangle(x, 2, x + 12, 20, width=0, fill=T.CYAN if lit(i) else T.PANEL2)


class ThumbLoader:
    """Charge les jaquettes en arrière-plan (les plus récemment demandées d'abord)."""
    MAX_CACHE, MAX_PENDING = 900, 300

    def __init__(self, widget, size, on_ready):
        self.widget, self.size, self.on_ready = widget, size, on_ready
        self.cache = {}            # chemin du jeu -> PhotoImage ou False (pas de jaquette)
        self.queued = set()
        self.pending = []
        self.results = queue.Queue()
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()
        self._poll()

    def get(self, game):
        if game.path in self.cache:
            return self.cache[game.path]
        if game.path not in self.queued:
            with self.lock:
                self.queued.add(game.path)
                self.pending.append(game)
                if len(self.pending) > self.MAX_PENDING:
                    self.queued.discard(self.pending.pop(0).path)
            self.wake.set()
        return None

    def _run(self):
        while True:
            self.wake.wait()
            with self.lock:
                if not self.pending:
                    self.wake.clear()
                    continue
                game = self.pending.pop()
            img = None
            path = core.cover_for(game)
            if path:
                try:
                    with Image.open(path) as im:
                        img = im.convert("RGBA")
                        img.thumbnail(self.size)
                except OSError:
                    img = None
            self.results.put((game.path, img))

    def _poll(self):
        changed = False
        while not self.results.empty():
            key, img = self.results.get_nowait()
            self.cache[key] = ImageTk.PhotoImage(img) if img else False
            self.queued.discard(key)
            changed = True
        if len(self.cache) > self.MAX_CACHE:
            for key in list(self.cache)[:200]:
                del self.cache[key]
        if changed:
            self.on_ready()
        self.widget.after(60, self._poll)


class GameGrid(tk.Frame):
    """Grille de jaquettes virtualisée : seules les cartes visibles sont dessinées."""
    CW, CH, GAP = 150, 222, 12
    COVER = (132, 124)

    STAR = 30  # zone cliquable de l'étoile favori (coin haut gauche de la carte)

    def __init__(self, master, on_select, on_activate, on_delete, on_favorite, on_context):
        super().__init__(master, bg=T.BG)
        self.on_select, self.on_activate, self.on_delete = on_select, on_activate, on_delete
        self.on_favorite, self.on_context = on_favorite, on_context
        self.canvas = tk.Canvas(self, bg=T.BG, highlightthickness=0, bd=0, yscrollincrement=20)
        sb = ttk.Scrollbar(self, orient="vertical", style=T.SCROLL, command=self._yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.games, self.selected = [], set()
        self.anchor = self.cursor = self.hover = None
        self.cols, self.x0 = 1, self.GAP
        self._font = tkfont.Font(self, font=T.F["card"])
        self._names = {}           # nom -> nom coupé sur deux lignes
        self.thumbs = ThumbLoader(self, self.COVER, self.redraw)

        c = self.canvas
        c.bind("<Configure>", lambda e: self._relayout())
        c.bind("<Button-1>", lambda e: self._click(e, "set"))
        c.bind("<Control-Button-1>", lambda e: self._click(e, "toggle"))
        c.bind("<Shift-Button-1>", lambda e: self._click(e, "range"))
        c.bind("<Double-Button-1>", self._double)
        c.bind("<Button-3>", self._right_click)
        c.bind("<Motion>", self._motion)
        c.bind("<Enter>", lambda e: c.bind_all("<MouseWheel>", self._wheel))
        c.bind("<Leave>", lambda e: (c.unbind_all("<MouseWheel>"), self._set_hover(None)))
        for key, delta in (("Left", -1), ("Right", 1), ("Up", "up"), ("Down", "down")):
            c.bind(f"<{key}>", lambda e, d=delta: self._move(d))
        c.bind("<Delete>", lambda e: self.on_delete())
        c.bind("<Return>", lambda e: self.on_activate())
        c.bind("<Control-a>", lambda e: self.select_all())
        c.bind("<f>", lambda e: self.on_favorite(None))

    # -- données
    def set_games(self, games, selected=(), keep_scroll=False):
        self.games = games
        self.selected = {id(g) for g in selected}
        self.anchor = self.cursor = self.hover = None
        top = self.canvas.yview()[0]
        self._relayout()
        self.canvas.yview_moveto(top if keep_scroll else 0)
        self.redraw()

    def set_selected(self, games):
        self.selected = {id(g) for g in games}
        self.redraw()

    def select_all(self):
        self.selected = {id(g) for g in self.games}
        self._notify()

    def _notify(self):
        self.redraw()
        self.on_select([g for g in self.games if id(g) in self.selected])

    # -- géométrie
    def _relayout(self):
        w = max(self.canvas.winfo_width(), 1)
        self.cols = max(1, (w - self.GAP) // (self.CW + self.GAP))
        used = self.cols * (self.CW + self.GAP) - self.GAP
        self.x0 = max(self.GAP, (w - used) // 2)
        rows = -(-len(self.games) // self.cols)
        self.canvas.configure(scrollregion=(0, 0, w, rows * (self.CH + self.GAP) + self.GAP))
        self.redraw()

    def _pos(self, i):
        r, c = divmod(i, self.cols)
        return self.x0 + c * (self.CW + self.GAP), self.GAP + r * (self.CH + self.GAP)

    def _index_at(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        c, cx = divmod(x - self.x0, self.CW + self.GAP)
        r, cy = divmod(y - self.GAP, self.CH + self.GAP)
        if c < 0 or c >= self.cols or r < 0 or cx > self.CW or cy > self.CH:
            return None
        i = int(r) * self.cols + int(c)
        return i if i < len(self.games) else None

    # -- dessin
    def redraw(self):
        cv = self.canvas
        cv.delete("all")
        if not self.games:
            cv.create_text(cv.winfo_width() // 2, 120, text="AUCUN JEU", font=T.F["h1"], fill=T.MUTED)
            return
        top, h = cv.canvasy(0), cv.winfo_height()
        step = self.CH + self.GAP
        first = max(0, int((top - self.GAP) // step)) * self.cols
        last = min(len(self.games), (int((top + h) // step) + 1) * self.cols)
        for i in range(first, last):
            self._draw_card(i)

    def _draw_card(self, i):
        cv, g = self.canvas, self.games[i]
        x, y = self._pos(i)
        sel, hov = id(g) in self.selected, i == self.hover
        color = systems.color(g.system)
        outline = T.CYAN if sel else T.MAGENTA if hov else T.BORDER
        cv.create_rectangle(x, y, x + self.CW, y + self.CH, fill=T.SELECT if sel else T.PANEL,
                            outline=outline, width=3 if sel or hov else 1)
        for cx, cy in ((x, y), (x + self.CW - 3, y), (x, y + self.CH - 3), (x + self.CW - 3, y + self.CH - 3)):
            cv.create_rectangle(cx, cy, cx + 3, cy + 3, fill=T.BG, width=0)  # coins « pixel »

        mid, cover_y = x + self.CW // 2, y + 8 + self.COVER[1] // 2
        img = self.thumbs.get(g)
        cv.create_image(mid, cover_y, image=img or icons.icon(systems.kind(g.system), color, 5))
        cv.create_text(mid, y + self.COVER[1] + 14, text=self._two_lines(g.name), width=self.CW - 12, anchor="n",
                       justify="center", font=T.F["card"], fill=T.CYAN if sel else T.TEXT)
        # ligne du bas : logo de la console à gauche, note (ou taille) à droite
        bottom = y + self.CH - 8
        badge = logos.get(g.system, 58, 18, fallback=False)
        if badge:
            cv.create_image(x + 7, bottom, image=badge, anchor="sw")
        else:
            cv.create_text(x + 8, bottom, text=g.system.upper(), anchor="sw", font=T.F["tiny"], fill=color)
        if g.rating is not None:
            cv.create_image(x + self.CW - 7, bottom - 3, image=icons.stars(g.rating), anchor="se")
        else:
            cv.create_text(x + self.CW - 8, bottom + 2, text=human(g.size), anchor="se",
                           font=T.F["small"], fill=T.MUTED)
        if not g.in_gamelist:
            cv.create_rectangle(x + self.CW - 16, y + 8, x + self.CW - 8, y + 16, fill=T.YELLOW, width=0)
        if g.favorite:
            cv.create_image(x + 6, y + 6, image=icons.icon("star", T.YELLOW, 2), anchor="nw")
        elif hov:
            cv.create_image(x + 6, y + 6, image=icons.icon("star_outline", T.MUTED, 2), anchor="nw")

    def _two_lines(self, text):
        """Coupe le nom pour qu'il tienne sur deux lignes de la carte (avec « … »)."""
        if text in self._names:
            return self._names[text]
        width = self.CW - 14
        measure = self._font.measure
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if measure(trial) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
        if len(lines) > 2:
            last = lines[1]
            while last and measure(last + " …") > width:
                last = last[:-1]
            lines = [lines[0], last.rstrip() + " …"]
        self._names[text] = "\n".join(lines)
        return self._names[text]

    # -- interactions
    def _yview(self, *args):
        self.canvas.yview(*args)
        self.redraw()

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) * 4, "units")
        self.redraw()

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.redraw()

    def _motion(self, event):
        self._set_hover(self._index_at(event))

    def _click(self, event, mode):
        self.canvas.focus_set()
        i = self._index_at(event)
        if i is None:
            if mode == "set" and self.selected:
                self.selected.clear()
                self._notify()
            return
        x, y = self._pos(i)
        if (mode == "set" and self.canvas.canvasx(event.x) - x < self.STAR
                and self.canvas.canvasy(event.y) - y < self.STAR):
            self.on_favorite([self.games[i]])  # clic sur l'étoile
            return
        key = id(self.games[i])
        if mode == "toggle":
            self.selected ^= {key}
        elif mode == "range" and self.anchor is not None:
            lo, hi = sorted((self.anchor, i))
            self.selected = {id(g) for g in self.games[lo:hi + 1]}
        else:
            self.selected = {key}
        if mode != "range":
            self.anchor = i
        self.cursor = i
        self._notify()

    def _right_click(self, event):
        """Clic droit : sélectionne la carte si elle ne l'est pas, puis ouvre le menu."""
        i = self._index_at(event)
        if i is None:
            return
        if id(self.games[i]) not in self.selected:
            self.selected = {id(self.games[i])}
            self.anchor = self.cursor = i
            self._notify()
        self.on_context(event)

    def _double(self, event):
        if self._index_at(event) is not None:
            self.on_activate()

    def _move(self, delta):
        if not self.games:
            return
        cur = self.cursor if self.cursor is not None else -1
        step = {"up": -self.cols, "down": self.cols}.get(delta, delta)
        i = min(max(cur + step, 0), len(self.games) - 1)
        self.cursor = self.anchor = i
        self.selected = {id(self.games[i])}
        self._ensure_visible(i)
        self._notify()

    def _ensure_visible(self, i):
        _, y = self._pos(i)
        top, h = self.canvas.canvasy(0), self.canvas.winfo_height()
        total = float(self.canvas.cget("scrollregion").split()[3]) or 1
        if y < top:
            self.canvas.yview_moveto((y - self.GAP) / total)
        elif y + self.CH > top + h:
            self.canvas.yview_moveto((y + self.CH + self.GAP - h) / total)


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"
