# DeezerRP Cloud — PC éteint = toujours en ligne

> **Pourquoi ?** `deezer.py` et `discord_rp.py` lisent la session Windows locale (`SMTC` + pipe Discord). **PC éteint = rien ne tourne**. Pour afficher Deezer même téléphone/PC off, il faut un service hébergé 24/7 qui poll Last.fm/Deezer.

## Comment ça marche

```
Deezer (téléphone/PC) --scrobble--> Last.fm --poll toutes les 5s--> cloud/server.py --update--> Discord Bot (présence)
```

- Deezer mobile/PC scrobble automatiquement vers Last.fm (une fois activé, ça marche même PC off)
- `cloud/server.py` poll `Last.fm user.getRecentTracks` (`nowplaying=true`) + récupère pochette via `api.deezer.com`
- Met à jour la présence d'un **BOT Discord** en `Écoute Deezer — Titre par Artiste` (prioritaire 5s keepalive, comme le local)

> **Important :** Un bot montre l'activité du **bot**, pas de ton compte perso. Pour afficher sur ton compte perso PC off, il faudrait un self-bot (token utilisateur) → **contre ToS, risque de ban**. On recommande le bot safe + tu laisses le bot dans un serveur privé.

## Installation hébergement

### 1) Préparer Last.fm (1 fois)
1. Deezer → Paramètres → Connecter à Last.fm → autorise le scrobble
2. https://www.last.fm/api/account/create → crée une API → copie `API key`
3. Note ton `username` Last.fm

### 2) Créer le bot Discord
1. https://discord.com/developers/applications → New Application → `DeezerRP-Cloud`
2. Bot → Reset Token → copie le token
3. OAuth2 → URL Generator → scopes `bot` + `applications.commands` → copie l'URL → invite le bot sur ton serveur privé

### 3) Configurer
```bash
cd cloud
cp config.json.example config.json
# édite config.json :
# discord_bot_token = token du bot
# lastfm_api_key + lastfm_username
# interval 5, discord_priority true, mode bot
```

### 4) Héberger 24/7

**Option A — Docker (VPS, Raspberry Pi, maison)**
```bash
docker build -t deezerrp-cloud ./cloud
docker run -d --restart unless-stopped --name deezerrp -v ./cloud/config.json:/app/config.json deezerrp-cloud
docker logs -f deezerrp
```

**Option B — Gratuit Render / Fly.io / Oracle**
- Render : New Web Service → connecte ton repo GitHub → Root Directory `cloud` → Start Command `python server.py` → ajoute `config.json` en Secret File
- Fly.io : `fly launch` dans `cloud/` → `fly deploy`

**Option C — Ton PC mais avec `pm2` (reste local)**
```bash
pip install -r cloud/requirements.txt
pm2 start cloud/server.py --name deezerrp-cloud
```

## Vérifier

Logs : `▶ Maes — Méchant` toutes les 5s + présence du bot qui passe à `Écoute Deezer`.
Si `⏸ Rien en lecture — clear` → vérifie que Deezer scrobble bien vers Last.fm (joue un son sur téléphone).

## Mode self-bot (ton compte, risqué)
```json
{ "mode": "selfbot", "discord_bot_token": "TON_TOKEN_UTILISATEUR" }
```
Récupère ton token via `Ctrl+Shift+I` → Application → Local Storage → `token` → **risque de ban Discord, déconseillé**.

## Limites

- Sans Last.fm scrobble, le cloud ne sait pas ce que tu écoutes téléphone (Deezer API publique n'a pas de nowplaying temps réel sans auth).
- Les boutons `Écouter sur Deezer` avec pochette HTTP ne marchent qu'en Rich Presence local (`pypresence`), pas via bot (Discord bot ne supporte pas les boutons avec image HTTP). Le cloud met à jour le `details/state` + grosse image si possible.

## Fichiers

```
cloud/server.py      → bot + poll Last.fm
cloud/config.json    → token + lastfm
cloud/Dockerfile     → pour hébergement
cloud/requirements.txt
```
