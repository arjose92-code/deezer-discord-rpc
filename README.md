# 🎵 DeezerRP PRO — Deezer → Discord Rich Presence

> **La vraie app premium** pour afficher ta musique Deezer sur ton profil Discord, comme Spotify.  
> *Design inspiré de **Spotify + Discord + Linear** — live, silencieux, prioritaire même en jeu.*

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-RPC-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Deezer](https://img.shields.io/badge/Deezer-API-00C7B7?style=for-the-badge&logo=deezer&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Platform](https://img.shields.io/badge/Windows-11-0078D4?style=for-the-badge&logo=windows&logoColor=white)

---

## ✨ Aperçu

| Hero "En lecture" | Aperçu Discord | Tray arrière-plan |
|---|---|---|
| Pochette 140px arrondie + titre/artiste/album + progress shimmer + `⚡ PRIORITÉ HAUTE` | Carte `#232428` comme sur Discord + bouton `▶ Écouter sur Deezer` | Icône `♪` blurple + menu `Afficher / Pause / Priorité / Quitter` + toast `Tourne en arrière-plan` |

> **Interface 1160×720** — Sidebar `242px` Spotify, Topbar `56px`, Hero, 2 colonnes, Bottom player `68px` Spotify, animations 45ms shimmer + 120ms pulse.

---

## 🚀 Lancement ultra-simple

### 1) Installation des dépendances (1 clic)

Double-clique **`INSTALL.bat`** — il installe tout seul `pypresence pillow psutil pystray plyer` :

```bat
INSTALL.bat
# ou manuellement :
pip install -r requirements.txt
```

### 2) Lancer l'app

Double-clique **`lancer.bat`** (recommandé, silencieux `pythonw`) :

```bat
lancer.bat
# ou
python main.py
pythonw main.py --minimized  # arrière-plan direct
```

1. Colle ton **Client ID** Discord (déjà rempli) → **Connecter** (Discord Desktop doit être ouvert)
2. Active **Détection** `● LIVE` (switch dans `Tableau de bord` → `DÉTECTION`) → les champs se remplissent tout seuls depuis Deezer Desktop
3. Vérifie dans **Aperçu Discord** et sur ton profil — c'est live !

> **Polling silencieux** : `deezer.py` utilise `CREATE_NO_WINDOW` → plus de console qui clignote toutes les secondes, rafraîchissement fluide `1-30s`.

---

## 🎨 Fonctionnalités PRO

### Interface vraie app
- **Sidebar** Spotify : logo `♪ DeezerRP PRO • v2.7 LIVE`, nav 3 pages, status `● LIVE`, switches `Auto-start PC` / `Priorité haute`
- **Hero** 140px : pochette arrondie `18px`, `EN LECTURE • ⚡ PRIORITÉ HAUTE • ● EN ÉCOUTE`, progress shimmer
- **Bottom player** 68px : cover 52px + titre/artiste + `⏮ ⏸ ⏭` + progress + `↗ Mettre à jour`
- **Thème** : `BG #0a0a0e`, `CARD #14151c`, `ACCENT #5865f2`, `GREEN #1DB954`, `ENTRY #1c1e29`

### Arrière-plan + Tray
- **Ferme la fenêtre → ne quitte pas** : `root.withdraw()` + toast custom `♪ Tourne en arrière-plan — ton activité Discord reste prioritaire même en jeu.`
- **Tray icon** `64x64` blurple `♪` + point vert LIVE (via `pystray` + `PIL`)
- Menu tray : `Afficher`, `Pause/Reprendre`, `⚡ Priorité Discord ON/OFF`, `Mettre à jour`, `Effacer`, `Quitter`
- **Keepalive** : `tray_utils.py` + `plyer`/`win10toast`/`pystray.notify` + fallback `tkinter` slide toast

### Auto-start PC (robuste 4 méthodes)
- `Startup/DeezerRP.bat` + `DeezerRP.vbs` (hidden `0`)
- `HKCU\...\Run\DeezerRP` (registre)
- `schtasks /create /tn DeezerRP /sc onlogon /rl HIGHEST /delay 0000:10` (tâche planifiée)
- Toggle dans `Système & Priorité` + sidebar → `BAT:✓ VBS:✓ Registre:✓ Tâche:✓`

### Priorités
- **Windows** : `psutil.HIGH_PRIORITY_CLASS` + `ctypes SetPriorityClass(HIGH)` + `SetThreadExecutionState` + keepalive 15s → reste actif en `Game Mode` plein écran
- **Discord** : `discord_priority=True` → keepalive `5s` (vs `12s`) + reconnexion auto si `pipe closed` + `force=True` pour repasser devant `Joue à <Jeu>` → ton `Écoute Deezer` reste prioritaire
- Astuce : Discord → `Paramètres → Confidentialité → décoche "Affiche le jeu en cours"` pour 100% priorité

### ☁️ PC éteint ? Héberge 24/7
Local `SMTC` s'arrête PC éteint → voir `cloud/` :
```bash
# 1) Deezer → Paramètres → Connecte Last.fm + crée API key https://www.last.fm/api/account/create
# 2) Discord → https://discord.com/developers → Bot → Token
# 3) cd cloud && cp config.json.example config.json # remplis token + lastfm
# 4) Héberge :
docker build -t deezerrp-cloud ./cloud && docker run -d --restart unless-stopped -v ./cloud/config.json:/app/config.json deezerrp-cloud
# ou Render/Fly.io : Root Directory `cloud`, Start `python server.py`
```
`cloud/server.py:1` poll Last.fm `nowplaying` toutes les 5s + pochette Deezer → bot `Écoute Deezer`. Détails `cloud/README.md`.

---

## ⚙️ Personnaliser (comme CustomRP)

- **Type** `Écoute/Joue/Regarde`, **Nom** (`Deezer`), **Détails** (titre), **État** (artiste), **Temps écoulé**
- **Images** : grande URL pochette auto (API Deezer) + texte album + petite image
- **Boutons** : 2 boutons cliquables (`Écouter sur Deezer` → lien track)
- **Presets** : `💾 Sauver` / `📂 Charger` `.json`

---

## 📁 Structure

```
main.py          → lance l'interface ( --minimized --autostart + boost priorité )
gui.py           → interface premium 1160x720 (sidebar + hero + player + tray)
deezer.py        → détection SMTC via PowerShell + WinRT (CREATE_NO_WINDOW) + API Deezer
discord_rp.py    → client pypresence (LISTENING/PLAYING/WATCHING)
autostart.py     → 4 méthodes auto-start (BAT/VBS/Registre/Tâche)
priority.py      → HIGH_PRIORITY_CLASS + keepalive
tray_utils.py    → icône tray 64x64 + notifications (plyer/pystray/tk toast)
cloud/server.py  → bot 24/7 Last.fm → Discord (PC éteint)
cloud/Dockerfile → hébergement Render/Fly/Raspberry
INSTALL.bat      → installe les dépendances
lancer.bat       → lance en pythonw silencieux
config.json      → réglages (interval, Client ID, prio, etc.)
requirements.txt → pypresence pillow psutil pystray plyer
```

---

## 🛠️ Dépannage

- **Connexion impossible** → ouvre **Discord Desktop** (pas le navigateur), vérifie le Client ID sur https://discord.com/developers/applications
- **Rien détecté** → lance un son dans **Deezer Desktop** (pas juste "Deezer" affiché). Pour Deezer Web, coche `Inclure Deezer Web` (risque d'afficher un autre onglet)
- **Activité non visible** → Discord → `Paramètres → Confidentialité de l'activité` → active l'affichage + désactive `Affiche le jeu en cours` pour priorité Deezer
- **Tray invisible** → `pip install pystray plyer` ou relance `INSTALL.bat`

---

## 📦 Dépôt GitHub

```bash
git clone https://github.com/TON_USER/deezer-discord-rpc.git
cd deezer-discord-rpc
INSTALL.bat        # ou pip install -r requirements.txt
lancer.bat
```

**Pousser ton fork :**

```bash
git init
git add .
git commit -m "feat: DeezerRP PRO v2.6 — tray, priority, autostart"
git branch -M main
git remote add origin https://github.com/TON_USER/deezer-discord-rpc.git
git push -u origin main
```

---

## 📄 Licence

MIT — utilise, modifie, partage.

---

<p align="center">
  <b>Deezer → Discord</b> • <i>Reste en arrière-plan, même en jeu — et passe en priorité.</i><br>
  <code>♪ Écoute Deezer — Méchant - Maes</code>
</p>
