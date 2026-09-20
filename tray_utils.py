"""Tray + notifications pour DeezerRP — tourne en arrière-plan même en jeu."""
import threading
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

def create_icon_image(size=64):
    """Génère une icône 64x64 blurple avec ♪ comme les apps premium (Spotify/Discord)."""
    if not HAS_PIL:
        return None
    try:
        # fond blurple #5865f2 avec coins arrondis
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # fond arrondi
        draw.rounded_rectangle((0, 0, size, size), radius=14, fill=(88, 101, 242, 255))
        # note
        # essaie de charger une font, sinon fallback
        try:
            # Segoe UI si dispo
            font = ImageFont.truetype("seguisym.ttf", 32)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 30)
            except:
                font = ImageFont.load_default()
        # centre la note
        text = "♪"
        # get bbox
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except:
            w, h = (20, 20)
        draw.text(((size - w) // 2, (size - h) // 2 - 2), text, fill="white", font=font)
        # petit point vert LIVE en haut à droite
        draw.ellipse((size - 18, 8, size - 8, 18), fill=(35, 165, 90, 255), outline=(255, 255, 255, 255), width=2)
        return img
    except Exception as e:
        print("icon fail", e)
        return None

# ---------- Notifications ----------
def _notify_plyer(title, msg):
    try:
        from plyer import notification
        notification.notify(title=title, message=msg, app_name="DeezerRP", timeout=4)
        return True
    except Exception:
        return False

def _notify_pystray(icon, title, msg):
    try:
        if icon and hasattr(icon, "notify"):
            icon.notify(msg, title)
            return True
    except Exception:
        pass
    return False

def _notify_win10toast(title, msg):
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, msg, duration=4, threaded=True)
        return True
    except Exception:
        return False

def _notify_powershell(title, msg):
    """Fallback sans dépendance : PowerShell BurntToast ou balloon via WScript."""
    try:
        import subprocess
        # Essaie BurntToast si installé, sinon fallback silencieux
        ps = f'powershell -NoProfile -Command "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null; $t=[Windows.Data.Xml.Dom.XmlDocument]::new(); $t.LoadXml(@\"<toast><visual><binding template=\\\'ToastGeneric\\\'><text>{title}</text><text>{msg}</text></binding></visual></toast>\"@); [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(\\\'DeezerRP\\\').Show([Windows.UI.Notifications.ToastNotification]::new($t))"'
        subprocess.Popen(ps, shell=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except Exception:
        return False

def notify(title, msg, icon=None, fallback_tk=None):
    """Essaie plyer > pystray > win10toast > powershell > tkinter toast."""
    if _notify_plyer(title, msg):
        return True
    if icon and _notify_pystray(icon, title, msg):
        return True
    if _notify_win10toast(title, msg):
        return True
    # fallback tkinter toast si fourni
    if fallback_tk:
        try:
            fallback_tk(title, msg)
            return True
        except Exception:
            pass
    # dernier recours powershell
    _notify_powershell(title, msg)
    return True

# ---------- Tray ----------
class TrayManager:
    def __init__(self, app):
        self.app = app
        self.icon = None
        self.thread = None
        self.running = False

    def _menu(self):
        """Construit le menu tray."""
        try:
            import pystray
            from pystray import MenuItem as item
            # état
            is_live = getattr(self.app, "auto_on", False) and getattr(self.app, "connected", False)
            track = getattr(self.app, "current_track", None)
            track_label = f"▶ {track['artist']} — {track['title']}"[:32] if track else "Aucune lecture"
            # priorité Discord : check v_discord_prio si dispo, sinon v_prio
            prio_on = False
            if hasattr(self.app, "v_discord_prio") and self.app.v_discord_prio:
                try: prio_on = bool(self.app.v_discord_prio.get())
                except: prio_on = False
            elif hasattr(self.app, "v_prio") and self.app.v_prio:
                try: prio_on = bool(self.app.v_prio.get())
                except: prio_on = False

            return pystray.Menu(
                item(f"DeezerRP PRO  •  {track_label}", None, enabled=False),
                pystray.Menu.SEPARATOR,
                item("▶ Afficher DeezerRP", self.on_show, default=True),
                item("⏸ Mettre en pause" if is_live else "▶ Reprendre", self.on_toggle),
                item("⚡ Priorité Discord : ON" if prio_on else "⚡ Priorité Discord : OFF", self.on_prio),
                pystray.Menu.SEPARATOR,
                item("↗ Mettre à jour", self.on_update),
                item("✕ Effacer statut", self.on_clear),
                pystray.Menu.SEPARATOR,
                item("❌ Quitter", self.on_quit),
            )
        except Exception as e:
            print("tray menu fail", e)
            return None

    def on_show(self, icon=None, item=None):
        try:
            # réveille la fenêtre
            self.app.root.after(0, self.app.show_from_tray)
        except Exception as e:
            print("on_show fail", e)

    def on_toggle(self, icon=None, item=None):
        try:
            # toggle auto
            self.app.root.after(0, lambda: self.app.toggle_auto_from_tray())
        except: pass

    def on_prio(self, icon=None, item=None):
        try:
            # priorité Discord, pas Windows
            if hasattr(self.app, "toggle_discord_priority"):
                self.app.root.after(0, self.app.toggle_discord_priority)
            elif hasattr(self.app, "toggle_priority"):
                self.app.root.after(0, self.app.toggle_priority)
            # refresh menu
            self.update_menu()
        except: pass

    def on_update(self, icon=None, item=None):
        try:
            self.app.root.after(0, self.app.send_fields)
        except: pass

    def on_clear(self, icon=None, item=None):
        try:
            self.app.root.after(0, self.app.clear_presence)
        except: pass

    def on_quit(self, icon=None, item=None):
        try:
            self.app.root.after(0, self.app.really_quit)
        except: pass
        self.stop()

    def update_menu(self):
        try:
            if self.icon:
                self.icon.menu = self._menu()
                self.icon.update_menu()
        except: pass

    def run(self):
        if self.running:
            return
        self.running = True
        try:
            import pystray
            image = create_icon_image(64)
            if image is None:
                # fallback: crée une image vide
                from PIL import Image
                image = Image.new("RGBA", (64, 64), (88, 101, 242, 255))
            self.icon = pystray.Icon("DeezerRP", image, "DeezerRP — Deezer → Discord", menu=self._menu())
            # lance en thread daemon
            self.thread = threading.Thread(target=self.icon.run, daemon=True)
            self.thread.start()
            # petite notif de démarrage
            self.icon.notify("DeezerRP tourne en arrière-plan", "♪ Activité Discord prioritaire")
        except Exception as e:
            print("Tray pystray fail, fallback sans tray:", e)
            self.icon = None
            self.running = False

    def stop(self):
        self.running = False
        try:
            if self.icon:
                self.icon.stop()
        except: pass
        self.icon = None

    def notify(self, title, msg):
        # essaie via pystray, sinon plyer
        if self.icon and _notify_pystray(self.icon, title, msg):
            return
        _notify_plyer(title, msg)

