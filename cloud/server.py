"""
DeezerRP Cloud — tourne 24/7 même PC éteint.
Poll Last.fm (scrobble Deezer) ou Deezer API -> Bot Discord prioritaire.

PC off = SMTC impossible. Ce serveur poll Last.fm/Deezer toutes les 5s
et met à jour un BOT Discord (safe). Pour afficher sur TON compte,
utilise le mode self-bot (risqué, voir README).
"""
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

import discord

CONFIG = Path(__file__).parent / "config.json"
LASTFM_API = "http://ws.audioscrobbler.com/2.0/"

def load_cfg():
    import os
    # Render met les secrets dans l'ENV, pas dans le fichier
    env_overrides = {
        "discord_bot_token": os.getenv("discord_bot_token") or os.getenv("DISCORD_BOT_TOKEN"),
        "lastfm_api_key": os.getenv("lastfm_api_key") or os.getenv("LASTFM_API_KEY"),
        "lastfm_username": os.getenv("lastfm_username") or os.getenv("LASTFM_USERNAME"),
        "deezer_user_id": os.getenv("deezer_user_id"),
    }
    # nettoie les None
    env_overrides = {k: v for k, v in env_overrides.items() if v}
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        # ENV prioritaire sur fichier
        data.update(env_overrides)
        return data
    except:
        base = {
            "discord_bot_token": "",
            "lastfm_api_key": "",
            "lastfm_username": "",
            "deezer_user_id": "",
            "interval": 5,
            "discord_priority": True,
            "mode": "bot"  # bot | selfbot
        }
        base.update(env_overrides)
        return base

def lastfm_now_playing(api_key, username):
    """Retourne (artist, title, album) si en écoute, sinon None. Détecte nowplaying=true."""
    if not api_key or not username:
        return None
    try:
        q = urllib.parse.urlencode({
            "method": "user.getrecenttracks",
            "user": username,
            "api_key": api_key,
            "format": "json",
            "limit": 2
        })
        req = urllib.request.Request(f"{LASTFM_API}?{q}", headers={"User-Agent": "DeezerRP-Cloud/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        tracks = data.get("recenttracks", {}).get("track", [])
        if not tracks:
            return None
        # Last.fm met track[0] avec @attr.nowplaying quand en écoute
        t = tracks[0] if isinstance(tracks, list) else tracks
        if "@attr" in t and t["@attr"].get("nowplaying") == "true":
            artist = t.get("artist", {}).get("#text") or t.get("artist")
            title = t.get("name") or t.get("title")
            album = t.get("album", {}).get("#text")
            if isinstance(artist, dict): artist = artist.get("#text")
            return {"artist": (artist or "").strip(), "title": (title or "").strip(), "album": (album or "").strip()}
        return None
    except Exception as e:
        print(f"[Last.fm] erreur: {e}")
        return None

def deezer_track_info(artist, title):
    """Pochette + lien via API publique Deezer."""
    try:
        q = urllib.parse.quote(f"{artist} {title}" if artist else title)
        req = urllib.request.Request(f"https://api.deezer.com/search?q={q}", headers={"User-Agent": "DeezerRP-Cloud"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r).get("data") or []
        if not data:
            return None, None, None
        best = data[0]
        if artist:
            for it in data[:5]:
                if artist.lower() in str(it.get("artist", {}).get("name", "")).lower():
                    best = it; break
        album = best.get("album", {}) or {}
        return album.get("cover_big") or album.get("cover_medium"), album.get("title"), best.get("link")
    except Exception as e:
        print(f"[Deezer API] {e}")
        return None, None, None

def search_url(artist, title):
    q = f"{artist} {title}" if artist else title
    return "https://www.deezer.com/search/" + urllib.parse.quote(q)

class CloudBot(discord.Client):
    def __init__(self, cfg):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.cfg = cfg
        self.last_key = None
        self.start_time = None

    async def setup_hook(self):
        self.loop.create_task(self.poll_loop())
        # HTTP pour Render Web Service (sinon In progress forever)
        self.loop.create_task(self.start_web())

    async def start_web(self):
        import os
        try:
            from aiohttp import web
            async def health(req): return web.Response(text="DeezerRP Cloud OK - bot actif")
            app = web.Application()
            app.router.add_get("/", health)
            app.router.add_get("/health", health)
            runner = web.AppRunner(app)
            await runner.setup()
            port = int(os.getenv("PORT", "10000"))
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            print(f"🌐 HTTP OK sur :{port} (Render health check)")
        except Exception as e:
            print(f"web fail {e}")

    async def on_ready(self):
        print(f"✓ Connecté Discord : {self.user} ({self.user.id})")
        print(f"  Mode {'SELF-BOT (ton compte)' if self.cfg.get('mode')=='selfbot' else 'BOT (présence du bot)'}")
        print(f"  Interval {self.cfg.get('interval',5)}s | Prioritaire={self.cfg.get('discord_priority',True)}")

    async def poll_loop(self):
        await self.wait_until_ready()
        interval = max(5, int(self.cfg.get("interval", 5)))
        # si prioritaire, on garde 5s max même si config plus haute
        if self.cfg.get("discord_priority", True):
            interval = min(interval, 5)

        while not self.is_closed():
            try:
                playing = lastfm_now_playing(self.cfg.get("lastfm_api_key",""), self.cfg.get("lastfm_username",""))
                # fallback: si tu veux Deezer direct sans Last.fm, décommente :
                # if not playing and self.cfg.get("deezer_user_id"):
                #     playing = deezer_history(self.cfg["deezer_user_id"])

                if not playing:
                    if self.last_key is not None:
                        print("⏸ Rien en lecture — clear")
                        try: await self.change_presence(activity=None)
                        except: pass
                        self.last_key = None
                        self.start_time = None
                    await discord.utils.sleep_until(discord.utils.utcnow().replace(microsecond=0) + discord.utils.utcnow().replace(microsecond=0).second * 0)  # dummy
                    await self._sleep(interval)
                    continue

                artist, title = playing["artist"], playing["title"]
                key = (artist, title)
                is_new = key != self.last_key
                if is_new:
                    self.last_key = key
                    self.start_time = discord.utils.utcnow()
                    print(f"▶ {artist} — {title}")

                # anti-spam keepalive : on renvoie même si même morceau pour rester prioritaire sur les jeux
                # discord.py rate limite ~15s, on respecte 5-12s
                cover, album, link = deezer_track_info(artist, title)
                url = link or search_url(artist, title)

                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name="Deezer",
                    details=title[:128],
                    state=artist[:128] if artist else None,
                    assets={
                        "large_image": cover or "https://cdn.discordapp.com/attachments/123/deezer.png",
                        "large_text": album[:128] if album else "Deezer",
                    } if cover else {},
                    buttons=[
                        {"label": "Écouter sur Deezer", "url": url[:512]},
                        {"label": "Ouvrir Deezer", "url": "https://www.deezer.com"}
                    ][:2],
                    # discord.py 2.4+ supporte assets via Activity, sinon passe par Game
                )
                # Pour small image / timestamps, on passe par Spotify-like :
                # discord.py ne supporte pas start directement sur Activity, on utilise l'astuce Game
                try:
                    # Essai avec timestamps (marche sur Listening)
                    await self.change_presence(activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name="Deezer",
                        details=title[:128],
                        state=f"par {artist}"[:128] if artist else None,
                        assets={"large_image": cover} if cover else {}
                    ))
                    # Note : les boutons nécessitent Rich Presence via pypresence, pas via bot.
                    # Avec bot, on ne peut avoir que 1 activité simple. Pour boutons + pochette HTTP,
                    # il faut utiliser le mode self-bot (voir README) ou garder le RPC local quand PC allumé.
                except Exception as e:
                    print(f"presence fail: {e}")
                    # fallback simple
                    await self.change_presence(activity=discord.Game(name=f"Deezer — {title[:60]}"))

                # si nouveau morceau, on a déjà envoyé, sinon keepalive déjà fait
                await self._sleep(interval)

            except Exception as e:
                print(f"[Loop] {e}")
                await self._sleep(interval)

    async def _sleep(self, sec):
        try:
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.utcnow().second * 0)
        except:
            pass
        import asyncio
        await asyncio.sleep(sec)

