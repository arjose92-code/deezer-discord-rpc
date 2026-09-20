# 📦 TOUT CE QUE TU METS SUR L'HÉBERGEUR (Render / Fly / VPS)

> Tu upload **uniquement le dossier `cloud/`** — rien d'autre. Voilà exactement quoi mettre où.

---

## 📁 Dossier à uploader : `cloud/`

Quand tu vas sur **Render.com → New Web Service → Connecte ton repo**, tu mets :
**Root Directory = `cloud`**

Ça veut dire que Render ne voit que ça :

```
cloud/
├── server.py              ← NE TOUCHE PAS (poll Last.fm → Discord)
├── requirements.txt       ← NE TOUCHE PAS (discord.py pillow)
├── Dockerfile             ← NE TOUCHE PAS (pour Docker/Fly)
├── render.yaml            ← NE TOUCHE PAS (config Render)
├── fly.toml               ← NE TOUCHE PAS (config Fly)
├── Procfile               ← NE TOUCHE PAS
└── config.json            ← ★ SEUL FICHIER OÙ TU METS TES INFOS ★
```

---

## ★ SEUL FICHIER À REMPLIR : `cloud/config.json`

**1. Crée-le :** Dans `cloud/`, copie `config.json.example` → renomme `config.json`

**2. Ouvre-le avec Bloc-notes et colle ça (remplace les 3) :**

```json
{
  "discord_bot_token": "MTAxOTYzNjU1NTg0NDAxNTM4... COLLE TON TOKEN BOT ICI",
  "lastfm_api_key": "a1b2c3d4e5f6... COLLE TON API KEY LAST.FM ICI",
  "lastfm_username": "ton_pseudo_lastfm",
  "interval": 5,
  "discord_priority": true,
  "mode": "bot"
}
```

**3. Où tu trouves les 3 trucs à coller :**

| Champ | Où tu le copies | Exemple |
|---|---|---|
| `discord_bot_token` | https://discord.com/developers/applications → **New Application** → nom `DeezerRP-Cloud` → **Bot** → **Reset Token** → **Copy** | `MTAx... (long, 59 caractères)` |
| `lastfm_api_key` | https://www.last.fm/api/account/create → **Application name** `DeezerRP` → **Create** → copie **API key** | `b704...` |
| `lastfm_username` | https://www.last.fm → ton profil en haut à droite → ton pseudo | `jaoua` |

**4. Active le scrobble (obligatoire sinon le cloud ne voit rien) :**
Deezer (sur téléphone **et** PC) → **Paramètres** → **Connecter à Last.fm** → Autorise → joue un son → va sur https://www.last.fm/user/ton_pseudo → tu dois voir `Now playing`.

---

## 🤖 Où tu invites le bot (obligatoire)

1. https://discord.com/developers/applications → ton app `DeezerRP-Cloud` → **OAuth2 → URL Generator**
2. Coche **bot** + **applications.commands**
3. En bas copie l'URL → ouvre-la → choisis **ton serveur privé** → **Autoriser**

Sans ça, le bot ne peut pas afficher `Écoute Deezer`.

---

## ☁️ Où tu héberges — 3 options, tu en choisis 1

### OPTION 1 — Render.com (GRATUIT, 2 clics, recommandé)

**Ce que tu mets sur Render :**

- **Repository :** `TON_USER/deezer-discord-rpc`
- **Root Directory :** `cloud`  ← important
- **Build Command :** `pip install -r requirements.txt`  ← déjà dans `render.yaml`
- **Start Command :** `python server.py`  ← déjà dans `render.yaml`
- **Plan :** `Free`

**Où tu colles tes tokens sur Render (pas dans GitHub) :**

Render → ton service → **Environment** → **Add Environment Variable** :

| Key | Value (tu colles) |
|---|---|
| `discord_bot_token` | `MTAx...` |
| `lastfm_api_key` | `abc...` |
| `lastfm_username` | `ton_pseudo` |

→ **Save Changes** → Render redémarre → **Logs** → `▶ Maes — Méchant` → `✓ Connecté Discord` → c'est en ligne 24/7.

**+ Anti-sleep (obligatoire gratuit) :**
https://uptimerobot.com → **Add New Monitor** → **Monitor Type** `HTTP(s)` → **URL** `https://deezerrp-cloud.onrender.com` → **Interval** `5 minutes` → **Create**.

---

### OPTION 2 — Fly.io (toujours allumé, gratuit)

**Ce que tu mets :** tout le dossier `cloud/` via `flyctl`

```bash
# une fois : https://fly.io/docs/hands-on/install-flyctl/
cd cloud
fly launch  # il lit fly.toml, choisis app name + region cdg
# il te demande si tu veux copier config.json → dis NON (tu mettras les secrets après)
fly secrets set discord_bot_token="MTAx..." lastfm_api_key="abc..." lastfm_username="ton_pseudo"
fly deploy  # utilise Dockerfile + fly.toml
fly logs    # vois ▶ Maes — Méchant
```

---

### OPTION 3 — Docker sur ton VPS / Raspberry

**Ce que tu mets sur le VPS :** tout le dossier `cloud/` en SFTP

```bash
cd cloud
# mets tes 3 tokens dans config.json comme plus haut
docker build -t deezerrp-cloud .
docker run -d --restart unless-stopped --name deezerrp -v $(pwd)/config.json:/app/config.json deezerrp-cloud
docker logs -f deezerrp
```

---

## ✅ Vérif PC éteint

1. **Éteins ton PC**
2. Lance Deezer sur **téléphone** → joue un son
3. Sur https://www.last.fm/user/ton_pseudo → tu vois **Now playing**
4. Sur Discord (téléphone) → le **bot** affiche `Écoute Deezer — Titre par Artiste` → c'est ton cloud !

Si tu vois `⏸ Rien en lecture — clear` dans les logs Render/Fly → Last.fm ne scrobble pas → refais l'étape scrobble.

---

## 📦 Résumé ultra-court : tu mets où

| Fichier | Tu touches ? | Tu mets quoi |
|---|---|---|
| `cloud/server.py` | **NON** | laisse tel quel |
| `cloud/requirements.txt` | **NON** |  |
| `cloud/Dockerfile` | **NON** |  |
| `cloud/render.yaml` | **NON** | Render le lit auto |
| `cloud/fly.toml` | **NON** | Fly le lit auto |
| `cloud/config.json` | **OUI ★** | tes 3 tokens + username |
| **Render → Environment** | **OUI ★** | colle les 3 mêmes tokens (plus sûr que config.json) |

**Tu ne mets JAMAIS `cloud/config.json` sur GitHub** (déjà dans `.gitignore`). Tu le mets seulement sur l'hébergeur.

---

Besoin du bouton 1-clic `Deploy to Render` ? Dis-moi ton repo GitHub et je te le mets dans le README.
