"""Réglages mémorisés entre deux lancements."""
import settings


def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "FILE", str(tmp_path / "sub" / "settings.json"))
    monkeypatch.setattr(settings, "_values", None)
    assert settings.get("view") == "grid"          # valeur par défaut
    settings.set("view", "list")
    settings.set("panes", [300, 1500])
    settings.save()
    monkeypatch.setattr(settings, "_values", None)  # comme un nouveau lancement
    assert settings.get("view") == "list" and settings.get("panes") == [300, 1500]


def test_broken_settings_file_is_ignored(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    path.write_text("{ pas du json", encoding="utf-8")
    monkeypatch.setattr(settings, "FILE", str(path))
    monkeypatch.setattr(settings, "_values", None)
    assert settings.get("sort") == "name_asc"
