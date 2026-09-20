"""DeezerRP - detection du morceau Deezer en cours.

Methode : session media Windows (SMTC) lue via PowerShell + WinRT.
Marche avec Deezer Desktop et (optionnel) Deezer Web, meme quand la
fenetre Deezer affiche juste "Deezer".
"""
import json
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

PS_SCRIPT = """Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties, Windows.Media, ContentType=WindowsRuntime] | Out-Null
$asTaskMethods = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod })
function Wait-WinRT($op, $resultType) {
  $m = $asTaskMethods | Where-Object { $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
  $task = $m.MakeGenericMethod($resultType).Invoke($null, @(, $op))
  $task.Wait(10000) | Out-Null
  return $task.Result
}
try {
  $op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
  $mgr = Wait-WinRT $op ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
  $out = @()
  foreach ($s in @($mgr.GetSessions())) {
    try {
      $props = Wait-WinRT $s.TryGetMediaPropertiesAsync() ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties])
      $out += [PSCustomObject]@{ app = $s.SourceAppUserModelId; title = $props.Title; artist = $props.Artist; album = $props.AlbumTitle; status = $s.GetPlaybackInfo().PlaybackStatus.ToString() }
    } catch { continue }
  }
  $out | ConvertTo-Json -Compress
} catch { Write-Output "[]" }
"""

_ps_path = None


def _ps_file():
    """Ecrit le script PowerShell une fois dans le dossier temporaire."""
    global _ps_path
    if _ps_path is None or not Path(_ps_path).exists():
        _ps_path = str(Path(tempfile.gettempdir()) / "deezerrp_media.ps1")
        Path(_ps_path).write_text(PS_SCRIPT, encoding="utf-8")
    return _ps_path


def current_track(timeout=12, include_browser=False):
    """Morceau Deezer en lecture, ou None si rien ne joue.

    Retourne {"title", "artist", "album", "source"}.
    include_browser=True accepte aussi les sessions navigateur (Deezer Web),
    au risque d'afficher un autre onglet (ex. TikTok) qui joue du son.
    """
    try:
        # CREATE_NO_WINDOW evite le flash de console a chaque poll (toutes les 1-2s)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", _ps_file()],
            capture_output=True, text=True, timeout=timeout,
            creationflags=flags, encoding="utf-8", errors="replace",
        )
        data = json.loads((r.stdout or "").strip() or "[]")
    except Exception:
        return None
    if isinstance(data, dict):
        data = [data]
    if not data:
        return None

    deezer = [s for s in data if "deezer" in str(s.get("app", "")).lower()]
    pool = (deezer + [s for s in data if s not in deezer]) if include_browser else deezer
    pool = [s for s in pool
            if str(s.get("status", "")) == "Playing"
            and str(s.get("title", "") or "").strip()]
    if not pool:
        return None
    best = pool[0]
    app = str(best.get("app", ""))
    return {
        "title": str(best["title"]).strip(),
        "artist": str(best.get("artist", "") or "").strip() or None,
        "album": str(best.get("album", "") or "").strip() or None,
        "source": "Deezer Desktop" if "deezer" in app.lower() else "Deezer Web",
    }


_info_cache = {}


def track_info(artist, title):
    """(cover_url, album, track_url) via l'API publique Deezer. Resultat en cache."""
    key = f"{(artist or '').lower()} - {title.lower()}"
    if key in _info_cache:
        return _info_cache[key]
    try:
        q = urllib.parse.quote(f"{artist} {title}" if artist else title)
        req = urllib.request.Request(
            "https://api.deezer.com/search?q=" + q,
            headers={"User-Agent": "DeezerRP"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            items = json.load(resp).get("data") or []
        if not items:
            return _info_cache.setdefault(key, (None, None, None))
        best = items[0]
        if artist:
            for it in items[:5]:
                if artist.lower() in str(it.get("artist", {}).get("name", "")).lower():
                    best = it
                    break
        album = best.get("album", {}) or {}
        info = (album.get("cover_big") or album.get("cover_medium"),
                album.get("title"), best.get("link"))
        _info_cache[key] = info
        return info
    except Exception:
        return (None, None, None)


def search_url(artist, title):
    q = f"{artist} {title}" if artist else title
    return "https://www.deezer.com/search/" + urllib.parse.quote(q)
