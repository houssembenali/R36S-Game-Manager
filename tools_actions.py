"""Actions du menu OUTILS et du clic droit (classe mélangée dans App, voir app.py).

Chaque action prépare son travail, le lance avec self.run_in_background() (fenêtre de
chargement, pas de gel) puis rafraîchit l'affichage avec self.reload_systems().
Textes affichés : via _() / _n() (voir i18n.py).
"""
import datetime
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog

import bios
import chd
import core
import dupes
import health
import i18n
import importer
import journal
import metadata
import multidisc
import paths
import ports
import saves
import scraper
import settings
import systems
import theme as T
from dialogs import ChecklistDialog, EditDialog, HistoryDialog, ImportDialog, PortCatalogDialog, ReportDialog
from i18n import _, _n
from widgets import _dialog, human, info


class ToolsMixin:
    # ------------------------------------------------------------ menus
    def _menu(self):
        return tk.Menu(self, tearoff=0, bg=T.PANEL2, fg=T.TEXT, activebackground=T.MAGENTA,
                       activeforeground=T.BG, font=T.F["body"], bd=0, relief="flat")

    def show_tools_menu(self, widget):
        m = self._menu()
        ready = bool(self.root_path)
        for label, command in ((_("Ajouter des jeux…"), self.add_games),
                               (None, None),
                               (_("Compléter les fiches incomplètes…"), self.complete_cards),
                               (_("Regrouper les jeux multi-disques…"), self.group_multidisc),
                               (_("Compresser les jeux CD en CHD…"), self.compress_chd),
                               (_("Supprimer des vidéos…"), self.delete_videos_tool),
                               (_("Nettoyer la carte…"), self.cleanup),
                               (_("Chercher les doublons…"), self.find_dupes),
                               (_("Vérifier la carte SD…"), self.check_card),
                               (None, None),
                               (_("Catalogue PortMaster…"), self.port_catalog),
                               (_("Mises à jour des ports…"), self.port_updates),
                               (_("Installer un port depuis un .zip…"), self.install_port_zips),
                               (_("Ports en attente d'installation…"), self.pending_ports),
                               (None, None),
                               (_("Sauvegarder mes parties sur le PC…"), self.backup_saves),
                               (_("Restaurer des parties…"), self.restore_saves),
                               (None, None),
                               (_("Vérifier les BIOS…"), self.check_bios),
                               (None, None),
                               (_("Historique et corbeille…"), self.show_history)):
            if label is None:
                m.add_separator()
            else:
                m.add_command(label="  " + label, command=command, state="normal" if ready else "disabled")
        m.add_separator()
        lang = self._menu()
        for code, name in i18n.LANGUAGES.items():
            lang.add_command(label=("  ✓ " if code == i18n.LANG else "     ") + name,
                             command=lambda c=code: self.change_language(c))
        m.add_cascade(label="  " + _("Langue") + " / Language", menu=lang)
        m.tk_popup(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def show_context_menu(self, event):
        games = list(self.selection)
        if not games:
            return
        one = len(games) == 1
        m = self._menu()
        if one:
            m.add_command(label="  " + _("Ouvrir le dossier"), command=self.open_folder)
            m.add_command(label="  " + _("Modifier la fiche…"), command=self.edit_selected)
        fav = all(g.favorite for g in games)
        m.add_command(label="  " + (_("Retirer des favoris") if fav else _("Ajouter aux favoris")),
                      command=lambda: self.toggle_favorites(games))
        m.add_command(label="  " + _("Compléter la fiche depuis internet"), command=lambda: self.enrich_games(games))
        if one and self.needs_port_files(games[0]):
            m.add_command(label="  " + _("Ajouter les fichiers du jeu…"), command=self.add_port_files)
        move = self._menu()
        current = {g.system for g in games}
        for s in sorted(core.list_systems(self.root_path), key=lambda k: systems.name(k).lower()):
            if s not in current:
                move.add_command(label=f"  {systems.name(s)}  ({s})", command=lambda s=s: self.move_games(games, s))
        m.add_cascade(label="  " + _("Déplacer vers"), menu=move)
        m.add_separator()
        m.add_command(label="  " + _("Supprimer…"), command=self.delete_selected)
        m.tk_popup(event.x_root, event.y_root)

    def change_language(self, code):
        """Change la langue : elle s'applique au prochain démarrage (proposé tout de suite)."""
        if code == i18n.LANG:
            return
        settings.set("language", code)
        self.save_settings()
        i18n.set_language(code)  # pour que la question soit posée dans la nouvelle langue
        if _dialog(self, _("Langue"), _("La langue sera changée au redémarrage du programme."), "",
                   [(_("PLUS TARD"), "normal", False), (_("REDÉMARRER"), "normal", True)], T.CYAN, "menu"):
            self.restart()

    def restart(self):
        args = [sys.executable] if paths.FROZEN else [sys.executable, os.path.abspath(sys.argv[0])]
        subprocess.Popen(args)
        self.quit_app()

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

    def _errors(self, errors, what=None):
        if errors:
            info(self, _("Erreurs"), what or _("Certaines opérations ont échoué :"), "\n".join(errors[:30]))

    # ------------------------------------------------------------ fiche / déplacement
    def edit_selected(self):
        if len(self.selection) != 1:
            return
        g = self.selection[0]
        values = EditDialog(self, g).show()
        if values is None:
            return
        images = values.pop("images", {})
        with journal.operation(self.root_path, _("Fiche modifiée : {name}", name=g.name)):
            errors = core.set_info(self.root_path, g, values)
            for tag, data in images.items():
                errors += scraper.set_image(self.root_path, g, tag, data, self.games.get(g.system, []))
                self.grid_view.thumbs.cache.pop(g.path, None)
        self.refresh_history()
        if images:
            self.refresh_usage()
        self.fill_games(keep_scroll=True)
        self.set_selection([g])
        self.flash(_("Fiche enregistrée"), T.GREEN)
        self._errors(errors)

    def move_games(self, games, target):
        root = self.root_path
        sources = {g.system for g in games}

        def work(report, cancel):
            errors = []
            for i, g in enumerate(games):
                if cancel.is_set():
                    break
                report(i, _("Déplacement : {name}", name=g.name))
                errors += core.move_game(root, g, target, self.games.get(g.system, []))
            return errors

        def done(errors):
            self.reload_systems(sources | {target})
            self.flash(_n(len(games), "{n} jeu déplacé vers {system}", "{n} jeux déplacés vers {system}",
                          system=systems.name(target)), T.GREEN)
            self._errors(errors)

        self.run_in_background(_("Déplacement"), "move", len(games), work, done,
                               _("Déplacement vers {system}", system=systems.name(target)))

    # ------------------------------------------------------------ ajout de jeux
    def add_games(self, files=None):
        if not self.root_path:
            return
        if files is None:
            files = filedialog.askopenfilenames(parent=self, title=_("Choisir des jeux à ajouter"))
            if not files:
                return
        files = importer.expand(files)
        if not files:
            info(self, _("Ajouter des jeux"), _("Aucun jeu reconnu dans ce qui a été déposé."))
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
            self.reload_systems({s for _f, s in items})
            self.flash(_n(len(copied), "{n} jeu ajouté", "{n} jeux ajoutés"), T.GREEN)
            self._errors(errors, _("Certains jeux n'ont pas été ajoutés :"))
            if scrape and copied:
                new = {os.path.normcase(p) for p in copied}
                fresh = [g for lst in self.games.values() for g in lst if os.path.normcase(g.path) in new]
                self.enrich_games(fresh)

        self.run_in_background(_("Ajout de jeux"), "plus", len(items), work, done,
                               _n(len(items), "Ajout de {n} jeu", "Ajout de {n} jeux"))

    def on_drop(self, event):
        files = list(self.tk.splitlist(event.data))
        port_zips = [f for f in files if f.lower().endswith(".zip") and ports.is_port_zip(f)]
        if port_zips:
            self.install_port_zips(port_zips)
        rest = [f for f in files if f not in port_zips]
        if rest:
            self.add_games(rest)

    # ------------------------------------------------------------ fiches depuis internet
    def enrich_games(self, games):
        """Complète les fiches (description, année, genre, développeur, éditeur, joueurs, images)
        depuis internet. Un jeu introuvable ou une source muette n'arrête jamais la suite."""
        games = [g for g in games if metadata.missing_fields(g) or metadata.needs_images(g)]
        if not games:
            self.flash(_("Ces fiches sont déjà complètes"), T.GREEN)
            return
        root = self.root_path

        def work(report, cancel):
            done, empty, media = 0, [], []
            for i, g in enumerate(games):
                if cancel.is_set():
                    break
                report(i, _("Recherche : {name}", name=g.name))
                values = metadata.lookup(g)  # ne lève jamais
                images = self._find_images(g)
                if values:
                    core.set_info(root, g, values)
                if images:
                    media.append((g, images))
                if values.keys() - {"name"} or images:
                    done += 1
                else:
                    empty.append(g.name)
            report(len(games), _("Mise à jour des gamelist.xml…"))
            core.set_media(root, media)
            return done, empty

        def finished(result):
            done, empty = result
            for g in games:
                self.grid_view.thumbs.cache.pop(g.path, None)
            self.fill_games(keep_scroll=True)
            self.refresh_usage()
            text = _n(done, "{n} fiche complétée", "{n} fiches complétées")
            if empty:
                text += "  ·  " + _n(len(empty), "rien trouvé pour {n} jeu", "rien trouvé pour {n} jeux")
            self.flash(text, T.GREEN)

        self.run_in_background(_("Fiches depuis internet"), "download", len(games), work, finished,
                               _n(len(games), "Fiches complétées ({n} jeu)", "Fiches complétées ({n} jeux)"))

    @staticmethod
    def _find_images(g):
        """Images à inscrire dans la fiche d'un jeu qui n'en a pas ({balise: chemin}). Ne lève jamais."""
        if not metadata.needs_images(g):
            return {}
        try:
            if core.port_media(g):
                return core.port_media(g)  # images livrées avec le port : rien à télécharger
            if g.system.lower() == "ports":
                shot = ports.catalog_screenshot(g)  # capture du catalogue PortMaster
                if not shot:
                    return {}
                path = scraper.save_image(shot, os.path.join(g.sysdir, "media", "images", g.stem))
                return {"image": path, "thumbnail": path}
            return scraper.fetch_images(g) if scraper.supported(g.system) else {}
        except Exception:  # réseau : on passe au jeu suivant
            return {}

    def complete_cards(self):
        games = metadata.incomplete([g for lst in self.games.values() for g in lst])
        if not games:
            info(self, _("Fiches"), _("Toutes les fiches ont une description, une année, un genre et une image."))
            return
        labels = {"desc": _("description"), "year": _("année"), "genre": _("genre")}

        def detail(g):
            missing = [labels[k] for k in ("desc", "year", "genre") if k in metadata.missing_fields(g)]
            return _("manque : {list}", list=", ".join(missing + ([] if core.cover_for(g) else [_("image")])))
        items = [(g.name, detail(g), True, None) for g in games]
        chosen = ChecklistDialog(self, _("Compléter les fiches"), "download",
                                 _("Cherche sur internet (base libretro, Wikidata, Wikipédia, images libretro) ce qui "
                                   "manque à ces fiches. Rien n'est écrasé. Compter quelques secondes par jeu ; "
                                   "un jeu introuvable est simplement passé."), items, _("COMPLÉTER")).show()
        if chosen:
            self.enrich_games([games[i] for i in chosen])

    # ------------------------------------------------------------ multi-disques
    def group_multidisc(self):
        groups = multidisc.find_groups(self.games)
        if not groups:
            info(self, _("Multi-disques"), _("Aucun jeu en plusieurs disques à regrouper."))
            return
        items = [(gr.name, f"{systems.name(gr.system)} · " + _n(len(gr.discs), "{n} disque", "{n} disques"),
                  True, None) for gr in groups]
        chosen = ChecklistDialog(self, _("Jeux multi-disques"), "disc",
                                 _("Chaque jeu sélectionné n'apparaîtra plus qu'une seule fois sur la console. "
                                   "Les disques sont rangés dans un dossier caché « .multidisc » et on change "
                                   "de disque depuis le menu RetroArch (Hotkey + X → Contrôle du disque)."),
                                 items, _("REGROUPER")).show()
        if not chosen:
            return
        root, picked = self.root_path, [groups[i] for i in chosen]

        def work(report, cancel):
            errors = []
            for i, gr in enumerate(picked):
                if cancel.is_set():
                    break
                report(i, _("Regroupement : {name}", name=gr.name))
                errors += multidisc.create_m3u(root, gr)[1]
            return errors

        def done(errors):
            self.reload_systems({gr.system for gr in picked})
            self.flash(_n(len(picked), "{n} jeu regroupé", "{n} jeux regroupés"), T.GREEN)
            self._errors(errors)

        self.run_in_background(_("Multi-disques"), "disc", len(picked), work, done, _("Regroupement multi-disques"))

    # ------------------------------------------------------------ vidéos
    def delete_videos_tool(self):
        root = self.root_path
        per_system = {s: core.video_files(root, s) for s in core.list_systems(root)}
        per_system = {s: v for s, v in per_system.items() if v}
        if not per_system:
            info(self, _("Vidéos"), _("Il n'y a aucune vidéo de présentation sur la carte."))
            return
        names = sorted(per_system, key=lambda k: systems.name(k).lower())
        items = [(systems.name(s), _n(len(per_system[s]), "{n} vidéo", "{n} vidéos"), False,
                  sum(core.path_size(p) for p in per_system[s])) for s in names]
        chosen = ChecklistDialog(self, _("Supprimer des vidéos"), "film",
                                 _("Les vidéos de présentation ne servent qu'à l'aperçu dans la liste des jeux. "
                                   "Les jeux, images et sauvegardes ne sont pas touchés."),
                                 items, _("SUPPRIMER"), "danger").show()
        if not chosen:
            return
        picked = [names[i] for i in chosen]
        size = sum(items[i][3] for i in chosen)

        def work(report, cancel):
            errors = []
            for i, s in enumerate(picked):
                if cancel.is_set():
                    break
                report(i, _("Vidéos : {system}", system=systems.name(s)))
                errors += core.delete_videos(root, s, self.games.get(s, []))
            return errors

        def done(errors):
            self.refresh_usage()
            self.show_details()
            self.flash(_("Vidéos supprimées") + "  ·  " + _("{size} dans la corbeille", size=human(size)), T.GREEN)
            self._errors(errors)

        self.run_in_background(_("Suppression des vidéos"), "film", len(picked), work, done,
                               _("Suppression des vidéos"))

    # ------------------------------------------------------------ compression CHD
    def compress_chd(self):
        games = chd.convertible(self.games)
        if not games:
            info(self, _("Compression CHD"), _("Aucun jeu CD au format .cue / .gdi à compresser."))
            return

        def label(g):
            disc = core.DISC_RE.search(g.stem)
            return g.name + (_("  (disque {n})", n=disc.group(1)) if disc and not core.DISC_RE.search(g.name)
                             else "")
        items = [(label(g), systems.name(g.system), False, g.size) for g in games]
        note = "" if chd.find_chdman() else _("L'outil chdman (MAME) sera téléchargé automatiquement "
                                              "la première fois (≈ 85 Mo).")
        chosen = ChecklistDialog(self, _("Compression CHD"), "compress",
                                 _("Compresse les jeux CD sans perte au format .chd, lu directement par la console : "
                                   "on gagne souvent 30 à 60 % de place. Compter environ une minute par jeu. "
                                   "Les sauvegardes restent valables."), items, _("COMPRESSER"), note=note).show()
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
                report(i, _("Compression : {name}", name=g.name))
                try:
                    errors += chd.convert_game(root, tool, g, cancel)
                except OSError as e:
                    errors.append(f"{g.name} : {e}")
            return errors

        def done(errors):
            self.reload_systems({g.system for g in picked})
            self.flash(_("Compression terminée") + "  ·  " + _("{size} compressés", size=human(before)), T.GREEN)
            self._errors(errors, _("Certains jeux n'ont pas pu être compressés :"))

        self.run_in_background(_("Compression CHD"), "compress", len(picked), work, done, _("Compression CHD"))

    # ------------------------------------------------------------ santé de la carte
    def check_card(self):
        """Relit toute la carte pour trouver les fichiers abîmés (les cartes d'origine lâchent souvent)."""
        root = self.root_path
        mb = 1 << 20
        usage = core.disk_usage(root)
        total_mb = max(1, (usage.total - usage.free) // mb)

        def work(report, cancel):
            def progress(read, total, path):
                report(read // mb, f"{os.path.relpath(path, root)}  ·  {human(read)} / {human(total)}")
            return health.check(root, progress, cancel)

        self.run_in_background(_("Vérification de la carte"), "sd", total_mb, work,
                               lambda result: self._card_report(root, result))

    def _card_report(self, root, r):
        titles = {"unreadable": _("Fichiers illisibles"), "corrupt": _("Archives abîmées"),
                  "empty": _("ROM vides (0 octet)"), "gamelist": _("gamelist.xml abîmés"),
                  "slow": _("Fichiers très lents à lire")}
        by_kind = {k: [p for p in r.problems if p.kind == k] for k in titles}
        broken = by_kind["unreadable"] or by_kind["corrupt"] or by_kind["gamelist"]
        lines = []
        if r.cancelled:
            lines.append((_("Vérification arrêtée avant la fin : {n} fichiers vérifiés.", n=r.files), "warn"))
        if broken:
            lines.append(("⚠ " + _("La carte a des fichiers abîmés. Sauvegarde tes parties maintenant (Outils → "
                                   "Sauvegarder mes parties) et pense à passer sur une carte neuve de bonne "
                                   "qualité."), "bad"))
        elif by_kind["slow"] or by_kind["empty"]:
            lines.append(("⚠ " + _("Rien d'illisible, mais quelques points à surveiller."), "warn"))
        else:
            lines.append(("✓ " + _("Aucun problème : tous les fichiers se lisent correctement."), "ok"))
        lines.append((_("{n} fichiers relus ({size}) en {minutes} min.", n=r.files, size=human(r.read),
                        minutes=max(1, round(r.seconds / 60))), "muted"))
        if r.speed:
            slow = r.speed < health.SLOW_SPEED
            lines.append((_("Vitesse de lecture moyenne : {speed}/s", speed=human(int(r.speed)))
                          + ("  —  " + _("c'est lent : la carte est peut-être fatiguée ou de mauvaise qualité.")
                             if slow else ""), "warn" if slow else "muted"))
        advice = {"unreadable": _("Recopie ces fichiers depuis ton PC ; s'ils reviennent, la carte est en fin de vie."),
                  "corrupt": _("Le contenu a changé sans que tu le touches : recopie ces jeux."),
                  "empty": _("Copie interrompue : recopie ces jeux."),
                  "gamelist": _("Les fiches de cette console sont perdues pour EmulationStation. "
                                "Annule une opération récente ou recrée les fiches."),
                  "slow": _("La carte peine à lire ces endroits : surveille-les.")}
        for kind, title in titles.items():
            found = by_kind[kind]
            if found:
                lines.append((T.px(f"{title} ({len(found)})"), "head"))
                lines.append((advice[kind], "muted"))
                lines += [("> " + os.path.relpath(p.path, root) + (f"   ({p.detail})" if p.detail else ""),
                           "bad" if kind in ("unreadable", "corrupt", "gamelist") else "warn") for p in found[:200]]
        ReportDialog(self, _("Vérification de la carte"), "sd",
                     _("Chaque fichier de la carte a été relu en entier ; les .zip sont aussi contrôlés avec leur "
                       "empreinte (CRC)."), lines).show()

    # ------------------------------------------------------------ doublons
    def find_dupes(self):
        """Doublons sur toute la carte (copies identiques et versions d'un même jeu), meilleure copie gardée."""
        games = self.games

        def work(report, cancel):
            return dupes.find(games, lambda done, total, name: report(done, _("Comparaison : {name}", name=name)),
                              cancel)

        self.run_in_background(_("Doublons"), "copy", None, work, self._dupes_found)

    def _dupes_found(self, found):
        if not found:
            info(self, _("Doublons"), _("Aucun doublon sur la carte."))
            return

        def where(g):
            return f"{g.name}  [{systems.name(g.system)}]"
        items = []
        for d in found:
            what = (_("copie identique de : {name}", name=where(d.keep)) if d.kind == "copy"
                    else _("autre version de : {name}", name=d.keep.stem))
            if not d.checked:
                what += "  ·  " + _("a des parties, une note ou est en favori")
            items.append((f"{d.game.stem}  [{systems.name(d.game.system)}]", what, d.checked, d.game.size))
        chosen = ChecklistDialog(self, _("Doublons"), "copy",
                                 _("Pour chaque jeu en double, la meilleure copie est gardée : celle qui a des parties, "
                                   "une note ou un favori, puis la meilleure région et la révision la plus récente. "
                                   "Les copies cochées seront supprimées (elles passent par la corbeille)."),
                                 items, _("SUPPRIMER"), "danger").show()
        if not chosen:
            return
        plan = [(d.game, core.files_to_delete(d.game, self.games.get(d.game.system, [])))
                for d in (found[i] for i in chosen)]
        size = sum(core.path_size(p) for _g, files in plan for p in files)
        root = self.root_path

        def work(report, cancel):
            errors = []
            for i, (g, files) in enumerate(plan):
                if cancel.is_set():
                    break
                report(i, _("Suppression : {name}", name=g.name))
                errors += core.delete_game(root, g, files)
            return errors

        def done(errors):
            gone = [g for g, _f in plan]
            self._forget_games(gone)
            n = sum(1 for g in gone if not os.path.exists(g.path))
            self.flash(_n(n, "{n} doublon supprimé", "{n} doublons supprimés") + "  ·  "
                       + _("{size} dans la corbeille", size=human(size)), T.GREEN)
            self._errors(errors, _("Certains fichiers n'ont pas pu être supprimés :"))

        self.run_in_background(_("Suppression"), "trash", len(plan), work, done,
                               _n(len(plan), "Suppression de {n} doublon", "Suppression de {n} doublons"))

    # ------------------------------------------------------------ ports PortMaster
    def port_catalog(self):
        """Catalogue PortMaster : choisir des ports à installer depuis le PC."""
        root = self.root_path

        def show(catalog):
            chosen = PortCatalogDialog(self, catalog, ports.installed(root), ports.pending(root)).show()
            if chosen:
                self.install_ports(chosen)
        self.run_in_background(_("Catalogue PortMaster"), "download", None,
                               lambda report, cancel: ports.load_catalog(), show)

    def port_updates(self):
        """Ports installés dont le catalogue propose une version plus récente, et bibliothèques
        manquantes aux ports installés (sans elles le port ne se lance pas)."""
        root = self.root_path

        def check(report, cancel):
            catalog = ports.load_catalog(force=True)
            return catalog, ports.missing_installed_runtimes(root), ports.portmaster_update(root)

        def show(result):
            catalog, libs, pm = result
            waiting = ports.pending(root)
            found = [p for p in ports.updates(root, catalog) if p.key not in waiting]
            if not found and not libs and not pm:
                info(self, _("Mises à jour des ports"), _("Tous les ports installés sont à jour."))
                return
            items = [(p.title, _("version du {date}", date=p.updated) if p.updated else "", True, p.size)
                     for p in found]
            items += [(rt[0], _("bibliothèque manquante"), True, rt[3]) for rt in libs]
            if pm:
                items.append(("PortMaster", _("version {new} (sur la carte : {old})", new=pm[0][:10],
                                              old=ports.portmaster_version(root)[:10]), True, pm[3]))
            text = _("Une version plus récente de ces ports existe. La nouvelle version remplace l'ancienne au "
                     "prochain lancement de PortMaster ; les fichiers du jeu et les sauvegardes sont gardés.")
            if libs:
                text += " " + _("Les bibliothèques manquantes sont nécessaires pour lancer des ports déjà installés.")
            chosen = ChecklistDialog(self, _("Mises à jour des ports"), "download", text, items,
                                     _("METTRE À JOUR")).show()
            if chosen:
                n = len(found) + len(libs)
                self.install_ports([found[i] for i in chosen if i < len(found)],
                                   [libs[i - len(found)] for i in chosen if len(found) <= i < n],
                                   pm if n in chosen else None)
        self.run_in_background(_("Mises à jour des ports"), "download", None, check, show)

    def install_ports(self, chosen, extra_runtimes=(), portmaster=None):
        """Dépose les ports dans autoinstall et ajoute les runtimes manquants (la console n'a pas de Wi-Fi).
        portmaster : nouvelle version de PortMaster à déposer aussi (il se met à jour au lancement)."""
        root = self.root_path
        runtimes = ports.missing_runtimes(root, chosen)
        runtimes += [rt for rt in extra_runtimes if rt[0] not in {r[0] for r in runtimes}]
        jobs = [(p.title, p.size, lambda r, c, p=p: ports.download(root, p, r, c)) for p in chosen]
        jobs += [(rt[0], rt[3], lambda r, c, rt=rt: ports.download_runtime(root, rt, r, c)) for rt in runtimes]
        if portmaster:
            jobs.append(("PortMaster", portmaster[3],
                         lambda r, c: ports.download_portmaster(root, portmaster, r, c)))

        def work(report, cancel):
            errors, ok = [], 0
            for i, (name, size, fetch) in enumerate(jobs):
                if cancel.is_set():
                    break
                report(i, _("Téléchargement : {name}", name=name))
                progress = lambda done, i=i, name=name, size=size: report(
                    i, _("Téléchargement : {name}", name=name) + f"  ·  {human(done)} / {human(size)}")
                try:
                    ok += bool(fetch(progress, cancel))
                except OSError as e:
                    errors.append(f"{name} : {e}")
            return ok, errors

        def done(result):
            ok, errors = result
            self.refresh_usage()
            if ok and (chosen or portmaster):
                text = (_n(len(chosen), "{n} port est prêt à être installé.", "{n} ports sont prêts à être installés.")
                        if chosen else "")
                if portmaster:
                    text = (text + "\n" if text else "") + _("La nouvelle version de PortMaster est prête.")
                if runtimes:
                    text += "\n" + _n(len(runtimes), "{n} bibliothèque nécessaire a aussi été ajoutée.",
                                       "{n} bibliothèques nécessaires ont aussi été ajoutées.")
                info(self, _("Ports PortMaster"), text,
                     _("Remets la carte dans la console et lance PortMaster (dans Ports ou Options) : il installe "
                       "les ports déposés, qui apparaissent ensuite dans la liste Ports."))
            elif ok:
                self.flash(_n(ok, "{n} bibliothèque ajoutée", "{n} bibliothèques ajoutées"), T.GREEN)
            self._errors(errors, _("Certains téléchargements ont échoué :"))

        label = (_n(len(chosen), "Installation de {n} port", "Installation de {n} ports") if chosen
                 else _("Mise à jour de PortMaster") if portmaster
                 else _n(len(runtimes), "Installation de {n} bibliothèque", "Installation de {n} bibliothèques"))
        self.run_in_background(_("Installation des ports"), "download", len(jobs), work, done, label)

    def install_port_zips(self, files=None):
        """Dépose des ports déjà téléchargés (.zip d'itch.io, de Discord…) dans autoinstall."""
        if files is None:
            files = filedialog.askopenfilenames(parent=self, title=_("Ports à installer"),
                                                filetypes=[(_("Archives de ports"), "*.zip")])
        if not files:
            return
        good = [f for f in files if ports.is_port_zip(f)]
        bad = [os.path.basename(f) for f in files if f not in good]
        root = self.root_path

        def work(report, cancel):
            errors = []
            for i, f in enumerate(good):
                if cancel.is_set():
                    break
                report(i, os.path.basename(f))
                try:
                    ports.add_zip(root, f)
                except OSError as e:
                    errors.append(f"{os.path.basename(f)} : {e}")
            return errors

        def done(errors):
            self.refresh_usage()
            n = len(good) - len(errors)
            if n:
                info(self, _("Ports PortMaster"),
                     _n(n, "{n} port est prêt à être installé.", "{n} ports sont prêts à être installés."),
                     _("Remets la carte dans la console et lance PortMaster (dans Ports ou Options) : il installe "
                       "les ports déposés, qui apparaissent ensuite dans la liste Ports."))
            self._errors(errors, _("Certains fichiers n'ont pas pu être copiés :"))

        if bad:
            info(self, _("Ports PortMaster"), _("Ces archives ne sont pas des ports PortMaster :"), "\n".join(bad))
        if good:
            self.run_in_background(_("Installation des ports"), "download", len(good), work, done,
                                   _n(len(good), "Installation de {n} port", "Installation de {n} ports"))

    def pending_ports(self):
        """Ports déposés dans autoinstall et pas encore installés par PortMaster : on peut en retirer."""
        files = ports.pending_files(self.root_path)
        if not files:
            info(self, _("Ports en attente"), _("Aucun port n'attend d'être installé."))
            return
        items = [(os.path.basename(f), "", False, core.path_size(f)) for f in files]
        chosen = ChecklistDialog(self, _("Ports en attente"), "trash",
                                 _("Ces ports seront installés au prochain lancement de PortMaster sur la console. "
                                   "Coche ceux que tu ne veux plus installer : ils passent par la corbeille."),
                                 items, _("RETIRER"), "danger").show()
        if not chosen:
            return
        gone = [files[i] for i in chosen]

        def work(report, cancel):
            errors = []
            for i, f in enumerate(gone):
                report(i, os.path.basename(f))
                try:
                    journal.remove(f)
                except OSError as e:
                    errors.append(f"{os.path.basename(f)} : {e}")
            return errors

        def done(errors):
            self.refresh_usage()
            self.flash(_n(len(gone) - len(errors), "{n} port retiré", "{n} ports retirés"), T.GREEN)
            self._errors(errors)

        self.run_in_background(_("Ports en attente"), "trash", len(gone), work, done,
                               _n(len(gone), "Retrait de {n} port en attente", "Retrait de {n} ports en attente"))

    def open_store(self, url):
        if url:
            webbrowser.open(url)

    @staticmethod
    def needs_port_files(game):
        """Port qui demande les fichiers du jeu original (pas « prêt à jouer »)."""
        if game.system.lower() != "ports":
            return False
        req = ports.requirements(game)
        return bool(req and not req[0] and core.port_dir(game.path))

    def add_port_files(self):
        """Copie les fichiers du jeu original (dossier entier ou fichiers choisis) dans le dossier prévu du port."""
        if len(self.selection) != 1:
            return
        game = self.selection[0]
        target = ports.files_target(game)
        if not target:
            return
        root = self.root_path
        where = os.path.relpath(target, root).replace(os.sep, "/")
        choice = _dialog(self, _("Fichiers du jeu"),
                         _("Les fichiers seront copiés dans {folder}.", folder=where) + "\n"
                         + _("Choisis le dossier du jeu original (tout son contenu est copié) ou seulement "
                             "certains fichiers, comme le demandent les instructions :"),
                         ports.requirements(game)[1],
                         [(_("ANNULER"), "normal", None), (_("FICHIERS…"), "normal", "files"),
                          (_("DOSSIER…"), "normal", "dir")], T.CYAN, "folder")
        if choice == "dir":
            source = filedialog.askdirectory(parent=self, title=_("Dossier du jeu original"))
            files = ports.folder_files(source) if source else []
        elif choice == "files":
            picked = filedialog.askopenfilenames(parent=self, title=_("Fichiers du jeu original"))
            files = [(p, os.path.basename(p)) for p in picked]
        else:
            return
        if not files:
            return
        size = sum(core.path_size(p) for p, _rel in files)

        def work(report, cancel):
            errors, copied = [], 0
            for i, (src, rel) in enumerate(files):
                if cancel.is_set():
                    break
                report(i, rel)
                try:
                    journal.copy(src, os.path.join(target, rel))
                    copied += 1
                except OSError as e:
                    errors.append(f"{rel} : {e}")
            return copied, errors

        def done(result):
            copied, errors = result
            core.clear_cache()
            self.refresh_usage()
            self.show_details()
            self.flash(_n(copied, "{n} fichier copié", "{n} fichiers copiés") + f"  ·  {human(size)}  ·  {where}",
                       T.GREEN)
            self._errors(errors, _("Certains fichiers n'ont pas pu être copiés :"))

        self.run_in_background(_("Fichiers du jeu"), "copy", len(files), work, done,
                               _("Fichiers du jeu : {name}", name=game.name))

    # ------------------------------------------------------------ sauvegardes
    def backup_saves(self):
        files = saves.collect(self.root_path)
        if not files:
            info(self, _("Sauvegardes"), _("Aucune sauvegarde trouvée sur la carte."))
            return
        name = f"R36S-{_('sauvegardes')}-{datetime.date.today():%Y-%m-%d}.zip"
        dest = filedialog.asksaveasfilename(parent=self, title=_("Enregistrer les sauvegardes"), initialfile=name,
                                            defaultextension=".zip", filetypes=[(_("Archive zip"), "*.zip")])
        if not dest:
            return
        root = self.root_path

        def done(count):
            self.flash(_n(count, "{n} sauvegarde copiée dans {file}", "{n} sauvegardes copiées dans {file}",
                          file=os.path.basename(dest)), T.GREEN)
            info(self, _("Sauvegardes"), _n(count, "{n} fichier de sauvegarde a été copié dans :\n{file}",
                                            "{n} fichiers de sauvegarde ont été copiés dans :\n{file}", file=dest))

        self.run_in_background(_("Sauvegarde des parties"), "save", len(files),
                               lambda report, cancel: saves.backup(root, files, dest, report, cancel), done)

    def restore_saves(self):
        src = filedialog.askopenfilename(parent=self, title=_("Choisir une sauvegarde à restaurer"),
                                         filetypes=[(_("Archive zip"), "*.zip")])
        if not src:
            return
        choice = _dialog(self, _("Restaurer"), _("Que faire si une sauvegarde existe déjà sur la carte ?"), "",
                         [(_("ANNULER"), "normal", None), (_("GARDER CELLE DE LA CARTE"), "normal", False),
                          (_("REMPLACER"), "danger", True)], T.YELLOW, "save")
        if choice is None:
            return
        root = self.root_path

        def done(result):
            restored, skipped = result
            self.flash(_n(restored, "{n} sauvegarde restaurée", "{n} sauvegardes restaurées"), T.GREEN)
            info(self, _("Restauration"), _n(restored, "{n} sauvegarde restaurée, {skipped} ignorée(s).",
                                             "{n} sauvegardes restaurées, {skipped} ignorée(s).", skipped=skipped))

        self.run_in_background(_("Restauration"), "save", saves.zip_count(src),
                               lambda report, cancel: saves.restore(root, src, choice, report, cancel), done,
                               _("Restauration des parties"))

    # ------------------------------------------------------------ annulation / corbeille
    def refresh_history(self):
        """Met à jour le bouton « annuler » (activé s'il y a une opération à défaire)."""
        hist = journal.history(self.root_path) if self.root_path else []
        self.btn_undo.set_enabled(bool(hist))
        self.undo_tip.text = _("Annuler : {label}", label=hist[0][1]) if hist else _("Rien à annuler")

    def undo_last(self):
        hist = journal.history(self.root_path) if self.root_path else []
        if not hist:
            return
        op_id, label, date, _size = hist[0]
        when = f"{date[8:10]}/{date[5:7]} {date[11:16]}"
        if not _dialog(self, _("Annuler"), _("Défaire « {label} » ({when}) ?", label=label, when=when) + "\n"
                       + _("Les fichiers et les fiches reviennent comme avant cette opération."), "",
                       [(_("NON"), "normal", False), (_("ANNULER L'OPÉRATION"), "danger", True)], T.YELLOW, "undo"):
            return
        root = self.root_path

        def done(errors):
            self.load_drive()  # tout est relu depuis la carte
            self.flash(_("Opération annulée : {label}", label=label), T.GREEN)
            self._errors(errors, _("Certains éléments n'ont pas pu être remis en place :"))

        self.run_in_background(_("Annulation"), "undo", None, lambda report, cancel: journal.undo(root, op_id), done)

    def show_history(self):
        root = self.root_path
        choice = HistoryDialog(self, journal.history(root), journal.trash_size(root)).show()
        if choice == "undo":
            self.undo_last()
        elif choice == "empty":
            size = journal.trash_size(root)
            if _dialog(self, _("Vider la corbeille"), _("{size} seront libérés sur la carte.", size=human(size))
                       + "\n" + _("Les opérations passées ne pourront plus être annulées."), "",
                       [(_("NON"), "normal", False), (_("VIDER"), "danger", True)], T.RED, "trash"):
                def done(_result):
                    self.refresh_history()
                    self.refresh_usage()
                    self.flash(_("Corbeille vidée") + "  ·  " + _("{size} libérés", size=human(size)), T.GREEN)
                self.run_in_background(_("Corbeille"), "trash", None,
                                       lambda report, cancel: journal.empty_trash(root), done)

    # ------------------------------------------------------------ BIOS
    def check_bios(self):
        results = bios.check(self.root_path, list(self.games))
        if not results:
            info(self, _("BIOS"), _("Aucune de tes consoles n'a besoin de BIOS."))
            return
        lines, last, missing = [], None, 0
        for system, desc, level, found, names in results:
            if system != last:
                lines.append((systems.name(system).upper(), "head"))
                last = system
            if found:
                lines.append((f"  ✓  {_(desc)} : {found}", "ok"))
            else:
                bad = level == bios.REQUIRED
                missing += bad
                lines.append((f"  {'✗' if bad else '~'}  {_(desc)} ({_(level)}) : " + _("manquant"),
                              "bad" if bad else "warn"))
                lines.append(("       " + _("un de ces fichiers dans bios/ : {files}", files=", ".join(names[:4])),
                              "muted"))
        intro = (_("Tout est en ordre pour tes consoles.") if not missing else
                 _n(missing, "{n} BIOS requis manquant : les jeux de ces consoles risquent de ne pas démarrer.",
                    "{n} BIOS requis manquants : les jeux de ces consoles risquent de ne pas démarrer."))
        ReportDialog(self, _("Vérification des BIOS"), "chip", intro, lines).show()
