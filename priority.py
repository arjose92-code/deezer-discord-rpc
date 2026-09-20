"""Priorité haute - garde DeezerRP vivant même en jeu (Game Mode)."""
import os
import sys
import threading
import time

HIGH_CLASS = 0x00000080  # HIGH_PRIORITY_CLASS
ABOVE_NORMAL = 0x00008000
NORMAL_CLASS = 0x00000020

def _ctypes_boost(high=True):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        h = kernel32.GetCurrentProcess()
        prio = HIGH_CLASS if high else NORMAL_CLASS
        # Essaye HIGH, fallback ABOVE_NORMAL si refusé
        res = kernel32.SetPriorityClass(h, prio)
        if not res and high:
            kernel32.SetPriorityClass(h, ABOVE_NORMAL)
            return True
        # Empêche Windows de mettre en veille (ExecutionState)
        try:
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
        except Exception:
            pass
        return bool(res)
    except Exception:
        return False

def _psutil_boost(high=True):
    try:
        import psutil
        p = psutil.Process(os.getpid())
        # Windows constants
        if high:
            # HIGH_PRIORITY_CLASS sur Windows, sinon -10 sur Unix
            try:
                p.nice(psutil.HIGH_PRIORITY_CLASS)
            except Exception:
                p.nice(-10)
        else:
            try:
                p.nice(psutil.NORMAL_PRIORITY_CLASS)
            except Exception:
                p.nice(0)
        # Optionnel : I/O priority
        try:
            p.ionice(psutil.IOPRIO_HIGH)
        except Exception:
            pass
        return True
    except ImportError:
        return None
    except Exception:
        return False

def boost(high=True):
    """Passe le processus en priorité haute (reste prioritaire même en jeu)."""
    res = _psutil_boost(high)
    if res is None:
        return _ctypes_boost(high)
    if not res:
        # fallback ctypes si psutil échoue
        return _ctypes_boost(high)
    # même si psutil OK, on double avec ctypes pour ExecutionState
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
    except Exception:
        pass
    return True

def current_priority_name():
    try:
        import psutil
        p = psutil.Process(os.getpid())
        nice = p.nice()
        # Windows: 128=HIGH, 32768=ABOVE_NORMAL etc. On simplifie
        if nice == getattr(psutil, "HIGH_PRIORITY_CLASS", 128):
            return "HAUTE"
        if nice == getattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS", 32768):
            return "SUPÉRIEURE"
        if nice == getattr(psutil, "NORMAL_PRIORITY_CLASS", 32):
            return "NORMALE"
        return str(nice)
    except Exception:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetCurrentProcess()
            prio = kernel32.GetPriorityClass(h)
            m = {0x00000080: "HAUTE", 0x00008000: "SUPÉRIEURE", 0x00000020: "NORMALE", 0x00000040: "IDLE", 0x00000100: "REALTIME"}
            return m.get(prio, str(prio))
        except Exception:
            return "inconnue"

def keep_alive_thread(interval=12, check_fn=None):
    """Thread qui réaffirme la priorité toutes les X sec (Windows peut la rétrograder)."""
    def loop():
        while True:
            time.sleep(interval)
            try:
                if check_fn and not check_fn():
                    continue
                boost(True)
            except Exception:
                pass
    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t
