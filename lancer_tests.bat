@echo off
rem Vérifie que tout fonctionne (sur une fausse carte, la vraie n'est jamais touchée).
cd /d "%~dp0"
python -c "import pytest" 2>nul || python -m pip install --user pytest
python -m pytest -q -p no:cacheprovider
pause
