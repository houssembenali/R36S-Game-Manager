"""Fenêtres des outils : liste à cocher, ajout de jeux, modification de fiche, rapport."""
import io
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageGrab, ImageTk

import gamecat
import gptk
import icons
import net
import ports
import regions
import scraper
import settings
import systems
import theme as T
from i18n import _, _n
from widgets import PixelButton, RetroCheck, human


class RetroWindow(tk.Toplevel):
    """Base des fenêtres : cadre néon, en-tête avec icône, centrée et modale.
    Les sous-classes remplissent self.body puis appellent self.show()."""

    def __init__(self, parent, title, icon, accent=T.CYAN):
        super().__init__(parent, bg=accent)
        self.withdraw()
        self.parent = parent
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self.body = tk.Frame(self, bg=T.PANEL, padx=26, pady=20)
        self.body.pack(fill="both", expand=True, padx=3, pady=3)
        head = tk.Frame(self.body, bg=T.PANEL)
        head.pack(fill="x", pady=(0, 12))
        tk.Label(head, image=icons.icon(icon, accent, 3), bg=T.PANEL).pack(side="left")
        tk.Label(head, text=T.px(title), font=T.F["h1"], fg=accent, bg=T.PANEL).pack(side="left", padx=12)
        self.bind("<Escape>", lambda e: self.destroy())

    def buttons(self, ok_text, ok_icon=None, ok_style="normal", left=None):
        """Barre du bas : [left] … ANNULER  OK. Retourne le bouton OK."""
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(16, 0))
        if left is not None:
            left(bar)
        ok = PixelButton(bar, ok_text, icon=ok_icon, style=ok_style, command=self.ok)
        ok.pack(side="right")
        PixelButton(bar, _("ANNULER"), command=self.destroy).pack(side="right", padx=10)
        return ok

    def ok(self):
        self.destroy()

    def show(self):
        self.update_idletasks()
        p = self.parent
        x = p.winfo_rootx() + (p.winfo_width() - self.winfo_reqwidth()) // 2
        y = p.winfo_rooty() + max(0, (p.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.grab_set()
        self.focus_set()
        p.wait_window(self)
        return self.result


def scroll_area(master, height):
    """Zone défilante : retourne le cadre intérieur où placer les lignes."""
    outer = tk.Frame(master, bg=T.PANEL2)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, bg=T.PANEL2, highlightthickness=0, height=height, width=640)
    sb = ttk.Scrollbar(outer, orient="vertical", style=T.SCROLL, command=canvas.yview)
    inner = tk.Frame(canvas, bg=T.PANEL2)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))  # pleine largeur
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    wheel = lambda e: canvas.yview_scroll(int(-e.delta / 120) * 3, "units")
    canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
    canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    return inner


