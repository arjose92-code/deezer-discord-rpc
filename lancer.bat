@echo off
title DeezerRP PRO
cd /d "%~dp0"
:: Boost priorité & autostart gérés par l'app (autostart.py + priority.py)
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Python introuvable : https://www.python.org/downloads/
  pause
  exit /b 1
)
python -c "import pypresence, PIL" >nul 2>&1
if errorlevel 1 (
  echo Installation des dependances...
  python -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo [ERREUR] Echec installation.
    pause
    exit /b 1
  )
)
:: Priorité haute même en jeu : on passe par priority.py (HIGH_PRIORITY_CLASS)
:: Lancement silencieux (pythonw = sans console, CREATE_NO_WINDOW pour le polling)
start "" pythonw main.py
exit /b 0