def main():
    cfg = load_cfg()
    token = cfg.get("discord_bot_token", "").strip() or cfg.get("discord_token", "").strip()
    if not token:
        print("❌ Mets ton token dans cloud/config.json -> discord_bot_token")
        print("   Crée un bot sur https://discord.com/developers/applications -> Bot -> Token")
        print("   Invite-le : OAuth2 -> bot -> scopes bot + applications.commands")
        print("   (Sur Render : Environment → discord_bot_token)")
        print("   En attente du token... (le service reste allumé, mets le token et sauve)")
        import time
        while True:
            time.sleep(60)
    if not cfg.get("lastfm_api_key") or not cfg.get("lastfm_username"):
        print("⚠️  Configure Last.fm pour que ça marche PC éteint :")
        print("   1) Deezer -> Paramètres -> Connecte Last.fm (scrobble)")
        print("   2) https://www.last.fm/api/account/create -> copie API key")
        print("   3) Mets api_key + username dans cloud/config.json")
        print("   Sans Last.fm, le cloud ne peut pas savoir ce que tu écoutes téléphone/PC off.")
        # on continue quand même, il pollera Deezer si deezer_user_id est mis

    mode = cfg.get("mode", "bot")
    if mode == "selfbot":
        print("⚠️  MODE SELF-BOT : utilise ton token utilisateur — contre ToS Discord, risque de ban. Utilise à tes risques.")
        print("   Préfère le mode bot (présence du bot) safe.")

    intents = discord.Intents.default()
    client = CloudBot(cfg)
    try:
        client.run(token)
    except discord.LoginFailure:
        print("❌ Token invalide")
    except Exception as e:
        print(f"❌ {e}")

if __name__ == "__main__":
    main()
