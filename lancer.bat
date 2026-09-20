@echo off
chcp 65001 >nul 2>&1
title DeezerRP PRO
cd /d "%~dp0"
:: Detection python/py + pythonw
set PY=python
set PYW=pythonw
%PY% --version >nul 2>&1
if errorlevel 1 (
  set PY=py
  set PYW=pyw
)
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Python introuvable : https://www.python.org/downloads/
  echo Installe Python 3.10+ et coche "Add to PATH"
  pause
  exit /b 1
)
%PY% -c "import pypresence, PIL" >nul 2>&1
if errorlevel 1 (
  echo Installation des dependances...
  %PY% -m pip install --quiet -r requirements.txt
  if errorlevel 1 (
    echo [ERREUR] Echec installation. Lance INSTALL.bat
    pause
    exit /b 1
  )
)
:: Priorite haute meme en jeu : priority.py HIGH_PRIORITY_CLASS
:: Lancement silencieux (pythonw = sans console, CREATE_NO_WINDOW)
if exist "%PYW%.exe" (
  start "" "%PYW%" main.py
) else (
  start "" %PYW% main.py
)
exit /b 0
