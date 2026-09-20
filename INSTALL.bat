@echo off
chcp 65001 >nul 2>&1
title DeezerRP - Installation des dependances
color 0B
cd /d "%~dp0"
:: Detection python/py
set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Python introuvable - installe Python 3.10+ depuis https://www.python.org/downloads/
  pause
  exit /b 1
)
set PIP=%PY% -m pip
echo ========================================================
echo   DeezerRP PRO - Installation des dependances
echo ========================================================
echo.

echo [1/3] Verification de pip...
%PIP% --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] pip introuvable - reinstalle Python avec pip
  pause
  exit /b 1
)

echo [2/3] Mise a jour de pip...
%PIP% install --upgrade pip --quiet

echo [3/3] Installation des dependances (pypresence, pillow, psutil, pystray, plyer)...
%PIP% install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERREUR] Echec de l'installation.
  echo Essaie manuellement : pip install -r requirements.txt
  pause
  exit /b 1
)

echo.
echo ========================================================
echo   Installation reussie !
echo ========================================================
echo.
echo Dependances installees :
%PY% -c "import pypresence, PIL, psutil; print(' - pypresence', pypresence.__version__); print(' - pillow', PIL.__version__); print(' - psutil', psutil.__version__)"
%PY% -c "import pystray; print(' - pystray', pystray.__version__)" 2>nul || echo " - pystray : installe (optionnel)"
%PY% -c "import plyer; print(' - plyer OK')" 2>nul || echo " - plyer : fallback notif tkinter"
echo.
echo Tu peux maintenant lancer DeezerRP avec :
echo   - lancer.bat  (recommande)
echo   - python main.py
echo   - pythonw main.py --minimized (arriere-plan)
echo.
pause
