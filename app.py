"""Interface graphique rétro : gestionnaire de jeux R36S / ArkOS (partition EASYROMS)."""
import datetime
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

import cleanup
import core
import filters
import icons
import journal
import logos
import paths
import regions
import scraper
import systems
import theme as T
import video
from tools_actions import ToolsMixin
from widgets import (CleanupDialog, GameGrid, HPBar, PixelButton, ProgressDialog, RetroCheck, Tooltip, ask_delete,
                     human, info)

ALL = "__all__"
FAV = "__fav__"
DUP = "__dup__"
DETAIL_IMG = (340, 255)
VIDEO_DELAY = 3000  # ms de sélection avant de lancer la vidéo du jeu
SORTS = {
    "Nom A → Z": (lambda g: g.name.lower(), False),
    "Nom Z → A": (lambda g: g.name.lower(), True),
    "Mieux notés": (lambda g: (g.rating if g.rating is not None else -1, g.name.lower()), True),
    "Plus joués": (lambda g: (g.playcount, g.name.lower()), True),
    "Derniers joués": (lambda g: (g.lastplayed or datetime.datetime.min, g.name.lower()), True),
    "Plus gros": (lambda g: g.size, True),
    "Plus petits": (lambda g: g.size, False),
    "Système": (lambda g: (systems.name(g.system).lower(), g.name.lower()), False),
}
# Légende de la jauge de la carte : (clé, libellé, couleur)
USAGE = (("games", "Jeux", T.CYAN), ("images", "Images", T.MAGENTA), ("videos", "Vidéos", T.YELLOW),
         ("trash", "Corbeille", T.ORANGE))
OTHER_COLOR = "#5a5480"  # le reste (bios, thèmes, système…)
HINTS = ("Clic : sélectionner   ·   Ctrl/Maj + clic : sélection multiple   ·   F ou ★ : favori   ·   "
         "Suppr : supprimer   ·   Double-clic : ouvrir le dossier   ·   Ctrl+F : rechercher")


MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def played_text(count):
    return "Jamais joué" if not count else f"{count} fois"


def last_played_text(when):
    """« 12 sept. 2025 · il y a 3 mois » (vide si jamais joué)."""
    if not when:
        return ""
    days = (datetime.datetime.now() - when).days
    if days < 1:
        ago = "aujourd'hui"
    elif days < 2:
        ago = "hier"
    elif days < 31:
        ago = f"il y a {days} jours"
    elif days < 365:
        ago = f"il y a {days // 30} mois"
    else:
        ago = f"il y a {days // 365} an{'s' if days >= 730 else ''}"
    return f"{when.day} {MONTHS[when.month - 1]} {when.year}  ·  {ago}"


def stars_text(rating):
    """Note sur 5 pour la vue liste, ex. 3.5 → « 3.5 / 5 »."""
    if rating is None:
        return ""
    return f"{round(rating * 10) / 2:g} / 5"


try:  # glisser-déposer de fichiers depuis l'Explorateur (optionnel)
    from tkinterdnd2 import DND_FILES, TkinterDnD
    BaseTk = TkinterDnD.Tk
except ImportError:
    DND_FILES, BaseTk = None, tk.Tk


