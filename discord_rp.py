"""DeezerRP - client Discord Rich Presence (mode Ecoute + pochette)."""
from pypresence import Presence
from pypresence.types import ActivityType

TYPES = {
    "Ecoute": ActivityType.LISTENING,
    "Joue": ActivityType.PLAYING,
    "Regarde": ActivityType.WATCHING,
}


class DeezerPresence:
    def __init__(self, client_id):
        self.client_id = str(client_id).strip()
        self.rpc = None

    @property
    def connected(self):
        return self.rpc is not None

    def connect(self):
        self.disconnect()
        self.rpc = Presence(self.client_id)
        self.rpc.connect()

    def disconnect(self):
        if self.rpc is not None:
            try:
                self.rpc.clear()
            except Exception:
                pass
            try:
                self.rpc.close()
            except Exception:
                pass
            self.rpc = None

    def update(self, activity="Ecoute", name="Deezer", details=None,
               state=None, start=None, large_image=None, large_text=None,
               small_image=None, small_text=None, buttons=None):
        payload = {
            "activity_type": TYPES.get(activity, ActivityType.LISTENING),
            "name": name or "Deezer",
            "details": details,
            "state": state,
        }
        if start:
            payload["start"] = start
        if large_image:
            payload["large_image"] = large_image
            if large_text:
                payload["large_text"] = large_text
        if small_image:
            payload["small_image"] = small_image
            if small_text:
                payload["small_text"] = small_text
        if buttons:
            payload["buttons"] = buttons
        try:
            return self.rpc.update(**payload)
        except Exception as e:
            msg = str(e).lower()
            if "asset" not in msg and "image" not in msg:
                raise
            # Cle d'asset perso introuvable sur le portail Discord :
            # on garde l'URL http (pochette) mais on vire les cles d'asset.
            if large_image and not large_image.startswith("http"):
                payload.pop("large_image", None)
                payload.pop("large_text", None)
            if small_image and not str(small_image).startswith("http"):
                payload.pop("small_image", None)
                payload.pop("small_text", None)
            return self.rpc.update(**payload)
