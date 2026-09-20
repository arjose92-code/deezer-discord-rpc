@echo off
title DeezerRP - Installation des dependances
color 0B
cd /d "%~dp0"
echo ========================================================
echo   DeezerRP PRO - Installation des dependances
echo ========================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] Python introuvable !
  echo Telecharge Python 3.10+ sur https://www.python.org/downloads/
  echo Coche "Add to PATH" pendant l'installation.
  pause
  exit /b 1
)

echo [1/3] Verification de pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
  echo [ERREUR] pip introuvable
  pause
  exit /b 1
)

echo [2/3] Mise a jour de pip...
python -m pip install --upgrade pip --quiet

echo [3/3] Installation des dependances (pypresence, pillow, psutil, pystray, plyer)...
python -m pip install -r requirements.txt
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
python -c "import pypresence, PIL, psutil; print(' - pypresence', pypresence.__version__); print(' - pillow', PIL.__version__); print(' - psutil', psutil.__version__)"
python -c "import pystray; print(' - pystray', pystray.__version__)" 2>nul || echo " - pystray : installe (optionnel)"
python -c "import plyer; print(' - plyer OK')" 2>nul || echo " - plyer : fallback notif tkinter"
echo.
echo Tu peux maintenant lancer DeezerRP avec :
echo   - lancer.bat  (recommande)
echo   - python main.py
echo   - pythonw main.py --minimized (arriere-plan)
echo.
pause