class App(ToolsMixin, BaseTk):
    def __init__(self):
        T.load_fonts()
        super().__init__()
        T.apply(self)
        self.title("R36S Game Manager")
        self.geometry("1440x860")
        try:
            self.state("zoomed")              # Windows
        except tk.TclError:
            self.attributes("-zoomed", True)  # Linux
        self.minsize(1100, 620)
        self.iconphoto(True, icons.icon("gamepad", T.CYAN, 4))
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

        self.root_path = None
        self.games = {}          # système -> [Game]
        self.current = ALL       # système affiché
        self.shown = []          # jeux affichés (filtrés et triés)
        self.selection = []      # jeux sélectionnés
        self.drive_map = {}      # libellé -> racine du lecteur
        self.view = "grid"
        self._syncing = False
        self._photo = None
        self._flash_job = None

        self._build_header()
        T.neon_line(self)
        self._build_footer()
        body = tk.PanedWindow(self, orient="horizontal", bg=T.BG, sashwidth=6, bd=0)
        body.pack(fill="both", expand=True)
        body.add(self._build_sidebar(body), minsize=240, width=330)
        body.add(self._build_center(body), minsize=520, stretch="always")
        body.add(self._build_details(body), minsize=340, width=390)
        self._bind_keys()
        self.set_view("grid")
        self.set_selection([])
        self.refresh_drives()

    # ================================================================ construction
    def _build_header(self):
        bar = tk.Frame(self, bg=T.PANEL, padx=18, pady=12)
        bar.pack(fill="x")
        tk.Label(bar, image=icons.icon("gamepad", T.CYAN, 3), bg=T.PANEL).pack(side="left")
        logo = tk.Frame(bar, bg=T.PANEL)
        logo.pack(side="left", padx=(12, 34))
        tk.Label(logo, text="R36S", font=T.F["logo"], fg=T.CYAN, bg=T.PANEL).pack(anchor="w")
        tk.Label(logo, text="GAME MANAGER", font=T.F["tiny"], fg=T.MAGENTA,
                 bg=T.PANEL).pack(anchor="w", pady=(5, 0))

        tk.Label(bar, image=icons.icon("sd", T.YELLOW, 2), bg=T.PANEL).pack(side="left")
        self.drive_var = tk.StringVar()
        self.drive_cb = ttk.Combobox(bar, textvariable=self.drive_var, state="readonly",
                                     width=20, font=T.F["body"])
        self.drive_cb.pack(side="left", padx=8)
        self.drive_cb.bind("<<ComboboxSelected>>", lambda e: self.load_drive())
        refresh = PixelButton(bar, icon="refresh", command=self.reload)
        refresh.pack(side="left")
        Tooltip(refresh, "Relire la carte (F5)")
        self.btn_undo = PixelButton(bar, icon="undo", command=self.undo_last)
        self.btn_undo.pack(side="left", padx=(6, 0))
        self.undo_tip = Tooltip(self.btn_undo, "Rien à annuler")
        self.btn_undo.set_enabled(False)
        broom = PixelButton(bar, icon="broom", command=self.cleanup)
        broom.pack(side="left", padx=6)
        Tooltip(broom, "Nettoyer la carte : médias orphelins, fiches sans jeu, jeux mal rangés…")
        add = PixelButton(bar, icon="plus", command=self.add_games)
        add.pack(side="left")
        Tooltip(add, "Ajouter des jeux depuis le PC (ou glisse-les dans la fenêtre)")
        tools = PixelButton(bar, "OUTILS", icon="menu", command=lambda: self.show_tools_menu(tools))
        tools.pack(side="left", padx=6)

        box = tk.Frame(bar, bg=T.PANEL2, highlightthickness=2, highlightbackground=T.BORDER)
        box.pack(side="left", padx=34)
        tk.Label(box, image=icons.icon("search", T.CYAN, 2), bg=T.PANEL2).pack(side="left", padx=(12, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.fill_games())
        self.search = tk.Entry(box, textvariable=self.search_var, bg=T.PANEL2, fg=T.TEXT, bd=0,
                               insertbackground=T.CYAN, relief="flat", font=T.F["big"], width=24)
        self.search.pack(side="left", pady=6)
        self.search.bind("<FocusIn>", lambda e: box.configure(highlightbackground=T.CYAN))
        self.search.bind("<FocusOut>", lambda e: box.configure(highlightbackground=T.BORDER))
        clear = tk.Label(box, image=icons.icon("close", T.MUTED, 2), bg=T.PANEL2, cursor="hand2")
        clear.pack(side="left", padx=12)
        clear.bind("<Button-1>", lambda e: self.search_var.set(""))

        hp = tk.Frame(bar, bg=T.PANEL)
        hp.pack(side="right")
        top = tk.Frame(hp, bg=T.PANEL)
        top.pack(fill="x")
        tk.Label(top, text="CARTE SD", font=T.F["tiny"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
        self.space_lbl = tk.Label(top, font=T.F["small"], fg=T.TEXT, bg=T.PANEL)
        self.space_lbl.pack(side="right")
        self.hp = HPBar(hp)
        self.hp.pack(anchor="e", pady=5)
        legend = tk.Frame(hp, bg=T.PANEL)
        legend.pack(anchor="e")
        self.usage = {}  # catégorie -> octets ; None tant que le calcul n'est pas fini
        self.usage_lbl = {}
        for key, label, color in USAGE:
            tk.Label(legend, text="■", font=T.F["small"], fg=color, bg=T.PANEL).pack(side="left", padx=(12, 3))
            tk.Label(legend, text=label, font=T.F["small"], fg=T.MUTED, bg=T.PANEL).pack(side="left")
            self.usage_lbl[key] = tk.Label(legend, text="…", font=T.F["small"], fg=T.TEXT, bg=T.PANEL)
            self.usage_lbl[key].pack(side="left", padx=(5, 0))

    def _build_footer(self):
        bar = tk.Frame(self, bg=T.PANEL, padx=18, pady=10)
        bar.pack(side="bottom", fill="x")
        tk.Frame(self, bg=T.BORDER, height=2).pack(side="bottom", fill="x")
        self.status = tk.Label(bar, font=T.F["small"], fg=T.MUTED, bg=T.PANEL, anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.btn_delete = PixelButton(bar, "SUPPRIMER", icon="trash", style="danger",
                                      command=self.delete_selected)
        self.btn_delete.pack(side="right")
        self.btn_open = PixelButton(bar, "DOSSIER", icon="folder", command=self.open_folder)
        self.btn_open.pack(side="right", padx=12)
        self.btn_fav = PixelButton(bar, "FAVORI", icon="star", style="fav",
                                   command=lambda: self.toggle_favorites(None))
        self.btn_fav.pack(side="right")
        self.saves_var = tk.BooleanVar(value=False)
        RetroCheck(bar, "Supprimer aussi les sauvegardes", self.saves_var,
                   command=self.show_details).pack(side="right", padx=16)

    def _build_sidebar(self, master):
        f = tk.Frame(master, bg=T.BG)
        tk.Label(f, text=T.px("Systèmes"), font=T.F["h2"], fg=T.MUTED, bg=T.BG,
                 anchor="w").pack(fill="x", padx=18, pady=(18, 10))
        wrap = tk.Frame(f, bg=T.BG)
        wrap.pack(fill="both", expand=True, padx=(8, 0), pady=(0, 8))
        t = ttk.Treeview(wrap, style="Side.Treeview", show="tree", columns=("n",), selectmode="browse")
        t.column("#0", width=250, stretch=True)
        t.column("n", width=52, anchor="e", stretch=False)
        sb = ttk.Scrollbar(wrap, orient="vertical", style=T.SCROLL, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.bind("<<TreeviewSelect>>", lambda e: self.on_system())
        self.sys_tree = t
        return f

    def _build_center(self, master):
        f = tk.Frame(master, bg=T.BG)
        top = tk.Frame(f, bg=T.BG)
        top.pack(fill="x", padx=16, pady=(14, 12))
        self.sys_icon = tk.Label(top, bg=T.BG)
        self.sys_icon.pack(side="left")
        titles = tk.Frame(top, bg=T.BG)
        titles.pack(side="left", padx=14)
        self.sys_title = tk.Label(titles, font=T.F["h1"], fg=T.TEXT, bg=T.BG, anchor="w")
        self.sys_title.pack(anchor="w")
        self.count_lbl = tk.Label(titles, font=T.F["small"], fg=T.MUTED, bg=T.BG, anchor="w")
        self.count_lbl.pack(anchor="w", pady=(6, 0))

        self.btn_list = PixelButton(top, icon="list", style="toggle", command=lambda: self.set_view("list"))
        self.btn_list.pack(side="right")
        self.btn_grid = PixelButton(top, icon="grid", style="toggle", command=lambda: self.set_view("grid"))
        self.btn_grid.pack(side="right", padx=6)
        self.btn_filters = PixelButton(top, "FILTRES", icon="filter", style="toggle",
                                       command=self.toggle_filter_bar)
        self.btn_filters.pack(side="right", padx=(0, 10))
        self.btn_images = PixelButton(top, "IMAGES", icon="download", command=self.download_images)
        self.btn_images.pack(side="right", padx=(0, 14))
        Tooltip(self.btn_images, "Télécharger depuis internet les images des jeux affichés qui n'en ont pas")
        self.sort_var = tk.StringVar(value=next(iter(SORTS)))
        sort = ttk.Combobox(top, textvariable=self.sort_var, values=list(SORTS), state="readonly",
                            width=11, font=T.F["body"])
        sort.pack(side="right", padx=(8, 18))
        sort.bind("<<ComboboxSelected>>", lambda e: self.fill_games())

        self._build_filter_bar(f)
        self.content = tk.Frame(f, bg=T.BG)
        self.content.pack(fill="both", expand=True, padx=(10, 0))
        self.grid_view = GameGrid(self.content, self.set_selection, self.open_folder,
                                  self.delete_selected, self.toggle_favorites, self.show_context_menu)
        self.list_view = self._build_list(self.content)
        return f

    def _build_filter_bar(self, master):
        """Panneau repliable : genre, joueurs, région, jamais joué, sans image, sans note."""
        self.filters = dict(filters.EMPTY)
        bar = tk.Frame(master, bg=T.PANEL2, padx=14, pady=10)
        self.filter_bar = bar
        row1 = tk.Frame(bar, bg=T.PANEL2)
        row1.pack(fill="x")
        self.filter_combos = {}
        for key, label, width in (("genre", "GENRE", 24), ("players", "JOUEURS", 15), ("region", "RÉGION", 14)):
            tk.Label(row1, text=label, font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL2).pack(side="left", padx=(0, 6))
            combo = ttk.Combobox(row1, state="readonly", width=width, font=T.F["body"])
            combo.pack(side="left", padx=(0, 18))
            combo.bind("<<ComboboxSelected>>", lambda e: self._read_filters())
            self.filter_combos[key] = combo
        row2 = tk.Frame(bar, bg=T.PANEL2)
        row2.pack(fill="x", pady=(10, 0))
        self.filter_checks = {}
        for key, label in (("never", "Jamais joué"), ("noimage", "Sans image"), ("norating", "Sans note")):
            var = tk.BooleanVar(value=False)
            check = RetroCheck(row2, label, var, command=self._read_filters, bg=T.PANEL2)
            check.pack(side="left", padx=(0, 22))
            self.filter_checks[key] = (var, check)
        clear = tk.Label(row2, text="Effacer les filtres", font=T.F["small"], fg=T.CYAN, bg=T.PANEL2, cursor="hand2")
        clear.pack(side="right")
        clear.bind("<Button-1>", lambda e: self.clear_filters())

    def refresh_filter_choices(self):
        """Remplit les listes (genres et régions présents sur la carte)."""
        games = [g for lst in self.games.values() for g in lst]
        self._genre_labels = {"Tous": ""}
        self._genre_labels.update({f"{name}  ({n})": name for name, n in filters.genres(games)})
        self._region_labels = {"Toutes": ""}
        self._region_labels.update({regions.REGIONS[c]: c for c in filters.region_codes(games)})
        for key, labels in (("genre", self._genre_labels), ("players", filters.PLAYERS),
                            ("region", self._region_labels)):
            combo = self.filter_combos[key]
            combo["values"] = list(labels)
            current = next((lab for lab, v in labels.items() if v == self.filters[key]), None)
            combo.set(current or next(iter(labels)))

    def _read_filters(self):
        self.filters["genre"] = self._genre_labels.get(self.filter_combos["genre"].get(), "")
        self.filters["players"] = filters.PLAYERS.get(self.filter_combos["players"].get(), 0)
        self.filters["region"] = self._region_labels.get(self.filter_combos["region"].get(), "")
        for key, (var, _) in self.filter_checks.items():
            self.filters[key] = var.get()
        self.fill_games()

    def clear_filters(self):
        self.filters = dict(filters.EMPTY)
        for var, check in self.filter_checks.values():
            var.set(False)
            check._paint()
        self.refresh_filter_choices()
        self.fill_games()

    def toggle_filter_bar(self):
        if self.filter_bar.winfo_ismapped():
            self.filter_bar.pack_forget()
        else:
            self.filter_bar.pack(fill="x", padx=(10, 0), pady=(0, 10), before=self.content)
        self.btn_filters.set_active(self.filter_bar.winfo_ismapped() or bool(filters.active_count(self.filters)))

    def _build_list(self, master):
        frame = tk.Frame(master, bg=T.PANEL)
        cols = (("fav", "★", 40, "center"), ("rating", "NOTE", 70, "w"), ("system", T.px("Système"), 120, "w"),
                ("file", "FICHIER", 150, "w"), ("size", "TAILLE", 90, "e"))
        t = ttk.Treeview(frame, columns=[c[0] for c in cols], show="tree headings", selectmode="extended")
        t.heading("#0", text="NOM", anchor="w", command=lambda: self.sort_heading("name"))
        t.column("#0", width=230, stretch=True)
        for key, text, width, anchor in cols:
            t.heading(key, text=text, anchor=anchor,
                      command=(lambda k=key: self.sort_heading(k)) if key != "fav" else "")
            t.column(key, width=width, anchor=anchor, stretch=key == "file")
        sb = ttk.Scrollbar(frame, orient="vertical", style=T.SCROLL, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        t.tag_configure("nogl", foreground=T.YELLOW)
        t.bind("<<TreeviewSelect>>", lambda e: self.on_list_select())
        t.bind("<Delete>", lambda e: self.delete_selected())
        t.bind("<Double-1>", lambda e: self.open_folder())
        t.bind("<Return>", lambda e: self.open_folder())
        t.bind("<f>", lambda e: self.toggle_favorites(None))
        t.bind("<Button-3>", self._list_context)
        self.tree = t
        return frame

    def _build_details(self, master):
        """Panneau de droite. Il défile d'un seul bloc (image, infos et description) :
        la description prend la hauteur de son texte au lieu d'avoir sa propre petite zone."""
        outer = tk.Frame(master, bg=T.PANEL)
        canvas = tk.Canvas(outer, bg=T.PANEL, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(outer, orient="vertical", style=T.SCROLL, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        f = tk.Frame(canvas, bg=T.PANEL, padx=20, pady=18)
        window = canvas.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        self.details_canvas = canvas

        def wheel(event):
            if canvas.yview() != (0.0, 1.0):  # rien à faire si tout tient à l'écran
                canvas.yview_scroll(int(-event.delta / 120) * 3, "units")
            return "break"
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self.img_frame = tk.Frame(f, bg=T.BORDER, padx=3, pady=3)
        self.img_frame.pack(anchor="w")
        self.img_lbl = tk.Label(self.img_frame, bg=T.BG, width=DETAIL_IMG[0], height=DETAIL_IMG[1])
        self.img_lbl.pack()
        # aperçu vidéo (VLC) par-dessus l'image, + bouton du son
        self.video_muted, self._video_job = False, None
        self.video = video.VideoPreview(self.img_frame, self.img_lbl, on_click=self.toggle_video_sound)
        self.sound_btn = tk.Label(self.img_frame, bg=T.BG, cursor="hand2", padx=4, pady=3)
        self.sound_btn.bind("<Button-1>", lambda e: self.toggle_video_sound())
        self.title_lbl = tk.Label(f, font=T.F["h1"], fg=T.TEXT, bg=T.PANEL, justify="left", anchor="w")
        self.title_lbl.pack(fill="x", pady=(16, 8))
        row = tk.Frame(f, bg=T.PANEL)
        row.pack(fill="x")
        self.chip = tk.Label(row, font=T.F["tiny"], bg=T.PANEL, compound="left", anchor="w")
        self.chip.pack(side="left")
        self.detail_edit = PixelButton(row, icon="edit", command=self.edit_selected)
        Tooltip(self.detail_edit, "Modifier la fiche (F2)")
        self.detail_fav = PixelButton(row, "FAVORI", icon="star", style="fav",
                                      command=lambda: self.toggle_favorites(None))
        self.meta = tk.Frame(f, bg=T.PANEL)
        self.meta.pack(fill="x", pady=(10, 6))

        self.desc = tk.Text(f, wrap="word", bg=T.PANEL, fg=T.TEXT, font=T.F["small"], relief="flat", height=1,
                            highlightthickness=0, bd=0, cursor="arrow", spacing2=2, state="disabled")
        self.desc.pack(fill="x")
        self.desc.bind("<Configure>", lambda e: self._fit_desc())  # largeur changée : on recalcule
        self.desc.tag_configure("head", foreground=T.YELLOW, font=T.F["tiny"], spacing1=16, spacing3=8)
        self.desc.tag_configure("file", foreground=T.MUTED)
        self.desc.tag_configure("warn", foreground=T.YELLOW)
        canvas.bind("<Configure>", lambda e: self.title_lbl.configure(wraplength=max(200, e.width - 44)), add="+")
        return outer

    def _bind_keys(self):
        self.bind("<Control-f>", lambda e: (self.search.focus_set(), self.search.select_range(0, "end")))
        self.bind("<F5>", lambda e: self.reload())
        self.bind("<F2>", lambda e: self.edit_selected())
        if DND_FILES:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.on_drop)
        self.search.bind("<Escape>", lambda e: self.search_var.set(""))
        self.search.bind("<Down>", lambda e: self.focus_games())
        self.search.bind("<Return>", lambda e: self.focus_games())

    # ================================================================ lecteurs
    def refresh_drives(self):
        previous = self.drive_var.get()
        self.drive_map.clear()
        default = None
        for root, label, easy in core.list_drives():
            text = f"{root[:2]}  {label}" + ("  ★" if easy else "")
            self.drive_map[text] = root
            if easy and default is None:
                default = text
        self.drive_cb["values"] = list(self.drive_map)
        if previous in self.drive_map:
            return
        self.drive_var.set(default or "")
        if default:
            self.load_drive()

    def reload(self):
        self.refresh_drives()
        self.load_drive()

    def load_drive(self):
        root = self.drive_map.get(self.drive_var.get())
        if not root:
            return
        self.root_path = root
        self.flash(f"Lecture de {root[:2]} …", T.YELLOW, keep=True)
        self.config(cursor="watch")
        result = {}

        def work():
            try:
                logos.import_from_card(root, core.list_systems(root))
                result["data"] = core.load_all(root)
            except Exception as e:  # affiché à l'utilisateur
                result["err"] = e

        thread = threading.Thread(target=work, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(100, poll)
                return
            self.config(cursor="")
            if "err" in result:
                info(self, "Erreur", f"Impossible de lire {root} :", str(result["err"]))
                return
            logos.reset()
            self.games = result["data"]
            self.selection = []
            self.refresh_history()
            self.usage.clear()
            self.refresh_usage()
            self.fill_systems(ALL)
            total = sum(len(v) for v in self.games.values())
            self.flash(f"{total} jeux chargés depuis {root[:2]}", T.GREEN)
            if not self.games:
                info(self, "Aucun jeu", f"Aucun jeu trouvé sur {root[:2]}.\n"
                                        "Est-ce bien la partition EASYROMS ?")

        poll()

    def refresh_usage(self):
        """Recalcule en arrière-plan la place des images et vidéos (parcours de la carte)."""
        root, result = self.root_path, {}
        if not root:
            return
        def measure():
            result.update(core.media_usage(root))
            result["trash"] = journal.trash_size(root)
        thread = threading.Thread(target=measure, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(200, poll)
            elif root == self.root_path:
                self.usage.update(result)
                self.update_space()

        poll()

    def update_space(self):
        u = core.disk_usage(self.root_path) if self.root_path else None
        if not (u and u.total):
            return
        self.usage["games"] = sum(g.size for lst in self.games.values() for g in lst)
        parts, known = [], 0
        for key, _, color in USAGE:
            size = self.usage.get(key)
            self.usage_lbl[key].configure(text=human(size) if size is not None else "…")
            if size:
                parts.append((size / u.total, color))
                known += size
        parts.append((max(u.used - known, 0) / u.total, OTHER_COLOR))
        self.hp.set_parts(parts)
        self.space_lbl.configure(text=f"{human(u.free)} libres / {human(u.total)}")

    # ================================================================ listes
    def fill_systems(self, keep):
        t = self.sys_tree
        t.delete(*t.get_children())
        total = sum(len(v) for v in self.games.values())
        t.insert("", "end", iid=ALL, text="  Tous les jeux", values=(total,),
                 image=icons.boxed("gamepad", T.CYAN, 2, 78, 30))
        t.insert("", "end", iid=FAV, text="  Favoris", values=(len(self.favorites()),),
                 image=icons.boxed("star", T.YELLOW, 2, 78, 30))
        t.insert("", "end", iid=DUP, text="  Doublons", values=(len(core.find_duplicates(self.games)),),
                 image=icons.boxed("copy", T.ORANGE, 2, 78, 30))
        for s in sorted(self.games, key=lambda k: systems.name(k).lower()):
            t.insert("", "end", iid=s, text="  " + systems.name(s), values=(len(self.games[s]),),
                     image=logos.get(s, 78, 30, align="center"))
        self.current = keep if keep in self.games or keep in (FAV, DUP) else ALL
        self.refresh_filter_choices()
        t.selection_set(self.current)
        t.see(self.current)
        self.update_space()
        self.fill_games()

    def on_system(self):
        sel = self.sys_tree.selection()
        if sel and sel[0] != self.current:
            self.current = sel[0]
            self.fill_games()

    def favorites(self):
        return [g for lst in self.games.values() for g in lst if g.favorite]

    def fill_games(self, keep_scroll=False):
        if self.current == ALL:
            games = [g for lst in self.games.values() for g in lst]
        elif self.current == FAV:
            games = self.favorites()
        elif self.current == DUP:
            games = core.find_duplicates(self.games)
        else:
            games = list(self.games.get(self.current, []))
        query = self.search_var.get().strip()
        words = query.lower().split()
        if words:
            games = [g for g in games if all(w in f"{g.name} {g.filename}".lower() for w in words)]
        games = filters.apply(games, self.filters)
        key, reverse = SORTS[self.sort_var.get()]
        games.sort(key=key, reverse=reverse)
        if self.current == DUP:  # les copies d'un même jeu côte à côte
            games.sort(key=lambda g: (g.system, core.title_key(g.stem)))
        self.shown = games
        ids = {id(g) for g in games}
        self.selection = [g for g in self.selection if id(g) in ids]

        if self.current not in (ALL, FAV, DUP) and logos.has(self.current):
            self.sys_icon.configure(image=logos.get(self.current, 220, 44))
            self.sys_title.pack_forget()
        else:
            if self.current == ALL:
                self.sys_icon.configure(image=icons.icon("gamepad", T.CYAN, 3))
                self.sys_title.configure(text="TOUS LES JEUX")
            elif self.current == FAV:
                self.sys_icon.configure(image=icons.icon("star", T.YELLOW, 3))
                self.sys_title.configure(text="FAVORIS")
            elif self.current == DUP:
                self.sys_icon.configure(image=icons.icon("copy", T.ORANGE, 3))
                self.sys_title.configure(text="DOUBLONS")
            else:
                self.sys_icon.configure(image=icons.icon(systems.kind(self.current), systems.color(self.current), 3))
                self.sys_title.configure(text=T.px(systems.name(self.current)))
            self.sys_title.pack(anchor="w", before=self.count_lbl)
        count = f"{len(games)} jeu{'x' if len(games) > 1 else ''}  ·  {human(sum(g.size for g in games))}"
        active = filters.active_count(self.filters)
        self.count_lbl.configure(text=count + (f"  ·  recherche « {query} »" if query else "")
                                 + (f"  ·  {active} filtre{'s' if active > 1 else ''}" if active else ""))
        self.btn_filters.set_text(f"FILTRES ({active})" if active else "FILTRES")
        self.btn_filters.set_active(bool(active) or self.filter_bar.winfo_ismapped())
        self.render_view(keep_scroll)
        self.set_selection(self.selection)
        missing = len(scraper.missing_images(self.shown))
        self.btn_images.set_text(f"IMAGES ({missing})" if missing else "IMAGES OK")
        self.btn_images.set_enabled(missing > 0)

    def render_view(self, keep_scroll=False):
        if self.view == "grid":
            self.grid_view.set_games(self.shown, self.selection, keep_scroll)
            return
        t = self.tree
        self._syncing = True
        top = t.yview()[0]
        t.delete(*t.get_children())
        selected = {id(g) for g in self.selection}
        for i, g in enumerate(self.shown):
            t.insert("", "end", iid=str(i), text="  " + g.name,
                     image=logos.get(g.system, 84, 24, align="center"),
                     values=("★" if g.favorite else "", stars_text(g.rating), systems.name(g.system),
                             g.filename, human(g.size)),
                     tags=() if g.in_gamelist else ("nogl",))
        t.selection_set([str(i) for i, g in enumerate(self.shown) if id(g) in selected])
        if keep_scroll:
            t.yview_moveto(top)
        self.after_idle(lambda: setattr(self, "_syncing", False))

    def set_view(self, view):
        self.view = view
        self.btn_grid.set_active(view == "grid")
        self.btn_list.set_active(view == "list")
        self.grid_view.pack_forget()
        self.list_view.pack_forget()
        (self.grid_view if view == "grid" else self.list_view).pack(fill="both", expand=True)
        self.render_view()

    def focus_games(self):
        if self.view == "grid":
            self.grid_view.canvas.focus_set()
        else:
            self.tree.focus_set()

    def sort_heading(self, column):
        options = {"name": ("Nom A → Z", "Nom Z → A"), "file": ("Nom A → Z", "Nom Z → A"),
                   "rating": ("Mieux notés", "Mieux notés"),
                   "size": ("Plus gros", "Plus petits"), "system": ("Système", "Système")}[column]
        current = self.sort_var.get()
        self.sort_var.set(options[1] if current == options[0] else options[0])
        self.fill_games()

    def _list_context(self, event):
        """Clic droit en vue liste : sélectionne la ligne si besoin puis ouvre le menu."""
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection():
            self.tree.selection_set(row)
            self.set_selection([self.shown[int(row)]])
        self.show_context_menu(event)

    def on_list_select(self):
        if not self._syncing:
            self.set_selection([self.shown[int(i)] for i in self.tree.selection()])

    def set_selection(self, games):
        self.selection = list(games)
        n = len(self.selection)
        self.btn_delete.set_text(f"SUPPRIMER ({n})" if n > 1 else "SUPPRIMER")
        self.btn_delete.set_enabled(n > 0)
        self.btn_open.set_enabled(n == 1)
        self.btn_fav.set_enabled(n > 0)
        all_fav = n > 0 and all(g.favorite for g in self.selection)
        self.btn_fav.set_text("RETIRER DES FAVORIS" if all_fav else "AJOUTER AUX FAVORIS")
        if not self._flash_job:
            self.update_status()
        self.show_details()

    # ================================================================ détails
    def update_status(self):
        if self.selection:
            n = len(self.selection)
            size = human(sum(g.size for g in self.selection))
            self.status.configure(text=f"{n} jeu{'x' if n > 1 else ''} sélectionné{'s' if n > 1 else ''}"
                                       f"  ·  {size}", fg=T.CYAN)
        else:
            self.status.configure(text=HINTS, fg=T.MUTED)

    def flash(self, text, color, keep=False):
        """Message temporaire dans la barre d'état."""
        if self._flash_job:
            self.after_cancel(self._flash_job)
            self._flash_job = None
        self.status.configure(text=text, fg=color)
        if not keep:
            def done():
                self._flash_job = None
                self.update_status()
            self._flash_job = self.after(5000, done)

    def _write_desc(self, parts):
        self.desc.configure(state="normal")
        self.desc.delete("1.0", "end")
        for text, tag in parts:
            self.desc.insert("end", text, tag)
        self.desc.configure(state="disabled")
        self._fit_desc()
        self.details_canvas.yview_moveto(0)

    def _fit_desc(self):
        """Donne à la description la hauteur de tout son texte (le panneau entier défile)."""
        self.desc.update_idletasks()
        lines = self.desc.count("1.0", "end", "displaylines")
        lines = lines[0] if isinstance(lines, tuple) else lines
        if lines and int(self.desc.cget("height")) != lines:
            self.desc.configure(height=lines)

    def _set_image(self, path, fallback, border):
        self._photo = None
        if path:
            try:
                with Image.open(path) as im:
                    im = im.convert("RGBA")
                    im.thumbnail(DETAIL_IMG)
                    self._photo = ImageTk.PhotoImage(im)
            except OSError:
                self._photo = None
        self.img_lbl.configure(image=self._photo or fallback)
        self.img_frame.configure(bg=border)

    def _set_meta(self, rows):
        for w in self.meta.winfo_children():
            w.destroy()
        for r, (label, value) in enumerate((k, v) for k, v in rows if v):
            tk.Label(self.meta, text=label, font=T.F["tiny"], fg=T.MAGENTA, bg=T.PANEL,
                     anchor="w").grid(row=r, column=0, sticky="w", pady=3)
            image, text = value if isinstance(value, tuple) else ("", value)  # (image, texte)
            tk.Label(self.meta, text=text, image=image, compound="left", font=T.F["small"], fg=T.TEXT,
                     bg=T.PANEL, anchor="w", justify="left",
                     wraplength=280).grid(row=r, column=1, sticky="w", padx=(14, 0))

    # ---------------------------------------------------------------- vidéo
    def _stop_video(self):
        if self._video_job:
            self.after_cancel(self._video_job)
            self._video_job = None
        self.video.stop()
        self.sound_btn.place_forget()

    def _schedule_video(self, game):
        """Lance la vidéo du jeu si la sélection n'a pas changé au bout de VIDEO_DELAY."""
        path = core.video_for(game) if video.available() else None
        if path:
            self._video_job = self.after(VIDEO_DELAY, lambda: self._start_video(game, path))

    def _start_video(self, game, path):
        self._video_job = None
        if self.selection == [game] and os.path.isfile(path):
            self.video.play(path, self.video_muted)
            self._paint_sound()
            self.sound_btn.place(in_=self.img_lbl, relx=1, rely=1, x=-6, y=-6, anchor="se")
            self.sound_btn.lift()

    def toggle_video_sound(self):
        self.video_muted = not self.video_muted
        self.video.set_muted(self.video_muted)
        self._paint_sound()

    def _paint_sound(self):
        self.sound_btn.configure(image=icons.icon("sound_off" if self.video_muted else "sound_on",
                                                  T.MUTED if self.video_muted else T.CYAN, 2))

    def quit_app(self):
        self.video.release()
        self.destroy()

    def show_details(self):
        self._stop_video()
        sel = self.selection
        if len(sel) == 1:
            self._schedule_video(sel[0])
        if len(sel) == 1:
            self.detail_fav.set_text("DANS LES FAVORIS" if sel[0].favorite else "AJOUTER AUX FAVORIS")
            self.detail_fav.set_active(sel[0].favorite)
            self.detail_fav.pack(side="right")
            self.detail_edit.pack(side="right", padx=8)
        else:
            self.detail_fav.pack_forget()
            self.detail_edit.pack_forget()
        if len(sel) != 1:
            self.chip.configure(text="", image="")
            if sel:
                self._set_image(None, icons.icon("trash", T.RED, 10), T.RED)
                self.title_lbl.configure(text=T.px(f"{len(sel)} jeux sélectionnés"))
                self._set_meta([("TAILLE", human(sum(g.size for g in sel)))])
                self._write_desc([("".join(f"> {g.name}\n" for g in sel), "file")])
            else:
                self._set_image(None, icons.icon("gamepad", T.BORDER, 12), T.BORDER)
                self.title_lbl.configure(text=T.px("Sélectionne un jeu"))
                self._set_meta([])
                self._write_desc([("ASTUCES\n", "head"), (HINTS.replace("   ·   ", "\n"), "file")])
            return

        g = sel[0]
        color = systems.color(g.system)
        self._set_image(core.image_for(g), icons.icon(systems.kind(g.system), color, 10), color)
        self.title_lbl.configure(text=T.px(g.name))
        if logos.has(g.system):
            self.chip.configure(text="", image=logos.get(g.system, 200, 30))
        else:
            self.chip.configure(text="  " + T.px(systems.name(g.system)), fg=color,
                                image=icons.icon(systems.kind(g.system), color, 2))
        i = g.info
        note = (icons.stars(g.rating, 2), "   " + stars_text(g.rating)) if g.rating is not None else None
        codes, region_text, langs = regions.describe(g.stem)
        flags = icons.flags(codes)
        region = (flags, "  " + region_text) if flags else region_text
        self._set_meta([("NOTE", note), ("VERSION", region), ("LANGUES", langs),
                        ("PARTIES", played_text(g.playcount)), ("DERNIÈRE", last_played_text(g.lastplayed)),
                        ("ANNÉE", i.get("releasedate", "")[:4]), ("DÉV.", i.get("developer")),
                        ("ÉDITEUR", i.get("publisher")), ("GENRE", i.get("genre")),
                        ("JOUEURS", i.get("players")), ("TAILLE", human(g.size))])
        files = core.files_to_delete(g, self.games.get(g.system, []), self.saves_var.get())
        parts = []
        if not g.in_gamelist:
            parts.append(("Ce jeu n'est pas dans le gamelist.xml (pas de fiche).\n", "warn"))
        if i.get("desc"):
            parts.append((i["desc"] + "\n", None))
        parts.append((T.px("Fichiers supprimés avec ce jeu") + "\n", "head"))
        parts += [(f"> {os.path.relpath(p, g.sysdir)}\n", "file") for p in files]
        self._write_desc(parts)

    # ================================================================ actions
    def run_in_background(self, title, icon, total, work, on_done, label=None):
        """Exécute work(report, cancel) dans un thread, avec une fenêtre de chargement, pour que
        l'application ne se fige jamais. work appelle report(fait, texte) pour avancer la barre
        (total=None : barre animée sans fin connue). on_done(résultat) est appelé ensuite.
        label : si l'opération modifie la carte, son nom dans l'historique (elle devient annulable)."""
        self._stop_video()  # une vidéo en lecture est verrouillée par Windows
        cancel, updates, box = threading.Event(), queue.Queue(), {}
        dlg = ProgressDialog(self, title, cancel.set, icon)
        root = self.root_path

        def report(done, text):
            updates.put((done, text))

        def runner():
            try:
                if label:
                    with journal.operation(root, label):
                        box["result"] = work(report, cancel)
                else:
                    box["result"] = work(report, cancel)
            except Exception as e:  # affiché à l'utilisateur au lieu de planter
                box["error"] = e

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()

        def poll():
            latest = None
            while not updates.empty():
                latest = updates.get_nowait()
            if latest:
                done, text = latest
                dlg.set(done, total, text, f"{done} / {total}" if total else "")
            elif total is None:
                dlg.pulse()
            if thread.is_alive():
                self.after(80, poll)
                return
            dlg.destroy()
            if label:
                self.refresh_history()
            if "error" in box:
                info(self, "Erreur", "L'opération a échoué :", str(box["error"]))
            else:
                on_done(box.get("result"))

        dlg.set(0, total or 1, "Préparation…")
        poll()

    def _forget_games(self, games):
        """Retire de la liste les jeux dont la ROM n'existe plus."""
        for g in games:
            if not os.path.exists(g.path) and g in self.games.get(g.system, []):
                self.games[g.system].remove(g)
                if not self.games[g.system]:
                    del self.games[g.system]
        self.selection = []
        self.fill_systems(self.current)
        self.refresh_usage()

    def cleanup(self):
        """Cherche les fichiers obsolètes / incohérents et propose de les supprimer."""
        if not self.root_path:
            return
        root = self.root_path

        def work(report, cancel):
            report(0, "Analyse de la carte…")
            return cleanup.scan(root, self.games)

        def done(issues):
            chosen = CleanupDialog(self, root, cleanup.CATEGORIES, issues).result
            if chosen:
                self._do_cleanup(chosen)

        self.run_in_background("Analyse", "broom", None, work, done)

    def _do_cleanup(self, issues):
        size = sum(i.size for i in issues)
        root, games = self.root_path, self.games

        def work(report, cancel):
            return cleanup.clean(root, issues, games, report, cancel)

        def done(result):
            removed, errors, count = result
            self._forget_games(removed)
            self.flash(f"Nettoyage terminé : {count} élément{'s' if count > 1 else ''}"
                       f"  ·  {human(size)} dans la corbeille", T.GREEN)
            if errors:
                info(self, "Erreurs", "Certains éléments n'ont pas pu être nettoyés :", "\n".join(errors[:30]))

        self.run_in_background("Nettoyage", "broom", len(issues), work, done, "Nettoyage de la carte")

    def download_images(self, games=None):
        """Télécharge depuis internet les images des jeux affichés qui n'en ont pas."""
        games = scraper.missing_images(self.shown if games is None else games)
        if not games:
            return

        def work(report, cancel):
            results = []
            for i, g in enumerate(games):
                if cancel.is_set():
                    break
                report(i, f"Recherche : {g.name}")
                try:
                    results.append((g, scraper.fetch_images(g)))
                except OSError:
                    results.append((g, {}))
            report(len(games), "Mise à jour des gamelist.xml…")
            return results, core.set_media(root, [(g, m) for g, m in results if m])

        root = self.root_path
        self.run_in_background("Images manquantes", "download", len(games), work,
                               lambda result: self._images_done(*result), "Images téléchargées")

    def _images_done(self, results, errors):
        total = len(results)
        found = [(g, m) for g, m in results if m]
        for g, _ in found:
            self.grid_view.thumbs.cache.pop(g.path, None)
        self.fill_games(keep_scroll=True)
        self.refresh_usage()
        missing = [g.name for g, m in results if not m]
        message = (f"{len(found)} jeu{'x' if len(found) > 1 else ''} sur {total} "
                   f"{'ont' if len(found) > 1 else 'a'} maintenant une image.")
        if missing:
            message += f"\nIntrouvables sur libretro-thumbnails ({len(missing)}) :"
        info(self, "Images", message, "\n".join([f"> {n}" for n in missing] + errors))

    def toggle_favorites(self, games):
        """Ajoute aux favoris, ou les retire si tous les jeux concernés le sont déjà."""
        games = list(games or self.selection)
        if not games:
            return
        value = not all(g.favorite for g in games)
        with journal.operation(self.root_path, "Ajout aux favoris" if value else "Retrait des favoris"):
            errors = core.set_favorites(self.root_path, games, value)
        self.refresh_history()
        self.sys_tree.item(FAV, values=(len(self.favorites()),))
        self.fill_games(keep_scroll=True)
        n = len(games)
        if value:
            self.flash(f"★ {n} jeu{'x' if n > 1 else ''} ajouté{'s' if n > 1 else ''} aux favoris", T.YELLOW)
        else:
            self.flash(f"{n} jeu{'x' if n > 1 else ''} retiré{'s' if n > 1 else ''} des favoris", T.MUTED)
        if errors:
            info(self, "Erreurs", "Les favoris n'ont pas pu être enregistrés :", "\n".join(errors))

    def delete_selected(self):
        sel = list(self.selection)
        if not sel:
            return
        with_saves = self.saves_var.get()
        plan = [(g, core.files_to_delete(g, self.games.get(g.system, []), with_saves)) for g in sel]
        nfiles = sum(len(f) for _, f in plan)
        size = sum(core.path_size(p) for _, files in plan for p in files)
        what = "ROM, images, vidéos" + (", sauvegardes" if with_saves else "")
        message = (f"{len(sel)} jeu{'x' if len(sel) > 1 else ''} vont être supprimés de la carte SD.\n"
                   f"{nfiles} fichiers · {human(size)} ({what}).\n"
                   "Ils passent par la corbeille : tu pourras annuler. Vide la corbeille pour libérer la place.")
        if not ask_delete(self, message, "\n".join(f"> {g.name}" for g in sel)):
            return
        root = self.root_path

        def work(report, cancel):
            errors = []
            for i, (g, files) in enumerate(plan):
                if cancel.is_set():
                    break
                report(i, f"Suppression : {g.name}")
                errors += core.delete_game(root, g, files)
            return errors

        def done(errors):
            self._forget_games(sel)
            gone = sum(1 for g in sel if not os.path.exists(g.path))
            self.flash(f"{gone} jeu{'x' if gone > 1 else ''} supprimé{'s' if gone > 1 else ''}"
                       f"  ·  {human(size)} dans la corbeille", T.GREEN)
            if errors:
                info(self, "Erreurs", "Certains fichiers n'ont pas pu être supprimés :", "\n".join(errors[:30]))

        self.run_in_background("Suppression", "trash", len(plan), work, done,
                               f"Suppression de {len(sel)} jeu{'x' if len(sel) > 1 else ''}")

    def open_folder(self):
        if len(self.selection) == 1:
            paths.reveal(self.selection[0].path)
        elif self.root_path and not self.selection:
            paths.reveal(self.root_path)


if __name__ == "__main__":
    App().mainloop()