class ChecklistDialog(RetroWindow):
    """Liste d'éléments à cocher. items = [(libellé, détail, coché, taille ou None)].
    Résultat : indices cochés (None si annulé)."""

    def __init__(self, parent, title, icon, intro, items, ok_text, ok_style="normal", note=""):
        super().__init__(parent, title, icon)
        tk.Label(self.body, text=intro, font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left",
                 wraplength=660, anchor="w").pack(fill="x", pady=(0, 10))
        self.items = items
        self.vars = []
        inner = scroll_area(self.body, min(380, 40 * len(items) + 10))
        for label, detail, checked, size in items:
            var = tk.BooleanVar(value=checked)
            self.vars.append(var)
            row = tk.Frame(inner, bg=T.PANEL2, padx=10, pady=4)
            row.pack(fill="x")
            RetroCheck(row, label, var, command=self._update, bg=T.PANEL2).pack(side="left")
            if size is not None:
                tk.Label(row, text=human(size), font=T.F["small"], fg=T.TEXT, bg=T.PANEL2).pack(side="right")
            if detail:
                tk.Label(row, text=detail, font=T.F["small"], fg=T.MUTED, bg=T.PANEL2).pack(side="right", padx=12)
        if note:
            tk.Label(self.body, text=note, font=T.F["small"], fg=T.YELLOW, bg=T.PANEL, justify="left",
                     wraplength=660, anchor="w").pack(fill="x", pady=(10, 0))

        def left(bar):
            self.total = tk.Label(bar, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
            self.total.pack(side="left")
            for text, value in ((_("Tout"), True), (_("Rien"), False)):
                link = tk.Label(bar, text=text, font=T.F["small"], fg=T.CYAN, bg=T.PANEL, cursor="hand2")
                link.pack(side="left", padx=(14, 0))
                link.bind("<Button-1>", lambda e, v=value: self._set_all(v))
        self.ok_btn = self.buttons(ok_text, icon, ok_style, left)
        self._update()

    def _set_all(self, value):
        for v in self.vars:
            v.set(value)
        # les cases dessinées sont mises à jour via leur variable
        for row in self.body.winfo_children():
            self._repaint(row)
        self._update()

    def _repaint(self, widget):
        if isinstance(widget, RetroCheck):
            widget._paint()
        for child in widget.winfo_children():
            self._repaint(child)

    def _checked(self):
        return [i for i, v in enumerate(self.vars) if v.get()]

    def _update(self):
        chosen = self._checked()
        size = sum(self.items[i][3] or 0 for i in chosen)
        self.total.configure(text=_n(len(chosen), "{n} sélectionné", "{n} sélectionnés")
                                  + (f"  ·  {human(size)}" if size else ""))
        self.ok_btn.set_enabled(bool(chosen))

    def ok(self):
        self.result = self._checked()
        self.destroy()


class ImportDialog(RetroWindow):
    """Choix de la console de chaque fichier à ajouter.
    rows = [(chemin, système deviné ou None, taille)]. Résultat : ([(chemin, système)], chercher_images)."""

    def __init__(self, parent, rows, available, free):
        super().__init__(parent, _("Ajouter des jeux"), "plus")
        self.rows = [list(r) for r in rows]
        self.choices = sorted(set(available) | set(systems.EXTENSIONS), key=lambda s: systems.name(s).lower())
        self.labels = {f"{systems.name(s)}  ({s})": s for s in self.choices}
        self.free = free
        tk.Label(self.body, text=_("Vérifie la console de chaque jeu. Sélectionne une ou plusieurs lignes "
                                   "pour changer leur console."), font=T.F["body"], fg=T.TEXT, bg=T.PANEL,
                 wraplength=700, justify="left", anchor="w").pack(fill="x", pady=(0, 10))
        frame = tk.Frame(self.body, bg=T.PANEL)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("system", "size"), show="tree headings", height=min(12, len(rows)))
        self.tree.heading("#0", text=_("FICHIER"), anchor="w")
        self.tree.heading("system", text=_("CONSOLE"), anchor="w")
        self.tree.heading("size", text=_("TAILLE"), anchor="e")
        self.tree.column("#0", width=380)
        self.tree.column("system", width=220)
        self.tree.column("size", width=90, anchor="e")
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("missing", foreground=T.YELLOW)

        pick = tk.Frame(self.body, bg=T.PANEL)
        pick.pack(fill="x", pady=(10, 0))
        tk.Label(pick, text=_("Console de la sélection :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        self.combo = ttk.Combobox(pick, values=list(self.labels), state="readonly", width=34, font=T.F["body"])
        self.combo.pack(side="left", padx=8)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._assign())
        self.scrape = tk.BooleanVar(value=True)
        RetroCheck(self.body, _("Compléter ensuite les fiches depuis internet (image, description, année, genre…)"),
                   self.scrape).pack(anchor="w", pady=(10, 0))

        def left(bar):
            self.total = tk.Label(bar, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
            self.total.pack(side="left")
        self.ok_btn = self.buttons(_("AJOUTER"), "plus", left=left)
        self._fill()

    def _fill(self):
        sel = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for i, (path, system, size) in enumerate(self.rows):
            label = f"{systems.name(system)}  ({system})" if system else "⚠ " + _("à choisir")
            self.tree.insert("", "end", iid=str(i), text="  " + os.path.basename(path), values=(label, human(size)),
                             tags=() if system else ("missing",))
        self.tree.selection_set(sel)
        missing = sum(1 for r in self.rows if not r[1])
        size = sum(r[2] for r in self.rows)
        text = _n(len(self.rows), "{n} jeu", "{n} jeux") + f"  ·  {human(size)}"
        if size > self.free:
            text += "  ·  ⚠ " + _("pas assez de place ({free} libres)", free=human(self.free))
        elif missing:
            text += "  ·  " + _n(missing, "{n} jeu sans console", "{n} jeux sans console")
        self.total.configure(text=text, fg=T.RED if size > self.free else T.TEXT)
        self.ok_btn.set_enabled(not missing and size <= self.free)

    def _assign(self):
        system = self.labels.get(self.combo.get())
        for iid in self.tree.selection() or self.tree.get_children():
            self.rows[int(iid)][1] = system
        self._fill()

    def ok(self):
        self.result = ([(p, s) for p, s, _x in self.rows if s], self.scrape.get())  # sans console : ignoré
        self.destroy()


class StarPicker(tk.Canvas):
    """5 étoiles cliquables (demi-étoiles) pour choisir une note entre 0 et 1."""
    SCALE = 3

    def __init__(self, master, rating):
        self.star = 12 * self.SCALE + 2 * self.SCALE
        super().__init__(master, width=5 * self.star, height=12 * self.SCALE, bg=T.PANEL, highlightthickness=0,
                         cursor="hand2")
        self.value = rating
        self.bind("<Button-1>", self._click)
        self.bind("<Motion>", lambda e: self._draw(self._at(e.x)))
        self.bind("<Leave>", lambda e: self._draw(self.value))
        self._draw(rating)

    def _at(self, x):
        halves = min(10, max(1, int(x / self.star * 2) + 1))
        return halves / 10

    def _click(self, event):
        self.value = self._at(event.x)
        self._draw(self.value)

    def _draw(self, rating):
        self.delete("all")
        self.create_image(0, 0, image=icons.stars(rating or 0, self.SCALE), anchor="nw")


UNCHANGED = object()  # image non modifiée


class ImageSlot(tk.Frame):
    """Aperçu d'une image du jeu + boutons pour la remplacer (fichier, presse-papiers, internet)
    ou la retirer. self.change : UNCHANGED, des octets (nouvelle image) ou None (retirer)."""
    PREVIEW = (220, 150)

    def __init__(self, master, game, tag, title):
        super().__init__(master, bg=T.PANEL2, padx=10, pady=8)
        self.game, self.tag, self.change = game, tag, UNCHANGED
        tk.Label(self, text=title, font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL2, anchor="w").pack(fill="x")
        self.preview = tk.Label(self, bg=T.BG, fg=T.MUTED, font=T.F["small"], compound="center")
        self.preview.pack(pady=6)
        self._blank = tk.PhotoImage(width=self.PREVIEW[0], height=self.PREVIEW[1])
        row = tk.Frame(self, bg=T.PANEL2)
        row.pack()
        for i, (text, command, style) in enumerate(((_("FICHIER"), self._from_file, "normal"),
                                                    (_("COLLER"), self._from_clipboard, "normal"),
                                                    (_("INTERNET"), self._from_internet, "normal"),
                                                    (_("RETIRER"), self._remove, "danger"))):
            b = PixelButton(row, text, command=command, style=style)
            b.configure(padx=8, pady=4)
            b.grid(row=0, column=i, padx=2)
        current = next((game.media[t] for t in scraper.SLOTS[tag][0]
                        if t in game.media and os.path.isfile(game.media[t])), None)
        self._show_path(current)

    def _show(self, im, text=""):
        if im is None:
            self._photo = None
            self.preview.configure(image=self._blank, text=text or _("Aucune image"))
            return
        im = im.convert("RGBA")
        im.thumbnail(self.PREVIEW)
        self._photo = ImageTk.PhotoImage(im)
        self.preview.configure(image=self._photo, text="", width=self.PREVIEW[0], height=self.PREVIEW[1])

    def _show_path(self, path):
        try:
            with Image.open(path) as im:
                self._show(im.copy())
        except (OSError, TypeError, AttributeError):
            self._show(None)

    def _set(self, data):
        """Accepte des octets s'ils forment une image valide."""
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                self._show(im.copy())
            self.change = data
        except OSError:
            self._show(None, _("Fichier non reconnu comme image"))

    def _from_file(self):
        path = filedialog.askopenfilename(parent=self, title=_("Choisir une image"), filetypes=[
            (_("Images"), "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), (_("Tous les fichiers"), "*.*")])
        if path:
            with open(path, "rb") as f:
                self._set(f.read())

    def _from_clipboard(self):
        clip = ImageGrab.grabclipboard()  # image copiée, ou liste de fichiers copiés
        if isinstance(clip, list) and clip:
            with open(clip[0], "rb") as f:
                return self._set(f.read())
        if clip is None or isinstance(clip, list):
            return self._show(None, _("Presse-papiers sans image"))
        buf = io.BytesIO()
        clip.save(buf, "PNG")
        self._set(buf.getvalue())

    def _from_internet(self):
        self._show(None, _("Recherche…"))
        result = {}
        thread = threading.Thread(target=lambda: result.update(data=scraper.fetch_bytes(self.game, self.tag)),
                                  daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(150, poll)
            elif result.get("data"):
                self._set(result["data"])
            else:
                self._show(None, _("Introuvable sur internet"))
        poll()

    def _remove(self):
        self.change = None
        self._show(None)


class EditDialog(RetroWindow):
    """Modification de la fiche d'un jeu. Résultat : dict pour core.set_info (None si annulé)."""
    FIELDS = (("name", "Nom"), ("year", "Année"), ("genre", "Genre"), ("developer", "Développeur"),
              ("publisher", "Éditeur"), ("players", "Joueurs"))

    def __init__(self, parent, game):
        super().__init__(parent, _("Modifier la fiche"), "edit")
        top = tk.Frame(self.body, bg=T.PANEL)
        top.pack(fill="x")
        grid = tk.Frame(top, bg=T.PANEL)
        grid.pack(side="left", fill="x", anchor="n")
        images = tk.Frame(top, bg=T.PANEL)
        images.pack(side="left", anchor="n", padx=(22, 0))
        self.slots = [ImageSlot(images, game, "image", _("IMAGE (fiche du jeu)")),
                      ImageSlot(images, game, "thumbnail", _("JAQUETTE (vue grille)"))]
        for slot in self.slots:
            slot.pack(pady=(0, 10))
        current = {"name": game.name, "year": game.info.get("releasedate", "")[:4]}
        self.entries = {}
        for r, (key, label) in enumerate(self.FIELDS):
            tk.Label(grid, text=T.px(_(label)), font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL,
                     anchor="w").grid(row=r, column=0, sticky="w", pady=4)
            e = tk.Entry(grid, bg=T.PANEL2, fg=T.TEXT, insertbackground=T.CYAN, relief="flat", font=T.F["body"],
                         width=40, highlightthickness=1, highlightbackground=T.BORDER, highlightcolor=T.CYAN)
            e.insert(0, current.get(key, game.info.get(key, "")))
            e.grid(row=r, column=1, sticky="we", padx=(14, 0), ipady=4)
            self.entries[key] = e
        r = len(self.FIELDS)
        tk.Label(grid, text=_("NOTE"), font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL).grid(row=r, column=0, sticky="w", pady=6)
        stars = tk.Frame(grid, bg=T.PANEL)
        stars.grid(row=r, column=1, sticky="w", padx=(14, 0))
        self.stars = StarPicker(stars, game.rating)
        self.stars.pack(side="left")
        clear = tk.Label(stars, text=_("Effacer"), font=T.F["small"], fg=T.CYAN, bg=T.PANEL, cursor="hand2")
        clear.pack(side="left", padx=14)
        clear.bind("<Button-1>", lambda e: (setattr(self.stars, "value", None), self.stars._draw(None)))
        tk.Label(self.body, text=_("DESCRIPTION"), font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL,
                 anchor="w").pack(fill="x", pady=(10, 4))
        self.desc = tk.Text(self.body, height=7, width=70, wrap="word", bg=T.PANEL2, fg=T.TEXT, font=T.F["small"],
                            insertbackground=T.CYAN, relief="flat", padx=8, pady=6, highlightthickness=1,
                            highlightbackground=T.BORDER, highlightcolor=T.CYAN)
        self.desc.insert("1.0", game.info.get("desc", ""))
        self.desc.pack(fill="x")
        self.buttons(_("ENREGISTRER"), "save")

    def ok(self):
        values = {k: e.get() for k, e in self.entries.items()}
        values["desc"] = self.desc.get("1.0", "end").strip()
        values["rating"] = self.stars.value
        values["images"] = {s.tag: s.change for s in self.slots if s.change is not UNCHANGED}
        self.result = values
        self.destroy()


class HistoryDialog(RetroWindow):
    """Historique des opérations annulables + corbeille.
    history = [(id, libellé, date ISO, taille)]. Résultat : "undo", "empty" ou None."""

    def __init__(self, parent, history, trash):
        super().__init__(parent, _("Historique et corbeille"), "undo")
        intro = _("Les fichiers supprimés ou remplacés sont gardés dans une corbeille cachée sur la carte : "
                  "on peut annuler la dernière opération, puis la précédente… Vider la corbeille libère la place "
                  "mais rend ces opérations définitives.") if history else _("Aucune opération à annuler.")
        tk.Label(self.body, text=intro, font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left",
                 wraplength=640, anchor="w").pack(fill="x", pady=(0, 10))
        if history:
            inner = scroll_area(self.body, min(320, 38 * len(history) + 10))
            for i, (_op_id, label, date, size) in enumerate(history):
                row = tk.Frame(inner, bg=T.PANEL2, padx=12, pady=6)
                row.pack(fill="x")
                when = f"{date[8:10]}/{date[5:7]}  {date[11:16]}"
                tk.Label(row, text=when, font=T.F["small"], fg=T.MUTED, bg=T.PANEL2, width=12,
                         anchor="w").pack(side="left")
                tk.Label(row, text=label, font=T.F["body"], fg=T.CYAN if i == 0 else T.TEXT,
                         bg=T.PANEL2).pack(side="left")
                tk.Label(row, text=human(size), font=T.F["small"], fg=T.MUTED, bg=T.PANEL2).pack(side="right")
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(16, 0))
        empty = PixelButton(bar, f"{_('VIDER LA CORBEILLE')} ({human(trash)})", icon="trash", style="danger",
                            command=lambda: self._choose("empty"))
        empty.pack(side="left")
        empty.set_enabled(trash > 0 or bool(history))
        undo = PixelButton(bar, _("ANNULER LA DERNIÈRE"), icon="undo", command=lambda: self._choose("undo"))
        undo.pack(side="right")
        undo.set_enabled(bool(history))
        PixelButton(bar, _("FERMER"), command=self.destroy).pack(side="right", padx=10)

    def _choose(self, value):
        self.result = value
        self.destroy()


class ReportDialog(RetroWindow):
    """Rapport en lignes colorées. lines = [(texte, tag)] avec tag dans ok / bad / warn / head / None."""

    def __init__(self, parent, title, icon, intro, lines):
        super().__init__(parent, title, icon)
        tk.Label(self.body, text=intro, font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left",
                 wraplength=680, anchor="w").pack(fill="x", pady=(0, 10))
        frame = tk.Frame(self.body, bg=T.BG)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, height=min(22, len(lines) + 1), width=86, bg=T.BG, fg=T.TEXT, font=T.F["small"],
                       relief="flat", padx=12, pady=8, highlightthickness=0, wrap="word")
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        for tag, color in (("ok", T.GREEN), ("bad", T.RED), ("warn", T.YELLOW), ("muted", T.MUTED)):
            text.tag_configure(tag, foreground=color)
        text.tag_configure("head", foreground=T.CYAN, font=T.F["tiny"], spacing1=10, spacing3=4)
        for line, tag in lines:
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(14, 0))
        PixelButton(bar, "OK", command=self.destroy).pack(side="right")


class PortCatalogDialog(RetroWindow):
    """Catalogue PortMaster : recherche, filtre « prêts à jouer », aperçu et choix des ports à installer.
    catalog = [ports.Port] ; have = {zip: md5 installé} ; waiting = zips déjà dans autoinstall.
    Résultat : liste des Port cochés (None si annulé)."""
    PREVIEW = (300, 200)

    def __init__(self, parent, catalog, have, waiting, likes=None):
        super().__init__(parent, _("Catalogue PortMaster"), "download")
        self.catalog, self.have, self.waiting = catalog, have, waiting
        self.likes = likes or {}  # genres que tu joues (recommandations)
        self.by_key = {p.key: p for p in catalog}
        self.marked, self.shots, self.shown = set(), {}, None
        # badge « nouveau » : ports arrivés depuis la dernière ouverture du catalogue
        self.seen = settings.get("port_seen") or ""
        newest = max((p.added for p in catalog), default="")
        if newest > self.seen:
            settings.set("port_seen", newest)
            settings.save()
        tk.Label(self.body, text=_("Les ports cochés sont copiés dans ports/PortMaster/autoinstall : PortMaster "
                                   "les installe au prochain lancement sur la console. Les « prêts à jouer » "
                                   "fonctionnent tout de suite ; les autres demandent les fichiers du jeu original."),
                 font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left", wraplength=980,
                 anchor="w").pack(fill="x", pady=(0, 10))
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(0, 8))
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *a: self._fill())
        tk.Label(bar, text=_("Rechercher :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        tk.Entry(bar, textvariable=self.query, bg=T.PANEL2, fg=T.TEXT, insertbackground=T.CYAN, relief="flat",
                 font=T.F["body"], width=28, highlightthickness=1, highlightbackground=T.BORDER,
                 highlightcolor=T.CYAN).pack(side="left", padx=(8, 18), ipady=3)
        self.prices = [_("Gratuits et payants"), _("Gratuits"), _("Payants")]
        self.price = ttk.Combobox(bar, values=self.prices, state="readonly", width=18, font=T.F["body"])
        self.price.current(0)
        self.price.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.price.pack(side="left")
        self.all_genres = _("Tous les genres")
        genres = sorted({g for p in catalog for g in p.genres})
        self.genre = ttk.Combobox(bar, values=[self.all_genres] + genres, state="readonly", width=16,
                                  font=T.F["body"])
        self.genre.set(self.all_genres)
        self.genre.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.genre.pack(side="left", padx=18)
        # tris : (id, libellé, clé, décroissant, colonne dont l'en-tête active ce tri)
        state_rank = {"update": 0, "installed": 1}
        self.sorts = [
            ("name", _("Nom (A → Z)"), lambda p: p.title.lower(), False, "#0"),
            ("popular", _("Plus téléchargés"), lambda p: p.downloads, True, "downloads"),
            ("rating", _("Meilleures notes"), lambda p: (p.rating * p.votes + 30) / (p.votes + 10) if p.votes
             else 0, True, "rating"),
            ("recommended", _("Recommandés pour toi"), lambda p: ports.recommend_score(p, self.likes), True, ""),
            ("name_desc", _("Nom (Z → A)"), lambda p: p.title.lower(), True, "#0"),
            ("added", _("Ajoutés récemment"), lambda p: p.added, True, "date"),
            ("added_old", _("Ajoutés il y a longtemps"), lambda p: p.added, False, "date"),
            ("updated", _("Mis à jour récemment"), lambda p: p.updated, True, "date"),
            ("genre", _("Genre"), lambda p: p.genres[0] if p.genres else "~", False, "genre"),
            ("small", _("Plus petits d'abord"), lambda p: p.size, False, "size"),
            ("big", _("Plus gros d'abord"), lambda p: p.size, True, "size"),
            ("state", _("Installés d'abord"),
             lambda p: (p.key not in self.waiting, state_rank.get(self._state(p)[1], 2)), False, "state"),
        ]
        saved = settings.get("port_sort")
        self.sort_id = saved if any(s[0] == saved for s in self.sorts) else "name"
        tk.Label(bar, text=_("Trier par :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        self.sort_box = ttk.Combobox(bar, values=[s[1] for s in self.sorts], state="readonly", width=24,
                                     font=T.F["body"])
        self.sort_box.bind("<<ComboboxSelected>>",
                           lambda e: self._set_sort(self.sorts[self.sort_box.current()][0]))
        self.sort_box.pack(side="left", padx=(8, 0))
        checks = tk.Frame(self.body, bg=T.PANEL)
        checks.pack(fill="x", pady=(0, 8))
        self.rtr_only, self.suited_only, self.new_only = (tk.BooleanVar(value=v) for v in (True, True, False))
        for text, var in ((_("Prêts à jouer seulement"), self.rtr_only),
                          (_("Adaptés à la R36S seulement"), self.suited_only),
                          (_("Nouveautés seulement"), self.new_only)):
            RetroCheck(checks, text, var, command=self._fill).pack(side="left", padx=(0, 22))

        main = tk.Frame(self.body, bg=T.PANEL)
        main.pack(fill="both", expand=True)
        frame = tk.Frame(main, bg=T.PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("downloads", "rating", "genre", "date", "size", "state"),
                                 show="tree headings", height=16, selectmode="browse")
        self.headings = {"#0": _("PORT"), "downloads": _("TÉLÉCH."), "rating": _("NOTE"), "genre": _("GENRE"),
                         "date": _("AJOUTÉ LE"), "size": _("TAILLE"), "state": _("ÉTAT")}
        for col, width, anchor in (("#0", 250, "w"), ("downloads", 80, "e"), ("rating", 90, "w"),
                                   ("genre", 120, "w"), ("date", 95, "w"), ("size", 75, "e"), ("state", 100, "w")):
            self.tree.heading(col, text=self.headings[col], anchor=anchor,
                              command=lambda c=col: self._sort_by_column(c))
            self.tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("marked", foreground=T.GREEN)
        self.tree.tag_configure("installed", foreground=T.MUTED)
        self.tree.tag_configure("update", foreground=T.YELLOW)
        self.tree.tag_configure("new", foreground=T.CYAN)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._preview())
        self.tree.bind("<Double-1>", lambda e: self._toggle())
        self.tree.bind("<space>", lambda e: self._toggle())

        side = tk.Frame(main, bg=T.PANEL2, padx=12, pady=10, width=340)
        side.pack(side="left", fill="y", padx=(12, 0))
        side.pack_propagate(False)
        self._blank = tk.PhotoImage(width=self.PREVIEW[0], height=self.PREVIEW[1])
        self.image = tk.Label(side, image=self._blank, bg=T.BG, fg=T.MUTED, font=T.F["small"], compound="center")
        self.image.pack()
        self.title_lbl = tk.Label(side, font=T.F["body"], fg=T.CYAN, bg=T.PANEL2, wraplength=310, justify="left",
                                  anchor="w")
        self.title_lbl.pack(fill="x", pady=(8, 2))
        self.text = tk.Text(side, wrap="word", bg=T.PANEL2, fg=T.TEXT, font=T.F["small"], relief="flat",
                            highlightthickness=0, height=10, width=36)
        self.text.tag_configure("ok", foreground=T.GREEN)
        self.text.tag_configure("warn", foreground=T.YELLOW)
        self.text.tag_configure("muted", foreground=T.MUTED)
        self.text.pack(fill="both", expand=True)
        self.store_btn = PixelButton(side, "", command=self._open_store)
        self.mark_btn = PixelButton(side, _("COCHER"), command=self._toggle)
        self.mark_btn.pack(fill="x", pady=(8, 0))

        def left(b):
            self.total = tk.Label(b, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
            self.total.pack(side="left")
        self.ok_btn = self.buttons(_("INSTALLER"), "download", left=left)
        self._set_sort(self.sort_id)

    def _set_sort(self, sort_id):
        """Applique un tri (gardé pour la prochaine ouverture) et l'indique sur l'en-tête de sa colonne."""
        self.sort_id = sort_id
        settings.set("port_sort", sort_id)
        settings.save()
        i = next(i for i, s in enumerate(self.sorts) if s[0] == sort_id)
        _id, _label, _key, desc, column = self.sorts[i]
        self.sort_box.current(i)
        self.headings["date"] = _("MIS À JOUR") if sort_id == "updated" else _("AJOUTÉ LE")
        for col, text in self.headings.items():
            self.tree.heading(col, text=text + ((" ▼" if desc else " ▲") if col == column else ""))
        self._fill()

    def _sort_by_column(self, column):
        """Clic sur un en-tête : premier tri de cette colonne, puis les suivants à chaque clic."""
        ids = [s[0] for s in self.sorts if s[4] == column]
        self._set_sort(ids[(ids.index(self.sort_id) + 1) % len(ids)] if self.sort_id in ids else ids[0])

    def _sorted(self):
        _id, _label, key, desc, _col = next(s for s in self.sorts if s[0] == self.sort_id)
        by_name = sorted(self.catalog, key=lambda p: p.title.lower())
        return sorted(by_name, key=key, reverse=desc)  # tri stable : à égalité, ordre alphabétique

    def _state(self, p):
        """(texte de la colonne ÉTAT, tag de couleur)."""
        if p.key in self.waiting:
            return _("en attente"), "installed"
        if p.key in self.have:
            if self.have[p.key] and p.md5 and self.have[p.key] != p.md5:
                return _("mise à jour"), "update"
            return _("installé"), "installed"
        if self._is_new(p):
            return _("nouveau"), "new"
        return "", ""

    def _is_new(self, p):
        return bool(self.seen) and p.added > self.seen

    def _open_store(self):
        p = self.by_key.get(self.shown)
        if p and p.stores:
            webbrowser.open(p.stores[0][1])

    def _row(self, p):
        marked = p.key in self.marked
        tag = "marked" if marked else self._state(p)[1]
        return ("☑ " if marked else "☐ ") + p.title, (tag,) if tag else ()

    def _fill(self):
        q = self.query.get().strip().lower()
        genre = self.genre.get()
        self.tree.delete(*self.tree.get_children())
        date_updated = self.sort_id == "updated"
        price = self.price.current()
        for p in self._sorted():
            if p.key not in self.marked:  # un port coché reste visible quels que soient les filtres
                if self.rtr_only.get() and not p.rtr:
                    continue
                if self.suited_only.get() and (p.unsuited or p.exp):
                    continue
                if self.new_only.get() and not self._is_new(p):
                    continue
                if price and p.paid != (price == 2):
                    continue
            if genre != self.all_genres and genre not in p.genres:
                continue
            if q and q not in p.title.lower() and q not in p.desc.lower():
                continue
            text, tags = self._row(p)
            self.tree.insert("", "end", iid=p.key, text=text, tags=tags,
                             values=(f"{p.downloads:,}".replace(",", " ") if p.downloads else "",
                                     stars(p.rating) if p.votes else "", ", ".join(p.genres[:2]),
                                     p.updated if date_updated else p.added, human(p.size), self._state(p)[0]))
        if self.shown and self.tree.exists(self.shown):
            self.tree.selection_set(self.shown)
            self.tree.see(self.shown)
        self._update()

    def _toggle(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        self.marked ^= {key}
        text, tags = self._row(self.by_key[key])
        self.tree.item(key, text=text, tags=tags)
        self._preview()
        self._update()

    def _update(self):
        chosen = [self.by_key[k] for k in self.marked]
        self.total.configure(text=_n(len(chosen), "{n} sélectionné", "{n} sélectionnés")
                                  + (f"  ·  {human(sum(p.size for p in chosen))}" if chosen else ""))
        self.ok_btn.set_enabled(bool(chosen))

    def _preview(self):
        sel = self.tree.selection()
        if not sel:
            return
        p = self.by_key[sel[0]]
        self.shown = p.key
        self.title_lbl.configure(text=p.title)
        self.mark_btn.configure(text=_("DÉCOCHER") if p.key in self.marked else _("COCHER"))
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if p.rtr:
            t.insert("end", "✓ " + _("Prêt à jouer : aucun fichier à fournir.") + "\n\n", "ok")
        else:
            t.insert("end", "⚠ " + _("Ce port a besoin des fichiers du jeu original.") + "\n", "warn")
            if p.inst:
                t.insert("end", p.inst.strip() + "\n", "muted")  # instructions du port (en anglais)
            t.insert("end", "\n")
        if p.paid:
            t.insert("end", _("Le jeu original est payant.") + "\n\n", "warn")
        reasons = {"power": _("demande une console plus puissante"), "ultra": _("demande une console plus puissante"),
                   "2gb": _("demande 2 Go de mémoire (la R36S en a 1)"), "opengl": _("demande OpenGL"),
                   "!arkos": _("ne fonctionne pas sous ArkOS")}
        for r in dict.fromkeys(reasons[u.lower()] for u in p.unsuited):
            t.insert("end", "⚠ " + _("Peut ne pas tourner sur la R36S : {reason}.", reason=r) + "\n", "warn")
        if p.exp:
            t.insert("end", "⚠ " + _("Port expérimental : il peut mal fonctionner.") + "\n", "warn")
        if p.unsuited or p.exp:
            t.insert("end", "\n")
        t.insert("end", p.desc.strip() + "\n\n")
        if p.porter:
            t.insert("end", _("Porté par : {names}", names=", ".join(p.porter)) + "\n", "muted")
        if p.updated:
            t.insert("end", _("Mis à jour le {date}", date=p.updated) + "\n", "muted")
        if p.downloads:
            t.insert("end", _("Téléchargé {n} fois", n=f"{p.downloads:,}".replace(",", " ")) + "\n", "muted")
        if p.votes:
            t.insert("end", _("Jeu original : {rating} / 5 ({votes} votes)", rating=f"{p.rating:.1f}".replace(".", ","),
                              votes=p.votes) + "\n", "muted")
        t.configure(state="disabled")
        if p.stores:
            self.store_btn.set_text(_("VOIR SUR {store}", store=p.stores[0][0].upper()))
            self.store_btn.pack(fill="x", pady=(8, 0), before=self.mark_btn)
        else:
            self.store_btn.pack_forget()
        self._show_shot(p)

    def _show_shot(self, p):
        """Capture du port, téléchargée en arrière-plan puis gardée pour la session."""
        if p.key in self.shots:
            photo = self.shots[p.key]
            self.image.configure(image=photo or self._blank, text="" if photo else _("Pas d'image"))
            return
        self.image.configure(image=self._blank, text=_("Chargement…") if p.screenshot else _("Pas d'image"))
        if not p.screenshot:
            return
        result = {}

        def fetch():
            try:
                with Image.open(io.BytesIO(net.get(p.screenshot, timeout=20))) as im:
                    im = im.convert("RGB")
                    im.thumbnail(self.PREVIEW)
                    result["im"] = im
            except Exception:
                pass  # pas d'image : on affiche juste le texte
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

        def poll():
            if not self.winfo_exists():
                return
            if thread.is_alive():
                self.after(150, poll)
                return
            self.shots[p.key] = ImageTk.PhotoImage(result["im"]) if "im" in result else None
            if self.shown == p.key:
                self._show_shot(p)
        poll()

    def ok(self):
        self.result = [p for p in self.catalog if p.key in self.marked]
        self.destroy()


def stars(rating):
    """« ★★★★☆ 4,2 » : note sur 5 en étoiles (une étoile de plus à partir de x,75)."""
    full = int(rating + 0.25)
    return "★" * full + "☆" * (5 - full) + f" {rating:.1f}".replace(".", ",")


class GameCatalogDialog(RetroWindow):
    """Catalogue de jeux par console : tous les jeux sortis (fiches) et jeux gratuits installables.
    consoles = [dossier] ; games = {dossier: [Game]} de la carte. Résultat : [gamecat.Entry] à installer."""
    PREVIEW = (300, 220)

    def __init__(self, parent, consoles, games, start=None):
        super().__init__(parent, _("Catalogue de jeux"), "gamepad")
        self.games = games
        self.consoles = sorted(consoles, key=lambda s: systems.name(s).lower())
        self.data, self.loading = {}, set()   # dossier -> [Entry] ; consoles en cours de chargement
        self.marked, self.shots, self.shown = {}, {}, None
        self.keys, self.files = {}, {}        # dossier -> titres / fichiers présents sur la carte
        self.counts = (0, 0, 0)
        self.ratings = None                   # index des notes LaunchBox (chargé en arrière-plan)
        self.index = {}                       # identifiant de ligne -> Entry
        tk.Label(self.body, text=_("Tous les jeux sortis sur chaque console, avec ceux que tu as déjà. Les jeux du "
                                   "commerce sont protégés : copie-les depuis ta cartouche ou ton disque. Les jeux "
                                   "gratuits et légaux (homebrew, Freedoom) s'installent directement sur la carte."),
                 font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left", wraplength=1040,
                 anchor="w").pack(fill="x", pady=(0, 10))
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text=_("Console :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        self.console = ttk.Combobox(bar, values=[systems.name(s) for s in self.consoles], state="readonly",
                                    width=24, font=T.F["body"])
        self.console.current(self.consoles.index(start) if start in self.consoles else 0)
        self.console.bind("<<ComboboxSelected>>", lambda e: self._load())
        self.console.pack(side="left", padx=(8, 18))
        self.views = [_("Tous les jeux"), _("Sur ma carte"), _("Manquants"), _("Gratuits à installer")]
        self.view = ttk.Combobox(bar, values=self.views, state="readonly", width=20, font=T.F["body"])
        self.view.current(0)
        self.view.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.view.pack(side="left")
        self.all_genres = _("Tous les genres")
        self.genre = ttk.Combobox(bar, values=[self.all_genres], state="readonly", width=18, font=T.F["body"])
        self.genre.set(self.all_genres)
        self.genre.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.genre.pack(side="left", padx=18)
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *a: self._fill())
        tk.Label(bar, text=_("Rechercher :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        tk.Entry(bar, textvariable=self.query, bg=T.PANEL2, fg=T.TEXT, insertbackground=T.CYAN, relief="flat",
                 font=T.F["body"], width=24, highlightthickness=1, highlightbackground=T.BORDER,
                 highlightcolor=T.CYAN).pack(side="left", padx=(8, 0), ipady=3)
        # tris : (id, libellé, clé, décroissant, colonne)
        self.sorts = [
            ("title", _("Titre (A → Z)"), lambda e: e.title.lower(), False, "#0"),
            ("rating", _("Meilleures notes"), lambda e: e.score, True, "rating"),
            ("popular", _("Plus populaires"), lambda e: e.votes, True, "votes"),
            ("recent", _("Plus récents"), lambda e: e.year or "0", True, "year"),
            ("old", _("Plus anciens"), lambda e: e.year or "9999", False, "year"),
        ]
        saved = settings.get("game_sort")
        self.sort_id = saved if any(s[0] == saved for s in self.sorts) else "title"
        sort_bar = tk.Frame(self.body, bg=T.PANEL)
        sort_bar.pack(fill="x", pady=(0, 8))
        tk.Label(sort_bar, text=_("Trier par :"), font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        self.sort_box = ttk.Combobox(sort_bar, values=[s[1] for s in self.sorts], state="readonly", width=20,
                                     font=T.F["body"])
        self.sort_box.current(next(i for i, s in enumerate(self.sorts) if s[0] == self.sort_id))
        self.sort_box.bind("<<ComboboxSelected>>", lambda e: self._set_sort(self.sorts[self.sort_box.current()][0]))
        self.sort_box.pack(side="left", padx=(8, 18))
        self.rating_lbl = tk.Label(sort_bar, text=_("Notes : chargement…"), font=T.F["small"], fg=T.MUTED,
                                   bg=T.PANEL)
        self.rating_lbl.pack(side="left")

        main = tk.Frame(self.body, bg=T.PANEL)
        main.pack(fill="both", expand=True)
        frame = tk.Frame(main, bg=T.PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("rating", "votes", "year", "genre", "region", "state"),
                                 show="tree headings", height=18, selectmode="browse")
        self.headings = {"#0": _("JEU"), "rating": _("NOTE"), "votes": _("VOTES"), "year": _("ANNÉE"),
                         "genre": _("GENRE"), "region": _("RÉGIONS"), "state": _("ÉTAT")}
        for col, width, anchor in (("#0", 300, "w"), ("rating", 90, "w"), ("votes", 60, "e"), ("year", 55, "w"),
                                   ("genre", 110, "w"), ("region", 90, "w"), ("state", 110, "w")):
            self.tree.heading(col, text=self.headings[col], anchor=anchor,
                              command=lambda c=col: self._sort_by_column(c))
            self.tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("owned", foreground=T.GREEN)
        self.tree.tag_configure("free", foreground=T.CYAN)
        self.tree.tag_configure("marked", foreground=T.YELLOW)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._preview())
        self.tree.bind("<Double-1>", lambda e: self._toggle())
        self.tree.bind("<space>", lambda e: self._toggle())

        side = tk.Frame(main, bg=T.PANEL2, padx=12, pady=10, width=340)
        side.pack(side="left", fill="y", padx=(12, 0))
        side.pack_propagate(False)
        self._blank = tk.PhotoImage(width=self.PREVIEW[0], height=self.PREVIEW[1])
        self.image = tk.Label(side, image=self._blank, bg=T.BG, fg=T.MUTED, font=T.F["small"], compound="center")
        self.image.pack()
        self.title_lbl = tk.Label(side, font=T.F["body"], fg=T.CYAN, bg=T.PANEL2, wraplength=310, justify="left",
                                  anchor="w")
        self.title_lbl.pack(fill="x", pady=(8, 2))
        self.text = tk.Text(side, wrap="word", bg=T.PANEL2, fg=T.TEXT, font=T.F["small"], relief="flat",
                            highlightthickness=0, height=10, width=36)
        for tag, color in (("ok", T.GREEN), ("warn", T.YELLOW), ("muted", T.MUTED), ("free", T.CYAN)):
            self.text.tag_configure(tag, foreground=color)
        self.text.pack(fill="both", expand=True)
        self.site_btn = PixelButton(side, _("SITE DU JEU"), command=self._open_site)
        self.mark_btn = PixelButton(side, _("COCHER"), command=self._toggle)

        def left(b):
            self.total = tk.Label(b, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
            self.total.pack(side="left")
        self.ok_btn = self.buttons(_("INSTALLER"), "download", left=left)
        self._show_sort()
        self._load()
        self._load_ratings()

    # ---------------------------------------------------------------- données
    @property
    def system(self):
        return self.consoles[self.console.current()]

    def _load_ratings(self):
        """Notes LaunchBox : index local, téléchargé (108 Mo, 20 s) au premier usage puis une fois par mois."""
        box = {}
        thread = threading.Thread(target=lambda: box.update(table=gamecat.ratings()), daemon=True)
        thread.start()

        def poll():
            if not self.winfo_exists():
                return
            if thread.is_alive():
                self.after(200, poll)
                return
            self.ratings = box.get("table") or {}
            for system, entries in self.data.items():
                self.data[system] = gamecat.apply_ratings(entries, self.ratings)
            self.rating_lbl.configure(text=_("Notes et popularité : communauté LaunchBox") if self.ratings
                                      else _("Notes indisponibles (pas d'internet ?)"))
            self._fill()
        poll()

    def _set_sort(self, sort_id):
        self.sort_id = sort_id
        settings.set("game_sort", sort_id)
        settings.save()
        self._show_sort()
        self._fill()

    def _show_sort(self):
        i = next(i for i, s in enumerate(self.sorts) if s[0] == self.sort_id)
        _id, _label, _key, desc, column = self.sorts[i]
        self.sort_box.current(i)
        for col, text in self.headings.items():
            self.tree.heading(col, text=text + ((" ▼" if desc else " ▲") if col == column else ""))

    def _sort_by_column(self, column):
        """Clic sur un en-tête : tri de cette colonne (puis l'autre sens pour l'année)."""
        ids = [s[0] for s in self.sorts if s[4] == column]
        if ids:
            self._set_sort(ids[(ids.index(self.sort_id) + 1) % len(ids)] if self.sort_id in ids else ids[0])

    def _sorted(self, entries):
        """Jeux dans l'ordre du tri choisi (à égalité : ordre alphabétique)."""
        _id, _label, key, desc, _col = next(s for s in self.sorts if s[0] == self.sort_id)
        return sorted(sorted(entries, key=lambda e: e.title.lower()), key=key, reverse=desc)

    def _load(self):
        """Charge la liste de la console choisie (en arrière-plan, gardée pour la session)."""
        system = self.system
        if system in self.data or system in self.loading:
            self._fill()
            return
        self.loading.add(system)
        self._fill()
        box = {}

        def fetch():
            out = []
            for source in (gamecat.free_games, gamecat.commercial):
                try:
                    out += source(system)
                except (OSError, ValueError, KeyError) as e:
                    box["error"] = str(e)
            box["entries"] = out
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

        def poll():
            if not self.winfo_exists():
                return
            if thread.is_alive():
                self.after(150, poll)
                return
            self.loading.discard(system)
            if box.get("entries"):
                self.data[system] = gamecat.apply_ratings(box["entries"], self.ratings or {})
            if system == self.system:
                self._fill(error=False if box.get("entries") else "net" if "error" in box else "empty")
        poll()

    def _owned(self, e):
        if e.system not in self.keys:
            games = self.games.get(e.system, [])
            self.keys[e.system] = gamecat.owned_keys(games)
            self.files[e.system] = {os.path.basename(g.path).lower() for g in games}
        return gamecat.owned(e, self.keys[e.system], self.files[e.system])

    # ---------------------------------------------------------------- liste
    def _fill(self, error=False):
        self.tree.delete(*self.tree.get_children())
        system = self.system
        entries = self.data.get(system)
        if entries is None:
            self.counts = None
            self.total.configure(text=(_("Liste indisponible (pas d'internet ?)") if error == "net"
                                       else _("Pas de liste de jeux pour cette console.") if error
                                       else _("Chargement de la liste…")))
            self.ok_btn.set_enabled(bool(self.marked))
            return
        genres = sorted({e.genre for e in entries if e.genre})
        self.genre.configure(values=[self.all_genres] + genres)
        if self.genre.get() not in genres:
            self.genre.set(self.all_genres)
        q, genre, view = self.query.get().strip().lower(), self.genre.get(), self.view.current()
        shown = owned = 0
        for e in self._sorted(entries):
            have = self._owned(e)
            owned += have
            if (view == 1 and not have) or (view == 2 and have) or (view == 3 and not e.free):
                continue
            if genre != self.all_genres and e.genre != genre:
                continue
            if q and q not in e.title.lower() and not any(q in n.lower() for n in e.names):
                continue
            shown += 1
            iid = f"e{id(e)}"  # stable même quand la liste est réorganisée (tri, regroupement)
            self.index[iid] = e
            text, tags, state = self._row(e, iid, have)
            self.tree.insert("", "end", iid=iid, text=text, tags=tags,
                             values=(stars(e.rating) if e.votes else "", f"{e.votes:,}".replace(",", " ")
                                     if e.votes else "", e.year, e.genre, " ".join(c.upper() for c in e.regions[:4]),
                                     state))
        if self.shown and self.tree.exists(self.shown):
            self.tree.selection_set(self.shown)
            self.tree.see(self.shown)
        self.counts = (shown, owned, len(entries))
        self._update_total()

    def _update_total(self):
        text = ""
        if self.counts:
            shown, owned, total = self.counts
            text = _("{shown} jeux affichés · {owned} sur ta carte sur {total}", shown=shown, owned=owned,
                     total=total)
        if self.marked:
            text += "  ·  " + _("{n} à installer", n=len(self.marked))
        self.total.configure(text=text)
        self.ok_btn.set_enabled(bool(self.marked))

    def _row(self, e, iid, have):
        if have:
            return "  " + e.title, ("owned",), "✓ " + _("sur ta carte")
        if e.free:
            marked = iid in self.marked
            return ("☑ " if marked else "☐ ") + e.title, ("marked" if marked else "free",), _("gratuit")
        return "  " + e.title, (), ""

    def _entry(self, iid):
        return self.index[iid]

    def _toggle(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        e = self._entry(iid)
        if not e.free or self._owned(e):
            return
        if iid in self.marked:
            del self.marked[iid]
        else:
            self.marked[iid] = e
        text, tags, _state = self._row(e, iid, False)
        self.tree.item(iid, text=text, tags=tags)
        self._preview()
        self._update_total()

    # ---------------------------------------------------------------- aperçu
    def _preview(self):
        sel = self.tree.selection()
        if not sel:
            return
        e = self._entry(sel[0])
        self.shown = sel[0]
        self.title_lbl.configure(text=e.title)
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        if self._owned(e):
            t.insert("end", "✓ " + _("Ce jeu est sur ta carte.") + "\n\n", "ok")
        elif e.free:
            t.insert("end", "★ " + _("Gratuit et légal : il s'installe directement sur la carte.") + "\n\n", "free")
        else:
            t.insert("end", _("Jeu du commerce : copie-le depuis ta propre cartouche ou ton disque, puis ajoute-le "
                              "avec « Ajouter des jeux ».") + "\n\n", "muted")
        if e.votes:
            t.insert("end", _("Note : ") , "muted")
            t.insert("end", _("{rating} / 5 ({votes} votes)", rating=f"{e.rating:.1f}".replace(".", ","),
                              votes=f"{e.votes:,}".replace(",", " ")) + "\n", "free")
        for label, value in ((_("Année"), e.year), (_("Genre"), e.genre), (_("Développeur"), e.developer),
                             (_("Régions"), ", ".join(regions.region_name(c) for c in e.regions)),
                             (_("Licence"), e.license)):
            if value:
                t.insert("end", f"{label} : ", "muted")
                t.insert("end", value + "\n")
        if e.desc:
            t.insert("end", "\n" + e.desc + "\n")
        if len(e.names) > 1:
            t.insert("end", "\n" + _("Versions :") + "\n" + "\n".join("· " + n for n in e.names[:12]) + "\n", "muted")
        t.configure(state="disabled")
        self.site_btn.pack_forget()
        self.mark_btn.pack_forget()
        if e.website:
            self.site_btn.pack(fill="x", pady=(8, 0))
        if e.free and not self._owned(e):
            self.mark_btn.set_text(_("DÉCOCHER") if self.shown in self.marked else _("COCHER"))
            self.mark_btn.pack(fill="x", pady=(8, 0))
        self._show_shot(e, sel[0])

    def _open_site(self):
        if self.shown:
            webbrowser.open(self._entry(self.shown).website)

    def _show_shot(self, e, iid):
        """Image du jeu (capture des jeux gratuits, jaquette libretro sinon), chargée en arrière-plan."""
        if iid in self.shots:
            photo = self.shots[iid]
            self.image.configure(image=photo or self._blank, text="" if photo else _("Pas d'image"))
            return
        self.image.configure(image=self._blank, text=_("Chargement…"))
        result = {}

        def fetch():
            try:
                url = e.image or gamecat.boxart_url(e)
                if url:
                    with Image.open(io.BytesIO(net.get(url, timeout=20))) as im:
                        im = im.convert("RGB")
                        im.thumbnail(self.PREVIEW)
                        result["im"] = im
            except Exception:
                pass  # pas d'image : on affiche juste le texte
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

        def poll():
            if not self.winfo_exists():
                return
            if thread.is_alive():
                self.after(150, poll)
                return
            self.shots[iid] = ImageTk.PhotoImage(result["im"]) if "im" in result else None
            if self.shown == iid:
                self._show_shot(e, iid)
        poll()

    def ok(self):
        self.result = list(self.marked.values())
        self.destroy()


class StatsDialog(RetroWindow):
    """Statistiques de la collection (stats.Stats)."""

    def __init__(self, parent, s):
        super().__init__(parent, _("Statistiques"), "gamepad")
        tiles = tk.Frame(self.body, bg=T.PANEL)
        tiles.pack(fill="x", pady=(0, 14))
        for value, label, color in ((s.total, _("JEUX"), T.CYAN), (s.systems, _("CONSOLES"), T.MAGENTA),
                                    (s.plays, _("PARTIES"), T.GREEN), (s.favorites, _("FAVORIS"), T.YELLOW),
                                    (s.total - s.played, _("JAMAIS LANCÉS"), T.ORANGE)):
            box = tk.Frame(tiles, bg=T.PANEL2, padx=18, pady=10)
            box.pack(side="left", padx=(0, 10), fill="x", expand=True)
            tk.Label(box, text=f"{value:,}".replace(",", " "), font=T.F["h1"], fg=color, bg=T.PANEL2).pack(anchor="w")
            tk.Label(box, text=label, font=T.F["tiny"], fg=T.MUTED, bg=T.PANEL2).pack(anchor="w", pady=(6, 0))
        tk.Label(self.body, text=_("{size} de jeux · {played} jeux lancés au moins une fois · les jeux jamais "
                                   "lancés occupent {never}.", size=human(s.size), played=s.played,
                                   never=human(s.never_size)),
                 font=T.F["body"], fg=T.TEXT, bg=T.PANEL, anchor="w").pack(fill="x", pady=(0, 12))
        cols = tk.Frame(self.body, bg=T.PANEL)
        cols.pack(fill="both", expand=True)
        left, middle, right = (tk.Frame(cols, bg=T.PANEL, width=360) for _i in range(3))
        for col in (left, middle, right):
            col.pack(side="left", fill="both", expand=True, padx=(0, 18), anchor="n")
        self._list(left, _("LES PLUS JOUÉS"), [(g.name, _n(g.playcount, "{n} partie", "{n} parties"))
                                                for g in s.top_played[:8]])
        self._list(left, _("DERNIERS JOUÉS"), [(g.name, g.lastplayed.strftime("%d/%m/%Y")) for g in s.recent[:6]])
        self._bars(middle, _("CONSOLES (PAR PARTIES)"),
                   [(systems.name(sy), plays, _n(n, "{n} jeu", "{n} jeux") + f" · {_n(plays, '{n} partie', '{n} parties')}")
                    for sy, n, _size, _p, plays in s.by_system], T.CYAN)
        self._bars(right, _("GENRES"), [(g, n, _n(n, "{n} jeu", "{n} jeux")) for g, n in s.genres[:6]], T.MAGENTA)
        self._list(right, _("GROS JEUX JAMAIS LANCÉS"), [(g.name, human(g.size)) for g in s.biggest_never[:5]])
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(14, 0))
        PixelButton(bar, "OK", command=self.destroy).pack(side="right")

    def _head(self, master, text):
        tk.Label(master, text=T.px(text), font=T.F["tiny"], fg=T.YELLOW, bg=T.PANEL,
                 anchor="w").pack(fill="x", pady=(8, 6))

    def _list(self, master, title, rows):
        self._head(master, title)
        if not rows:
            tk.Label(master, text="—", font=T.F["small"], fg=T.MUTED, bg=T.PANEL, anchor="w").pack(fill="x")
        for name, value in rows:
            row = tk.Frame(master, bg=T.PANEL)
            row.pack(fill="x")
            tk.Label(row, text=name, font=T.F["small"], fg=T.TEXT, bg=T.PANEL, anchor="w").pack(side="left")
            tk.Label(row, text=value, font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="right")

    def _bars(self, master, title, rows, color):
        """Barres horizontales : [(libellé, valeur, texte)] ; seules les 10 premières sont affichées."""
        self._head(master, title)
        top = max((v for _l, v, _t in rows), default=0) or 1
        for label, value, text in rows[:10]:
            row = tk.Frame(master, bg=T.PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=label, font=T.F["small"], fg=T.TEXT, bg=T.PANEL, width=18, anchor="w").pack(side="left")
            c = tk.Canvas(row, width=150, height=12, bg=T.PANEL2, highlightthickness=0)
            c.pack(side="left", padx=6)
            c.create_rectangle(0, 0, max(2, int(150 * value / top)), 12, fill=color, width=0)
            tk.Label(row, text=text, font=T.F["small"], fg=T.MUTED, bg=T.PANEL, anchor="w").pack(side="left")


class ThemesDialog(RetroWindow):
    """Thèmes EmulationStation de la carte. Résultat : ("folder" | "zip", None) pour en ajouter un,
    ("delete", [themes.Theme]) pour en supprimer, None si fermé."""
    PREVIEW = (320, 220)

    def __init__(self, parent, theme_list, card_systems):
        super().__init__(parent, _("Thèmes EmulationStation"), "grid")
        self.themes, self.card = theme_list, card_systems
        tk.Label(self.body, text=_("Les thèmes changent l'apparence des menus de la console. Le thème utilisé se "
                                   "choisit sur la console : START → UI SETTINGS → THEME SET. Un thème qui ne "
                                   "dessine pas toutes tes consoles les affiche sans image."),
                 font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left", wraplength=980,
                 anchor="w").pack(fill="x", pady=(0, 10))
        main = tk.Frame(self.body, bg=T.PANEL)
        main.pack(fill="both", expand=True)
        frame = tk.Frame(main, bg=T.PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("size", "state"), show="tree headings", height=14,
                                 selectmode="extended")
        for col, text, width, anchor in (("#0", _("THÈME"), 280, "w"), ("size", _("TAILLE"), 90, "e"),
                                         ("state", _("TES CONSOLES"), 260, "w")):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor)
        self.tree.tag_configure("partial", foreground=T.YELLOW)
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        for i, t in enumerate(theme_list):
            missing = t.missing(card_systems)
            state = (_("toutes") if not missing else
                     _("{n} sur {total} : partiel", n=len(card_systems) - len(missing), total=len(card_systems)))
            self.tree.insert("", "end", iid=str(i), text="  " + t.name, values=(human(t.size), state),
                             tags=("partial",) if missing else ())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._preview())

        side = tk.Frame(main, bg=T.PANEL2, padx=12, pady=10, width=350)
        side.pack(side="left", fill="y", padx=(12, 0))
        side.pack_propagate(False)
        self._blank = tk.PhotoImage(width=self.PREVIEW[0], height=self.PREVIEW[1])
        self.image = tk.Label(side, image=self._blank, bg=T.BG, fg=T.MUTED, font=T.F["small"], compound="center")
        self.image.pack()
        self.info = tk.Label(side, font=T.F["small"], fg=T.TEXT, bg=T.PANEL2, wraplength=320, justify="left",
                             anchor="nw")
        self.info.pack(fill="both", expand=True, pady=(10, 0))

        def left(b):
            PixelButton(b, _("AJOUTER UN DOSSIER…"), icon="folder", command=lambda: self._close(("folder", None))
                        ).pack(side="left")
            PixelButton(b, _("AJOUTER UN .ZIP…"), icon="plus", command=lambda: self._close(("zip", None))
                        ).pack(side="left", padx=10)
        self.ok_btn = self.buttons(_("SUPPRIMER"), "trash", "danger", left=left)
        self.ok_btn.set_enabled(False)
        self._photo = None

    def _close(self, result):
        self.result = result
        self.destroy()

    def _selected(self):
        return [self.themes[int(i)] for i in self.tree.selection()]

    def _preview(self):
        sel = self._selected()
        self.ok_btn.set_enabled(bool(sel))
        if not sel:
            return
        t = sel[-1]
        missing = t.missing(self.card)
        text = _("{n} consoles dessinées", n=len(t.systems)) if t.systems else ""
        if t.generic:
            text += ("\n" if text else "") + _("Thème complet : il sert aussi aux autres consoles.")
        if missing:
            text += ("\n\n" if text else "") + _("Tes consoles sans image avec ce thème :") + "\n" + \
                ", ".join(systems.name(s) for s in missing)
        self.info.configure(text=text)
        self._photo = None
        if t.preview:
            try:
                with Image.open(t.preview) as im:
                    im = im.convert("RGBA").convert("RGB")
                    im.thumbnail(self.PREVIEW)
                    self._photo = ImageTk.PhotoImage(im)
            except OSError:
                pass
        self.image.configure(image=self._photo or self._blank, text="" if self._photo else _("Pas d'aperçu"))

    def ok(self):
        self._close(("delete", self._selected()))


class CardMoveDialog(RetroWindow):
    """Guide pour passer à une nouvelle carte SD. Résultat : « backup », « restore » ou None."""

    def __init__(self, parent, backup):
        super().__init__(parent, _("Passer à une nouvelle carte SD"), "sd")
        steps = (
            (_("1. COPIE LA CARTE ACTUELLE SUR LE PC"),
             _("Tous tes jeux, images, sauvegardes, ports et thèmes (la partition EASYROMS) sont copiés dans un "
               "dossier du PC. Compte une heure pour 100 Go ; la copie peut être arrêtée et reprise."),
             _("COPIER LA CARTE SUR LE PC"), "backup"),
            (_("2. PRÉPARE LA NOUVELLE CARTE"),
             _("Prends une carte de marque (SanDisk, Samsung, Kingston…) : celles livrées avec la R36S lâchent "
               "souvent. Écris dessus l'image ArkOS de ta R36S avec balenaEtcher ou Rufus, mets-la dans la "
               "console et démarre-la une fois (ArkOS prépare la carte), puis remets-la dans le PC."), "", ""),
            (_("3. REMETS TA COPIE SUR LA NOUVELLE CARTE"),
             _("Choisis la partition EASYROMS de la nouvelle carte en haut de la fenêtre, puis remets ta copie "
               "dessus. Les fichiers déjà présents et identiques sont gardés, rien n'est supprimé."),
             _("REMETTRE MA COPIE SUR CETTE CARTE"), "restore"),
        )
        for title, text, button, action in steps:
            box = tk.Frame(self.body, bg=T.PANEL2, padx=16, pady=12)
            box.pack(fill="x", pady=(0, 10))
            tk.Label(box, text=title, font=T.F["tiny"], fg=T.YELLOW, bg=T.PANEL2, anchor="w").pack(fill="x")
            tk.Label(box, text=text, font=T.F["body"], fg=T.TEXT, bg=T.PANEL2, justify="left", wraplength=640,
                     anchor="w").pack(fill="x", pady=(8, 0))
            if button:
                PixelButton(box, button, icon="sd", command=lambda a=action: self._close(a)).pack(anchor="e",
                                                                                                 pady=(10, 0))
        if backup:
            tk.Label(self.body, text=_("Dernière copie : {path}", path=backup), font=T.F["small"], fg=T.MUTED,
                     bg=T.PANEL, anchor="w").pack(fill="x")
        bar = tk.Frame(self.body, bg=T.PANEL)
        bar.pack(fill="x", pady=(10, 0))
        PixelButton(bar, _("FERMER"), command=self.destroy).pack(side="right")

    def _close(self, action):
        self.result = action
        self.destroy()


class KeysDialog(RetroWindow):
    """Touches d'un port (.gptk) : bouton de la console -> touche du clavier. Résultat : {bouton: touche}
    des touches changées (None si annulé)."""
    def __init__(self, parent, name, path, mapping):
        super().__init__(parent, _("Touches : {name}", name=name), "gamepad")
        tk.Label(self.body, text=_("Chaque bouton de la console envoie une touche du clavier au jeu. Choisis la "
                                   "touche dans la liste ou écris-la. Fichier : {file}", file=os.path.basename(path)),
                 font=T.F["body"], fg=T.TEXT, bg=T.PANEL, justify="left", wraplength=620,
                 anchor="w").pack(fill="x", pady=(0, 10))
        inner = scroll_area(self.body, min(460, 34 * len(mapping) + 10))
        self.mapping, self.vars = mapping, {}
        for button, key in mapping:
            row = tk.Frame(inner, bg=T.PANEL2, padx=10, pady=3)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=gptk.LABELS.get(button, button), font=T.F["body"], fg=T.CYAN, bg=T.PANEL2, width=14,
                     anchor="w").pack(side="left")
            var = tk.StringVar(value=key)
            ttk.Combobox(row, textvariable=var, values=gptk.KEYS, width=24, font=T.F["body"]).pack(side="left")
            self.vars[button] = var
        self.buttons(_("ENREGISTRER"), "save")

    def ok(self):
        old = dict(self.mapping)
        self.result = {b: v.get().strip() for b, v in self.vars.items() if v.get().strip() != old[b]}
        self.destroy()
