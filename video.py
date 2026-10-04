"""Aperçu vidéo des jeux, lu par VLC (son + accélération matérielle).

VLC doit être installé sur le PC (https://www.videolan.org) avec le module python-vlc.
Sans VLC, available() renvoie False et l'application affiche simplement l'image.
"""
import sys
import tkinter as tk

try:
    import vlc
    _instance = vlc.Instance("--quiet", "--no-video-title-show", "--no-osd")
except (ImportError, OSError, NameError, AttributeError):
    vlc, _instance = None, None

VOLUME = 60  # volume des aperçus (0-100)


def available():
    return _instance is not None


class VideoPreview:
    """Zone vidéo superposée à un cadre (place) ; play() / stop()."""

    def __init__(self, host, over, on_click=None):
        """host : cadre parent ; over : widget recouvert par la vidéo (ex. l'image du jeu)."""
        self.host, self.over = host, over
        self.frame = tk.Frame(host, bg="black", cursor="hand2")
        self.player = _instance.media_player_new() if available() else None
        self.playing = None
        if self.player:
            self.player.video_set_mouse_input(False)  # les clics restent pour l'application
            self.player.video_set_key_input(False)
        if on_click:
            self.frame.bind("<Button-1>", lambda e: on_click())

    def play(self, path, muted=False):
        if not self.player:
            return
        self.frame.place(in_=self.over, x=0, y=0, relwidth=1, relheight=1)
        self.frame.update_idletasks()
        media = _instance.media_new(path)
        media.add_option("input-repeat=65535")  # en boucle, comme sur la console
        self.player.set_media(media)
        if sys.platform.startswith("win"):
            self.player.set_hwnd(self.frame.winfo_id())
        else:
            self.player.set_xwindow(self.frame.winfo_id())
        self.player.play()
        self.set_muted(muted)
        self.playing = path

    def set_muted(self, muted):
        if self.player:
            self.player.audio_set_volume(VOLUME)
            self.player.audio_set_mute(muted)

    def stop(self):
        if self.player and self.playing:
            self.player.stop()
        self.playing = None
        self.frame.place_forget()

    def release(self):
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None
