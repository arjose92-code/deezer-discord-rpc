# 📍 HÉBERGE — Où mettre quoi (2 minutes)

> **But :** que ton activité `Écoute Deezer` s'affiche **même PC éteint** (téléphone → Deezer → Last.fm → Cloud → Discord).

---

## 1️⃣ Où tu mets quoi — le seul fichier à remplir

**Fichier : `cloud/config.json`**

1. Dans `cloud/` fais : `copie config.json.example → config.json` (clic droit → copier/coller → renomme)
2. Ouvre `cloud/config.json` avec Bloc-notes

Tu mets ça dedans :

```json
{
  "discord_bot_token": "COLLE TON TOKEN BOT ICI",
  "lastfm_api_key": "COLLE TON API KEY LAST.FM ICI",
  "lastfm_username": "TON_PSEUDO_LASTFM",
  "interval": 5,
  "discord_priority": true,
  "mode": "bot"
}
```

**Où trouver chaque truc :**

| Tu mets | Où tu le trouves | Copie quoi |
|---|---|---|
| `discord_bot_token` | https://discord.com/developers/applications → **New Application** → nom `DeezerRP-Cloud` → **Bot** → **Reset Token** → copie | `MTAxN...` (long) |
| `lastfm_api_key` | https://www.last.fm/api/account/create → Application name `DeezerRP` → **Create** → copie `API key` | `abc123...` |
| `lastfm_username` | Ton pseudo sur https://www.last.fm → en haut à droite | `ton_pseudo` |

**Et tu actives le scrobble (sinon le cloud ne sait rien) :**
Deezer (téléphone + PC) → Paramètres → **Connecter à Last.fm** → Autorise → joue un son → vérifie sur https://www.last.fm/user/TON_PSEUDO → tu vois `Méchant — Maes` en `Now playing`.

---

## 2️⃣ Inviter le bot sur Discord (1 clic)

1. https://discord.com/developers/applications → ton app `DeezerRP-Cloud` → **OAuth2 → URL Generator**
2. Coche `bot` + `applications.commands` → copie l'URL en bas → ouvre-la → **Invite sur ton serveur privé** → Autorise

Sans ça, le bot ne peut pas s'afficher.

---

## 3️⃣ Où tu héberges — choisis UNE option (gratuit 24/7)

### ✅ OPTION 1 — Render.com (le plus simple, 100% gratuit)

1. Pousse `deezer-discord-rpc` sur GitHub :
```bash
git push -u origin master
```
2. Va sur **https://dashboard.render.com → New + → Web Service → Connecte ton repo**
3. Remplis :
   - **Name:** `deezerrp-cloud`
   - **Root Directory:** `cloud`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python server.py`
   - **Plan:** `Free`
4. Clique **Create Web Service** → attends 1 min → logs `▶ Maes — Méchant` → `✓ Connecté Discord`
5. **Anti-sleep** (sinon Render s'endort) : https://uptimerobot.com → Add Monitor → Type `HTTP` → URL `https://deezerrp-cloud.onrender.com` → toutes les 5 min

**Fichier déjà prêt pour Render :** `cloud/render.yaml` (pas besoin de le toucher).

### Option 2 — Fly.io (toujours allumé, gratuit)

```bash
# installe flyctl https://fly.io/docs/hands-on/install-flyctl/
cd cloud
fly launch  # choisis app name, region cdg
fly deploy  # utilise cloud/fly.toml (auto_stop_machines=false)
fly logs    # vois ▶ Maes — Méchant
```

### Option 3 — Ton PC en Docker (reste local mais auto-restart)

```bash
cd cloud
docker build -t deezerrp-cloud .
docker run -d --restart unless-stopped --name deezerrp -v %cd%/config.json:/app/config.json deezerrp-cloud
docker logs -f deezerrp
```

---

## 4️⃣ Vérifier que ça marche PC éteint

1. **Éteins ton PC**
2. Lance Deezer sur **téléphone** → joue `Méchant`
3. Va sur Last.fm → ton profil → tu vois `Now playing`
4. Sur Discord (téléphone ou autre PC) → le **bot** affiche `Écoute Deezer — Méchant par Maes` → c'est ton cloud qui tourne !

Si tu vois `⏸ Rien en lecture — clear` dans les logs → Last.fm ne scrobble pas → revérifie étape 1.

---

## 📁 Résumé où mettre quoi

```
deezer-discord-rpc/
├── cloud/
│   ├── config.json              ← TU METS TES 3 TOKENS ICI (jamais sur GitHub, .gitignore)
│   ├── config.json.example      ← modèle à copier
│   ├── server.py                ← ne touche pas
│   ├── requirements.txt         ← ne touche pas
│   ├── Dockerfile               ← pour Docker/Fly
│   ├── render.yaml              ← pour Render 1-clic
│   └── README.md                ← tuto détaillé
├── config.json                  ← pour le mode local (PC allumé, SMTC)
├── lancer.bat                   ← double-clic local
└── INSTALL.bat                  ← installe tout
```

**Tu ne pousses JAMAIS `cloud/config.json` sur GitHub** (il est dans `.gitignore: cloud/config.json`). Pousse juste le code, et mets les tokens directement dans Render → Environment (plus sûr).

---

## ❓ Besoin d'aide ?

- Bot ne s'allume pas → vérifie `discord_bot_token` + invite OAuth2
- Last.fm vide → rejoue un son Deezer + vérifie scrobble activé
- Render s'endort → ajoute UptimeRobot

Tu veux que je te fasse une vidéo ou un bouton `Deploy to Render` 1-clic ? Dis-moi ton repo GitHub.
