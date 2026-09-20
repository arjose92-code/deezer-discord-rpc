"""DeezerRP - lance l'interface premium (support --minimized --autostart)."""
import sys

# Boost priorité très tôt, même avant tkinter (reste actif en jeu)
try:
    import priority as prio
    # on tente de lire config sans gui
    import json
    from pathlib import Path
    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        if cfg.get("priority_high", True):
            prio.boost(True)
    else:
        prio.boost(True)
except Exception:
    pass

# Si lancé via python.exe, cache la console immédiatement
try:
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
except Exception:
    pass

from gui import main

if __name__ == "__main__":
    main()
