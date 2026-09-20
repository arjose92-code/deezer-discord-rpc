"""Autostart robuste - 4 méthodes pour lancer au démarrage, même en jeu."""
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.resolve()
PYTHONW = sys.executable.replace("python.exe", "pythonw.exe") if "python.exe" in sys.executable else sys.executable
# fallback: try to find pythonw
if not Path(PYTHONW).exists():
    PYTHONW = sys.executable

STARTUP_DIR = Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
STARTUP_BAT = STARTUP_DIR / "DeezerRP.bat"
STARTUP_VBS = STARTUP_DIR / "DeezerRP.vbs"
TASK_NAME = "DeezerRP"

def _bat_content():
    # --autostart indique que c'est un lancement auto (pour --minimized)
    return f'@echo off\r\nstart "" /min "{PYTHONW}" "{BASE / "main.py"}" --minimized --autostart\r\n'

def _vbs_content():
    # VBS masque totalement la console (0 = hidden)
    return f'Set WshShell = CreateObject("WScript.Shell")\r\nWshShell.Run """{PYTHONW}"" ""{BASE / "main.py"}"" --minimized --autostart", 0, False\r\n'

def _task_cmd():
    # schtasks avec délai 10s au logon, plus haut privilège, même si en jeu
    tr = f'"{PYTHONW}" "{BASE / "main.py"}" --minimized --autostart'
    return ["schtasks", "/create", "/tn", TASK_NAME, "/tr", tr, "/sc", "onlogon", "/rl", "HIGHEST", "/f", "/delay", "0000:10"]

# ---------- Registry ----------
def _reg_key():
    try:
        import winreg
        return winreg
    except ImportError:
        return None

def _reg_set(enable=True):
    winreg = _reg_key()
    if not winreg:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if enable:
            cmd = f'"{PYTHONW}" "{BASE / "main.py"}" --minimized --autostart'
            winreg.SetValueEx(key, TASK_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, TASK_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def _reg_exists():
    winreg = _reg_key()
    if not winreg:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, TASK_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

# ---------- Task Scheduler ----------
def _task_exists():
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True, creationflags=flags, encoding="utf-8", errors="replace")
        return r.returncode == 0
    except Exception:
        return False

def _task_set(enable=True):
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if enable:
            # supprime ancienne si existe
            subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, creationflags=flags, encoding="utf-8", errors="replace")
            r = subprocess.run(_task_cmd(), capture_output=True, text=True, creationflags=flags, encoding="utf-8", errors="replace")
            return r.returncode == 0
        else:
            r = subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], capture_output=True, creationflags=flags, encoding="utf-8", errors="replace")
            return True
    except Exception:
        return False

# ---------- Public API ----------
def is_enabled():
    """True si au moins une méthode est active."""
    return STARTUP_BAT.exists() or STARTUP_VBS.exists() or _reg_exists() or _task_exists()

def status_detail():
    return {
        "bat": STARTUP_BAT.exists(),
        "vbs": STARTUP_VBS.exists(),
        "registry": _reg_exists(),
        "task": _task_exists(),
    }

def enable():
    ok = 0
    try:
        STARTUP_DIR.mkdir(parents=True, exist_ok=True)
        STARTUP_BAT.write_text(_bat_content(), encoding="utf-8")
        ok += 1
    except Exception as e:
        print("bat fail", e)
    try:
        STARTUP_VBS.write_text(_vbs_content(), encoding="utf-8")
        ok += 1
    except Exception as e:
        print("vbs fail", e)
    if _reg_set(True):
        ok += 1
    if _task_set(True):
        ok += 1
    return ok > 0

def disable():
    ok = True
    for p in (STARTUP_BAT, STARTUP_VBS):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            ok = False
    _reg_set(False)
    _task_set(False)
    return ok

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--disable", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.enable:
        print("enable", enable(), status_detail())
    elif args.disable:
        print("disable", disable(), status_detail())
    elif args.status:
        print(status_detail(), "enabled=", is_enabled())
    else:
        print(status_detail())
