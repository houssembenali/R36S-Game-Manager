"""Fenêtres des outils : liste à cocher, ajout de jeux, modification de fiche, rapport."""
import io
import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image, ImageGrab, ImageTk

import icons
import net
import scraper
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

    def __init__(self, parent, catalog, have, waiting):
        super().__init__(parent, _("Catalogue PortMaster"), "download")
        self.catalog, self.have, self.waiting = catalog, have, waiting
        self.by_key = {p.key: p for p in catalog}
        self.marked, self.shots, self.shown = set(), {}, None
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
        self.rtr_only = tk.BooleanVar(value=True)
        RetroCheck(bar, _("Prêts à jouer seulement"), self.rtr_only, command=self._fill).pack(side="left")
        self.all_genres = _("Tous les genres")
        genres = sorted({g for p in catalog for g in p.genres})
        self.genre = ttk.Combobox(bar, values=[self.all_genres] + genres, state="readonly", width=16,
                                  font=T.F["body"])
        self.genre.set(self.all_genres)
        self.genre.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.genre.pack(side="left", padx=18)

        main = tk.Frame(self.body, bg=T.PANEL)
        main.pack(fill="both", expand=True)
        frame = tk.Frame(main, bg=T.PANEL)
        frame.pack(side="left", fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=("genre", "size", "state"), show="tree headings", height=16,
                                 selectmode="browse")
        for col, text, width, anchor in (("#0", _("PORT"), 300, "w"), ("genre", _("GENRE"), 150, "w"),
                                         ("size", _("TAILLE"), 80, "e"), ("state", _("ÉTAT"), 120, "w")):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor)
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("marked", foreground=T.GREEN)
        self.tree.tag_configure("installed", foreground=T.MUTED)
        self.tree.tag_configure("update", foreground=T.YELLOW)
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
        self.mark_btn = PixelButton(side, _("COCHER"), command=self._toggle)
        self.mark_btn.pack(fill="x", pady=(8, 0))

        def left(b):
            self.total = tk.Label(b, font=T.F["body"], fg=T.TEXT, bg=T.PANEL)
            self.total.pack(side="left")
        self.ok_btn = self.buttons(_("INSTALLER"), "download", left=left)
        self._fill()

    def _state(self, p):
        """(texte de la colonne ÉTAT, tag de couleur)."""
        if p.key in self.waiting:
            return _("en attente"), "installed"
        if p.key in self.have:
            if self.have[p.key] and p.md5 and self.have[p.key] != p.md5:
                return _("mise à jour"), "update"
            return _("installé"), "installed"
        return "", ""

    def _row(self, p):
        marked = p.key in self.marked
        tag = "marked" if marked else self._state(p)[1]
        return ("☑ " if marked else "☐ ") + p.title, (tag,) if tag else ()

    def _fill(self):
        q = self.query.get().strip().lower()
        genre = self.genre.get()
        self.tree.delete(*self.tree.get_children())
        for p in self.catalog:
            if self.rtr_only.get() and not p.rtr and p.key not in self.marked:
                continue
            if genre != self.all_genres and genre not in p.genres:
                continue
            if q and q not in p.title.lower() and q not in p.desc.lower():
                continue
            text, tags = self._row(p)
            self.tree.insert("", "end", iid=p.key, text=text, tags=tags,
                             values=(", ".join(p.genres[:2]), human(p.size), self._state(p)[0]))
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
        t.insert("end", p.desc.strip() + "\n\n")
        if p.porter:
            t.insert("end", _("Porté par : {names}", names=", ".join(p.porter)) + "\n", "muted")
        if p.updated:
            t.insert("end", _("Mis à jour le {date}", date=p.updated) + "\n", "muted")
        t.configure(state="disabled")
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
