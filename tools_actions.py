"""Actions du menu OUTILS et du clic droit (classe mélangée dans App, voir app.py).

Chaque action prépare son travail, le lance avec self.run_in_background() (fenêtre de
chargement, pas de gel) puis rafraîchit l'affichage avec self.reload_systems().
"""
import datetime
import os
import tkinter as tk
from tkinter import filedialog

import bios
import chd
import core
import importer
import journal
import metadata
import multidisc
import saves
import scraper
import systems
import theme as T
from dialogs import ChecklistDialog, EditDialog, HistoryDialog, ImportDialog, ReportDialog
from widgets import _dialog, human, info


class ToolsMixin:
    # ------------------------------------------------------------ menus
    def _menu(self):
        return tk.Menu(self, tearoff=0, bg=T.PANEL2, fg=T.TEXT, activebackground=T.MAGENTA,
                       activeforeground=T.BG, font=T.F["body"], bd=0, relief="flat")

    def show_tools_menu(self, widget):
        m = self._menu()
        ready = bool(self.root_path)
        for label, command in (("Ajouter des jeux…", self.add_games),
                               (None, None),
                               ("Compléter les fiches incomplètes…", self.complete_cards),
                               ("Regrouper les jeux multi-disques…", self.group_multidisc),
                               ("Compresser les jeux CD en CHD…", self.compress_chd),
                               ("Supprimer des vidéos…", self.delete_videos_tool),
                               ("Nettoyer la carte…", self.cleanup),
                               (None, None),
                               ("Sauvegarder mes parties sur le PC…", self.backup_saves),
                               ("Restaurer des parties…", self.restore_saves),
                               (None, None),
                               ("Vérifier les BIOS…", self.check_bios),
                               (None, None),
                               ("Historique et corbeille…", self.show_history)):
            if label is None:
                m.add_separator()
            else:
                m.add_command(label="  " + label, command=command, state="normal" if ready else "disabled")
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def show_context_menu(self, event):
        games = list(self.selection)
        if not games:
            return
        one = len(games) == 1
        m = self._menu()
        if one:
            m.add_command(label="  Ouvrir le dossier", command=self.open_folder)
            m.add_command(label="  Modifier la fiche…", command=self.edit_selected)
        fav = all(g.favorite for g in games)
        m.add_command(label="  Retirer des favoris" if fav else "  Ajouter aux favoris",
                      command=lambda: self.toggle_favorites(games))
        m.add_command(label="  Compléter la fiche depuis internet", command=lambda: self.enrich_games(games))
        move = self._menu()
        current = {g.system for g in games}
        for s in sorted(core.list_systems(self.root_path), key=lambda k: systems.name(k).lower()):
            if s not in current:
                move.add_command(label=f"  {systems.name(s)}  ({s})", command=lambda s=s: self.move_games(games, s))
        m.add_cascade(label="  Déplacer vers", menu=move)
        m.add_separator()
        m.add_command(label="  Supprimer…", command=self.delete_selected)
        m.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------ utilitaires
    def reload_systems(self, names):
        """Relit des systèmes depuis la carte après une modification."""
        for s in set(names):
            games = core.load_system(self.root_path, s)
            if games:
                self.games[s] = games
            else:
                self.games.pop(s, None)
        self.selection = []
        self.fill_systems(self.current)
        self.refresh_usage()

    def _errors(self, errors, what="Certaines opérations ont échoué :"):
        if errors:
            info(self, "Erreurs", what, "\n".join(errors[:30]))

    # ------------------------------------------------------------ fiche / déplacement
    def edit_selected(self):
        if len(self.selection) != 1:
            return
        g = self.selection[0]
        values = EditDialog(self, g).show()
        if values is None:
            return
        images = values.pop("images", {})
        with journal.operation(self.root_path, f"Fiche modifiée : {g.name}"):
            errors = core.set_info(self.root_path, g, values)
            for tag, data in images.items():
                errors += scraper.set_image(self.root_path, g, tag, data, self.games.get(g.system, []))
                self.grid_view.thumbs.cache.pop(g.path, None)
        self.refresh_history()
        if images:
            self.refresh_usage()
        self.fill_games(keep_scroll=True)
        self.set_selection([g])
        self.flash("Fiche enregistrée", T.GREEN)
        self._errors(errors)

    def move_games(self, games, target):
        root = self.root_path
        sources = {g.system for g in games}

        def work(report, cancel):
            errors = []
            for i, g in enumerate(games):
                if cancel.is_set():
                    break
                report(i, f"Déplacement : {g.name}")
                errors += core.move_game(root, g, target, self.games.get(g.system, []))
            return errors

        def done(errors):
            self.reload_systems(sources | {target})
            self.flash(f"{len(games)} jeu{'x' if len(games) > 1 else ''} déplacé{'s' if len(games) > 1 else ''}"
                       f" vers {systems.name(target)}", T.GREEN)
            self._errors(errors)

        self.run_in_background("Déplacement", "move", len(games), work, done,
                               f"Déplacement vers {systems.name(target)}")

    # ------------------------------------------------------------ ajout de jeux
    def add_games(self, paths=None):
        if not self.root_path:
            return
        if paths is None:
            paths = filedialog.askopenfilenames(parent=self, title="Choisir des jeux à ajouter")
            if not paths:
                return
        files = importer.expand(paths)
        if not files:
            info(self, "Ajouter des jeux", "Aucun jeu reconnu dans ce qui a été déposé.")
            return
        available = core.list_systems(self.root_path)
        current = self.current if self.current in available else None
        rows = [(f, importer.guess_system(f, available, current), importer.total_size([f])) for f in files]
        u = core.disk_usage(self.root_path)
        result = ImportDialog(self, rows, available, u.free if u else 0).show()
        if not result:
            return
        items, scrape = result
        root = self.root_path

        def work(report, cancel):
            return importer.import_files(root, items, report, cancel)

        def done(result):
            copied, errors = result
            self.reload_systems({s for _, s in items})
            self.flash(f"{len(copied)} jeu{'x' if len(copied) > 1 else ''} ajouté{'s' if len(copied) > 1 else ''}",
                       T.GREEN)
            self._errors(errors, "Certains jeux n'ont pas été ajoutés :")
            if scrape and copied:
                new = {os.path.normcase(p) for p in copied}
                fresh = [g for lst in self.games.values() for g in lst if os.path.normcase(g.path) in new]
                self.enrich_games(fresh)

        self.run_in_background("Ajout de jeux", "plus", len(items), work, done,
                               f"Ajout de {len(items)} jeu{'x' if len(items) > 1 else ''}")

    def on_drop(self, event):
        self.add_games(self.tk.splitlist(event.data))

    # ------------------------------------------------------------ fiches depuis internet
    def enrich_games(self, games):
        """Complète les fiches (description, année, genre, développeur, éditeur, joueurs, images)
        depuis internet. Un jeu introuvable ou une source muette n'arrête jamais la suite."""
        games = [g for g in games if metadata.missing_fields(g) or not core.cover_for(g)]
        if not games:
            self.flash("Ces fiches sont déjà complètes", T.GREEN)
            return
        root = self.root_path

        def work(report, cancel):
            done, empty, media = 0, [], []
            for i, g in enumerate(games):
                if cancel.is_set():
                    break
                report(i, f"Recherche : {g.name}")
                values = metadata.lookup(g)  # ne lève jamais
                images = {}
                if not core.cover_for(g) and scraper.supported(g.system):
                    try:
                        images = scraper.fetch_images(g)
                    except Exception:  # réseau : on passe au jeu suivant
                        images = {}
                if values:
                    core.set_info(root, g, values)
                if images:
                    media.append((g, images))
                if values.keys() - {"name"} or images:
                    done += 1
                else:
                    empty.append(g.name)
            report(len(games), "Mise à jour des gamelist.xml…")
            core.set_media(root, media)
            return done, empty

        def finished(result):
            done, empty = result
            for g in games:
                self.grid_view.thumbs.cache.pop(g.path, None)
            self.fill_games(keep_scroll=True)
            self.refresh_usage()
            text = f"{done} fiche{'s' if done > 1 else ''} complétée{'s' if done > 1 else ''}"
            if empty:
                text += f"  ·  rien trouvé pour {len(empty)} jeu{'x' if len(empty) > 1 else ''}"
            self.flash(text, T.GREEN)

        self.run_in_background("Fiches depuis internet", "download", len(games), work, finished,
                               f"Fiches complétées ({len(games)} jeu{'x' if len(games) > 1 else ''})")

    def complete_cards(self):
        games = metadata.incomplete([g for lst in self.games.values() for g in lst])
        if not games:
            info(self, "Fiches", "Toutes les fiches ont une description, une année, un genre et une image.")
            return
        labels = {"desc": "description", "year": "année", "genre": "genre"}

        def detail(g):
            missing = [labels[k] for k in ("desc", "year", "genre") if k in metadata.missing_fields(g)]
            return "manque : " + ", ".join(missing + ([] if core.cover_for(g) else ["image"]))
        items = [(g.name, detail(g), True, None) for g in games]
        chosen = ChecklistDialog(self, "Compléter les fiches", "download",
                                 "Cherche sur internet (base libretro, Wikidata, Wikipédia, images libretro) ce qui "
                                 "manque à ces fiches. Rien n'est écrasé. Compter quelques secondes par jeu ; "
                                 "un jeu introuvable est simplement passé.", items, "COMPLÉTER").show()
        if chosen:
            self.enrich_games([games[i] for i in chosen])

    # ------------------------------------------------------------ multi-disques
    def group_multidisc(self):
        groups = multidisc.find_groups(self.games)
        if not groups:
            info(self, "Multi-disques", "Aucun jeu en plusieurs disques à regrouper.")
            return
        items = [(f"{gr.name}", f"{systems.name(gr.system)} · {len(gr.discs)} disques", True, None) for gr in groups]
        chosen = ChecklistDialog(self, "Jeux multi-disques", "disc",
                                 "Chaque jeu sélectionné n'apparaîtra plus qu'une seule fois sur la console. "
                                 "Les disques sont rangés dans un dossier caché « .multidisc » et on change "
                                 "de disque depuis le menu RetroArch (Hotkey + X → Contrôle du disque).",
                                 items, "REGROUPER").show()
        if not chosen:
            return
        root, picked = self.root_path, [groups[i] for i in chosen]

        def work(report, cancel):
            errors = []
            for i, gr in enumerate(picked):
                if cancel.is_set():
                    break
                report(i, f"Regroupement : {gr.name}")
                errors += multidisc.create_m3u(root, gr)[1]
            return errors

        def done(errors):
            self.reload_systems({gr.system for gr in picked})
            self.flash(f"{len(picked)} jeu{'x' if len(picked) > 1 else ''} regroupé{'s' if len(picked) > 1 else ''}",
                       T.GREEN)
            self._errors(errors)

        self.run_in_background("Multi-disques", "disc", len(picked), work, done, "Regroupement multi-disques")

    # ------------------------------------------------------------ vidéos
    def delete_videos_tool(self):
        root = self.root_path
        per_system = {s: core.video_files(root, s) for s in core.list_systems(root)}
        per_system = {s: v for s, v in per_system.items() if v}
        if not per_system:
            info(self, "Vidéos", "Il n'y a aucune vidéo de présentation sur la carte.")
            return
        names = sorted(per_system, key=lambda k: systems.name(k).lower())
        items = [(systems.name(s), f"{len(per_system[s])} vidéos", False,
                  sum(core.path_size(p) for p in per_system[s])) for s in names]
        chosen = ChecklistDialog(self, "Supprimer des vidéos", "film",
                                 "Les vidéos de présentation ne servent qu'à l'aperçu dans la liste des jeux. "
                                 "Les jeux, images et sauvegardes ne sont pas touchés.",
                                 items, "SUPPRIMER", "danger").show()
        if not chosen:
            return
        picked = [names[i] for i in chosen]
        size = sum(items[i][3] for i in chosen)

        def work(report, cancel):
            errors = []
            for i, s in enumerate(picked):
                if cancel.is_set():
                    break
                report(i, f"Vidéos : {systems.name(s)}")
                errors += core.delete_videos(root, s, self.games.get(s, []))
            return errors

        def done(errors):
            self.refresh_usage()
            self.show_details()
            self.flash(f"Vidéos supprimées  ·  {human(size)} dans la corbeille", T.GREEN)
            self._errors(errors)

        self.run_in_background("Suppression des vidéos", "film", len(picked), work, done,
                               "Suppression des vidéos")

    # ------------------------------------------------------------ compression CHD
    def compress_chd(self):
        games = chd.convertible(self.games)
        if not games:
            info(self, "Compression CHD", "Aucun jeu CD au format .cue / .gdi à compresser.")
            return
        def label(g):
            disc = core.DISC_RE.search(g.stem)
            return g.name + (f"  (disque {disc.group(1)})" if disc and not core.DISC_RE.search(g.name) else "")
        items = [(label(g), systems.name(g.system), False, g.size) for g in games]
        note = "" if chd.find_chdman() else ("L'outil chdman (MAME) sera téléchargé automatiquement "
                                              "la première fois (≈ 85 Mo).")
        chosen = ChecklistDialog(self, "Compression CHD", "compress",
                                 "Compresse les jeux CD sans perte au format .chd, lu directement par la console : "
                                 "on gagne souvent 30 à 60 % de place. Compter environ une minute par jeu. "
                                 "Les sauvegardes restent valables.", items, "COMPRESSER", note=note).show()
        if not chosen:
            return
        picked = [games[i] for i in chosen]
        before = sum(g.size for g in picked)
        root = self.root_path

        def work(report, cancel):
            tool = chd.find_chdman() or chd.download_chdman(report, cancel)
            errors = []
            for i, g in enumerate(picked):
                if cancel.is_set():
                    break
                report(i, f"Compression : {g.name}")
                try:
                    errors += chd.convert_game(root, tool, g, cancel)
                except OSError as e:
                    errors.append(f"{g.name} : {e}")
            return errors

        def done(errors):
            self.reload_systems({g.system for g in picked})
            self.flash(f"Compression terminée  ·  {human(before)} compressés", T.GREEN)
            self._errors(errors, "Certains jeux n'ont pas pu être compressés :")

        self.run_in_background("Compression CHD", "compress", len(picked), work, done, "Compression CHD")

    # ------------------------------------------------------------ sauvegardes
    def backup_saves(self):
        files = saves.collect(self.root_path)
        if not files:
            info(self, "Sauvegardes", "Aucune sauvegarde trouvée sur la carte.")
            return
        name = f"R36S-sauvegardes-{datetime.date.today():%Y-%m-%d}.zip"
        dest = filedialog.asksaveasfilename(parent=self, title="Enregistrer les sauvegardes", initialfile=name,
                                            defaultextension=".zip", filetypes=[("Archive zip", "*.zip")])
        if not dest:
            return
        root = self.root_path

        def done(count):
            self.flash(f"{count} sauvegardes copiées dans {os.path.basename(dest)}", T.GREEN)
            info(self, "Sauvegardes", f"{count} fichiers de sauvegarde ont été copiés dans :\n{dest}")

        self.run_in_background("Sauvegarde des parties", "save", len(files),
                               lambda report, cancel: saves.backup(root, files, dest, report, cancel), done)

    def restore_saves(self):
        src = filedialog.askopenfilename(parent=self, title="Choisir une sauvegarde à restaurer",
                                         filetypes=[("Archive zip", "*.zip")])
        if not src:
            return
        choice = _dialog(self, "Restaurer", "Que faire si une sauvegarde existe déjà sur la carte ?", "",
                         [("ANNULER", "normal", None), ("GARDER CELLE DE LA CARTE", "normal", False),
                          ("REMPLACER", "danger", True)], T.YELLOW, "save")
        if choice is None:
            return
        root = self.root_path

        def done(result):
            restored, skipped = result
            self.flash(f"{restored} sauvegardes restaurées", T.GREEN)
            info(self, "Restauration", f"{restored} sauvegardes restaurées, {skipped} ignorées.")

        self.run_in_background("Restauration", "save", saves.zip_count(src),
                               lambda report, cancel: saves.restore(root, src, choice, report, cancel), done,
                               "Restauration des parties")

    # ------------------------------------------------------------ annulation / corbeille
    def refresh_history(self):
        """Met à jour le bouton « annuler » (activé s'il y a une opération à défaire)."""
        hist = journal.history(self.root_path) if self.root_path else []
        self.btn_undo.set_enabled(bool(hist))
        self.undo_tip.text = f"Annuler : {hist[0][1]}" if hist else "Rien à annuler"

    def undo_last(self):
        hist = journal.history(self.root_path) if self.root_path else []
        if not hist:
            return
        op_id, label, date, _ = hist[0]
        if not _dialog(self, "Annuler", f"Défaire « {label} » ({date[8:10]}/{date[5:7]} à {date[11:16]}) ?\n"
                                        "Les fichiers et les fiches reviennent comme avant cette opération.", "",
                       [("NON", "normal", False), ("ANNULER L'OPÉRATION", "danger", True)], T.YELLOW, "undo"):
            return
        root = self.root_path

        def done(errors):
            self.load_drive()  # tout est relu depuis la carte
            self.flash(f"Opération annulée : {label}", T.GREEN)
            self._errors(errors, "Certains éléments n'ont pas pu être remis en place :")

        self.run_in_background("Annulation", "undo", None, lambda report, cancel: journal.undo(root, op_id), done)

    def show_history(self):
        root = self.root_path
        choice = HistoryDialog(self, journal.history(root), journal.trash_size(root)).show()
        if choice == "undo":
            self.undo_last()
        elif choice == "empty":
            size = journal.trash_size(root)
            if _dialog(self, "Vider la corbeille", f"{human(size)} seront libérés sur la carte.\n"
                       "Les opérations passées ne pourront plus être annulées.", "",
                       [("NON", "normal", False), ("VIDER", "danger", True)], T.RED, "trash"):
                def done(_):
                    self.refresh_history()
                    self.refresh_usage()
                    self.flash(f"Corbeille vidée  ·  {human(size)} libérés", T.GREEN)
                self.run_in_background("Corbeille", "trash", None,
                                       lambda report, cancel: journal.empty_trash(root), done)

    # ------------------------------------------------------------ BIOS
    def check_bios(self):
        results = bios.check(self.root_path, list(self.games))
        if not results:
            info(self, "BIOS", "Aucune de tes consoles n'a besoin de BIOS.")
            return
        lines, last, missing = [], None, 0
        for system, desc, level, found, names in results:
            if system != last:
                lines.append((systems.name(system).upper(), "head"))
                last = system
            if found:
                lines.append((f"  ✓  {desc} : {found}", "ok"))
            else:
                bad = level == bios.REQUIRED
                missing += bad
                lines.append((f"  {'✗' if bad else '~'}  {desc} ({level}) : manquant", "bad" if bad else "warn"))
                lines.append((f"       un de ces fichiers dans bios/ : {', '.join(names[:4])}", "muted"))
        intro = ("Tout est en ordre pour tes consoles." if not missing else
                 f"{missing} BIOS requis manquant{'s' if missing > 1 else ''} : les jeux de ces consoles risquent "
                 "de ne pas démarrer.")
        ReportDialog(self, "Vérification des BIOS", "chip", intro, lines).show()
