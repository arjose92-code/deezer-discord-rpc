"""DeezerRP — Vraie app premium (Spotify + Discord + Linear) — live, autostart, priorité jeu."""
import io
import json
import os
import queue
import sys
import threading
import time
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    Image = None

import deezer
from discord_rp import DeezerPresence, TYPES
import autostart
import priority as prio
try:
    import tray_utils
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False
    tray_utils = None

BASE = Path(__file__).parent
CONFIG = BASE / "config.json"

# ── Palette vraie app (Spotify noir + Discord blurple + Linear subtle) ──
BG_MAIN    = "#08080a"  # sidebar
BG         = "#0a0a0e"  # main
BG2        = "#111117"
CARD       = "#14151c"
CARD2      = "#1a1c26"
CARD3      = "#1f2230"
BORDER     = "#1e1f2a"
BORDER2    = "#272a3a"
ACCENT     = "#5865f2"
ACCENT_H   = "#4752c4"
GREEN      = "#1DB954"  # Spotify
GREEN2     = "#169c46"
SUCCESS    = "#23a55a"
WARN       = "#f0b132"
DANGER     = "#f23f42"
TEXT       = "#f2f3f5"
MUTED      = "#9aa0b0"
SUBTLE     = "#6b7280"
ENTRY_BG   = "#1c1e29"
ENTRY_BD   = "#2c2f42"

DEFAULTS = {
    "discord_client_id": "", "interval": 2, "include_browser": False,
    "show_buttons": True, "activity": "Ecoute", "app_name": "Deezer",
    "show_time": True, "small_image": "", "small_text": "",
    "btn1_text": "Écouter sur Deezer", "btn1_url": "",
    "btn2_text": "Ouvrir Deezer", "btn2_url": "https://www.deezer.com",
    "autostart": True, "priority_high": True, "minimize_to_tray": True, "always_on_top": False,
    "discord_priority": True,
}

def load_config():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    except Exception:
        return dict(DEFAULTS)

def save_config(data):
    try:
        CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def on_hover(btn, normal, hover):
    btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
    btn.bind("<Leave>", lambda e: btn.configure(bg=normal))

def rounded_image(pil_img, size=96, radius=18):
    if not HAS_PIL: return None
    try:
        img = pil_img.convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,size,size), radius=radius, fill=255)
        img.putalpha(mask)
        bg = Image.new("RGBA", (size, size), (31,32,42,255))
        bg = Image.alpha_composite(bg, img)
        return ImageTk.PhotoImage(bg)
    except Exception:
        try: return ImageTk.PhotoImage(pil_img.resize((size,size)))
        except: return None

class App:
    def __init__(self, root):
        self.root = root
        root.title("DeezerRP  —  Deezer → Discord")
        root.configure(bg=BG)
        try:
            root.geometry("1160x720")
            root.minsize(1080, 680)
        except: pass
        # icône
        try: root.iconbitmap("")
        except: pass

        self.cfg = load_config()
        self.presence = None
        self.auto_on = False
        self.v_auto = tk.BooleanVar(value=True)
        self.events = queue.Queue()
        self.last_key = None
        self.start_time = None
        self.current_source = None
        self.current_track = None
        self.img_cache = {}
        self.cover_photo = None
        self.coversmall = None
        self.pulse = 0
        self.shimmer = 0
        self.connected = False
        self.current_page = "dashboard"
        self.last_send = 0
        # priorité Discord : si activée, keepalive plus agressif (5s) pour passer devant les jeux
        self.discord_priority = self.cfg.get("discord_priority", True)
        self.keepalive_interval = 5 if self.discord_priority else 12
        self.tray_manager = None
        self._force_quit = False
        self._tray_shown_once = False

        # priorité haute dès le boot si activée — reste prioritaire même en jeu
        if self.cfg.get("priority_high", True):
            prio.boost(True)
            prio.keep_alive_thread(15, lambda: self.cfg.get("priority_high", True) and (self.v_prio.get() if hasattr(self, "v_prio") else True))

        self._style()
        self._build()
        self._load_cfg()
        self._bind_preview()

        # autostart réel vs config — si demandé dans config, on l'active vraiment (BAT+VBS+Registre+Tâche)
        self._sync_autostart_ui()
        self._sync_priority_ui()
        if self.cfg.get("autostart", True) and not autostart.is_enabled():
            try:
                autostart.enable()
                self._sync_autostart_ui()
            except: pass

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(250, self._drain)
        root.after(500, self._tick)
        root.after(90, self._pulse)
        root.after(50, self._shimmer_tick)
        # tray en arrière-plan — toujours actif même si on ferme la fenêtre
        self._init_tray()

        # si lancé au démarrage (--minimized ou --autostart), se minimise et auto-connect
        if "--minimized" in sys.argv or "--autostart" in sys.argv:
            try: root.iconify()
            except: pass
            self.say("lancement auto au démarrage", "ok")
            if self.e_client.get().strip():
                root.after(1200, self._auto_connect_start)

        # always on top si demandé
        if self.cfg.get("always_on_top"):
            try: root.attributes("-topmost", True)
            except: pass

    def _auto_connect_start(self):
        if not self.connected:
            self.do_connect(silent=True)
        if not self.auto_on:
            self.v_auto.set(True)
            self.toggle_auto()

    def _style(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except: pass
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=TEXT)
        s.configure("TCombobox", fieldbackground=ENTRY_BG, background=ENTRY_BG, foreground=TEXT, arrowcolor=MUTED)
        try: s.map("TCombobox", fieldbackground=[("readonly", ENTRY_BG)])
        except: pass

    # ── UI BUILD ──
    def _build(self):
        r = self.root
        # grid sidebar | main
        r.grid_columnconfigure(1, weight=1)
        r.grid_rowconfigure(0, weight=1)

        # === SIDEBAR (vraie app) ===
        sidebar = tk.Frame(r, bg=BG_MAIN, width=242, highlightbackground=BORDER, highlightthickness=1, bd=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.pack_propagate(False)

        # logo
        logo = tk.Frame(sidebar, bg=BG_MAIN)
        logo.pack(fill="x", padx=18, pady=18)
        tk.Label(logo, text="♪", bg=BG_MAIN, fg=ACCENT, font=("Segoe UI", 22, "bold")).pack(side="left")
        tb = tk.Frame(logo, bg=BG_MAIN)
        tb.pack(side="left", padx=10)
        tk.Label(tb, text="DeezerRP", bg=BG_MAIN, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(tb, text="PRO  •  v2.6", bg=BG_MAIN, fg=GREEN, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        # version pill
        pill = tk.Frame(logo, bg=CARD3, highlightbackground=BORDER2, highlightthickness=1)
        pill.pack(side="right")
        tk.Label(pill, text="LIVE", bg=CARD3, fg=GREEN, font=("Segoe UI", 7, "bold"), padx=6, pady=2).pack()

        # nav
        nav = tk.Frame(sidebar, bg=BG_MAIN)
        nav.pack(fill="x", padx=10, pady=6)
        tk.Label(nav, text="NAVIGATION", bg=BG_MAIN, fg=SUBTLE, font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=6, pady=(0,8))

        self.nav_btns = {}
        def nav_btn(icon, label, page, active=False):
            outer = tk.Frame(nav, bg=ACCENT if active else BG_MAIN, highlightthickness=0, bd=0)
            outer.pack(fill="x", pady=2)
            # left accent
            accent = tk.Frame(outer, bg=ACCENT if active else BG_MAIN, width=3)
            accent.pack(side="left", fill="y")
            btn = tk.Button(outer, text=f"  {icon}   {label}", bg=CARD if active else BG_MAIN, fg=TEXT if active else MUTED,
                            activebackground=CARD2, activeforeground=TEXT, relief="flat", bd=0, anchor="w",
                            font=("Segoe UI", 9, "bold" if active else "normal"), padx=10, pady=9, cursor="hand2",
                            command=lambda p=page: self.show_page(p))
            btn.pack(side="left", fill="x", expand=True)
            # hover
            def ent(e):
                if self.current_page != page:
                    btn.configure(bg=CARD2, fg=TEXT)
            def lea(e):
                if self.current_page != page:
                    btn.configure(bg=BG_MAIN, fg=MUTED)
            btn.bind("<Enter>", ent); btn.bind("<Leave>", lea)
            self.nav_btns[page] = (outer, accent, btn)
            return outer

        nav_btn("◉", "Tableau de bord", "dashboard", True)
        nav_btn("🎨", "Personnaliser", "studio")
        nav_btn("⚙", "Système & Priorité", "settings")

        # divider
        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=14, pady=12)

        # quick status card dans sidebar
        qcard = tk.Frame(sidebar, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        qcard.pack(fill="x", padx=12, pady=6)
        qh = tk.Frame(qcard, bg=CARD)
        qh.pack(fill="x", padx=12, pady=(10,6))
        tk.Label(qh, text="ÉTAT", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.sb_dot = tk.Canvas(qh, width=8, height=8, bg=CARD, highlightthickness=0)
        self.sb_dot.pack(side="right")
        self._sb_dot(SUBTLE)
        self.sb_status = tk.Label(qcard, text="Déconnecté", bg=CARD, fg=MUTED, font=("Segoe UI", 9, "bold"), anchor="w")
        self.sb_status.pack(fill="x", padx=12)
        self.sb_track = tk.Label(qcard, text="Aucune lecture", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7), anchor="w", wraplength=190)
        self.sb_track.pack(fill="x", padx=12, pady=(2,8))
        # mini eq
        self.sb_eq = tk.Canvas(qcard, width=60, height=12, bg=CARD, highlightthickness=0)
        self.sb_eq.pack(padx=12, pady=(0,10), anchor="w")

        # switches sidebar
        sw = tk.Frame(sidebar, bg=BG_MAIN)
        sw.pack(fill="x", padx=12, pady=6)
        # autostart
        r1 = tk.Frame(sw, bg=BG_MAIN)
        r1.pack(fill="x", pady=4)
        tk.Label(r1, text="Auto-start PC", bg=BG_MAIN, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        self.v_autostart = tk.BooleanVar(value=False)
        self.sw_autostart = self._switch(r1, self.v_autostart, self.toggle_autostart)
        self.sw_autostart.pack(side="right")
        # priorité
        r2 = tk.Frame(sw, bg=BG_MAIN)
        r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Priorité haute", bg=BG_MAIN, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        tk.Label(r2, text="jeu", bg=BG_MAIN, fg=SUBTLE, font=("Segoe UI", 7)).pack(side="left", padx=4)
        self.v_prio = tk.BooleanVar(value=True)
        self.sw_prio = self._switch(r2, self.v_prio, self.toggle_priority)
        self.sw_prio.pack(side="right")

        # footer sidebar
        foot = tk.Frame(sidebar, bg=BG_MAIN)
        foot.pack(side="bottom", fill="x", padx=12, pady=12)
        tk.Label(foot, text="Deezer → Discord", bg=BG_MAIN, fg=SUBTLE, font=("Segoe UI", 7)).pack(anchor="w")
        tk.Label(foot, text="Reste actif même en jeu", bg=BG_MAIN, fg=GREEN, font=("Segoe UI", 7, "bold")).pack(anchor="w")
        # github
        tk.Label(foot, text="github.com • DeezerRP", bg=BG_MAIN, fg=MUTED, font=("Segoe UI", 7, "underline"), cursor="hand2").pack(anchor="w", pady=(6,0))

        # === MAIN ===
        main = tk.Frame(r, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        # topbar
        topbar = tk.Frame(main, bg=BG2, height=56, highlightbackground=BORDER, highlightthickness=1, bd=0)
        topbar.grid(row=0, column=0, sticky="ew")
        topbar.pack_propagate(False)
        topbar.grid_propagate(False)

        tl = tk.Frame(topbar, bg=BG2)
        tl.pack(side="left", padx=16, pady=10)
        self.top_title = tk.Label(tl, text="Tableau de bord", bg=BG2, fg=TEXT, font=("Segoe UI", 12, "bold"))
        self.top_title.pack(side="left")
        self.top_sub = tk.Label(tl, text="  •  live  •  polling silencieux", bg=BG2, fg=MUTED, font=("Segoe UI", 8))
        self.top_sub.pack(side="left", padx=8)

        # live pill top
        self.live_canvas = tk.Canvas(topbar, width=18, height=18, bg=BG2, highlightthickness=0)
        self.live_canvas.pack(side="left", padx=(12,4))
        self.live_label = tk.Label(topbar, text="VEILLE", bg=BG2, fg=MUTED, font=("Segoe UI", 8, "bold"))
        self.live_label.pack(side="left")

        tr = tk.Frame(topbar, bg=BG2)
        tr.pack(side="right", padx=12, pady=8)
        # status pill
        self.status_pill = tk.Frame(tr, bg=CARD, highlightbackground=BORDER2, highlightthickness=1)
        self.status_pill.pack(side="left", padx=6)
        self.dot_canvas = tk.Canvas(self.status_pill, width=10, height=10, bg=CARD, highlightthickness=0)
        self.dot_canvas.pack(side="left", padx=(10,4), pady=6)
        self._draw_dot(SUBTLE)
        self.l_status = tk.Label(self.status_pill, text="Déconnecté", bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self.l_status.pack(side="left", padx=(0,10))

        self.b_connect = tk.Button(tr, text=" Connecter ", bg=ACCENT, fg="white", activebackground=ACCENT_H, relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2", command=self.do_connect)
        self.b_connect.pack(side="left", padx=4); on_hover(self.b_connect, ACCENT, ACCENT_H)
        self.b_disconnect = tk.Button(tr, text="Déconnecter", bg=CARD2, fg=MUTED, activebackground=BORDER2, relief="flat", bd=0, font=("Segoe UI", 9), padx=12, pady=6, cursor="hand2", command=self.do_disconnect, state="disabled", highlightbackground=BORDER2, highlightthickness=1)
        self.b_disconnect.pack(side="left", padx=4)
        # always on top
        self.v_top = tk.BooleanVar(value=self.cfg.get("always_on_top", False))
        tk.Checkbutton(tr, text="📌", variable=self.v_top, command=self.toggle_topmost, bg=BG2, fg=MUTED, selectcolor=CARD, font=("Segoe UI", 9), width=2).pack(side="left", padx=6)

        # === CONTENT SCROLLABLE ===
        # container for pages
        self.page_host = tk.Frame(main, bg=BG)
        self.page_host.grid(row=1, column=0, sticky="nsew")
        self.page_host.grid_rowconfigure(0, weight=1)
        self.page_host.grid_columnconfigure(0, weight=1)

        # create 3 pages as frames stacked
        self.pages = {}
        for name in ("dashboard", "studio", "settings"):
            f = tk.Frame(self.page_host, bg=BG)
            f.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = f

        self._build_dashboard(self.pages["dashboard"])
        self._build_studio(self.pages["studio"])
        self._build_settings(self.pages["settings"])

        self.show_page("dashboard")

        # === BOTTOM PLAYER BAR (Spotify-like) ===
        bottom = tk.Frame(main, bg="#0f1117", height=68, highlightbackground=BORDER, highlightthickness=1, bd=0)
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.pack_propagate(False)
        # left: cover + track
        bl = tk.Frame(bottom, bg="#0f1117")
        bl.pack(side="left", padx=12, pady=8, fill="y")
        self.btm_cover = tk.Canvas(bl, width=52, height=52, bg="#0f1117", highlightthickness=0)
        self.btm_cover.pack(side="left")
        self._draw_btm_placeholder()
        btm_txt = tk.Frame(bl, bg="#0f1117")
        btm_txt.pack(side="left", padx=10)
        self.btm_title = tk.Label(btm_txt, text="Aucune lecture", bg="#0f1117", fg=TEXT, font=("Segoe UI", 9, "bold"), anchor="w", width=28)
        self.btm_title.pack(anchor="w")
        self.btm_artist = tk.Label(btm_txt, text="Lance Deezer", bg="#0f1117", fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.btm_artist.pack(anchor="w")
        self.btm_source = tk.Label(btm_txt, text="", bg="#0f1117", fg=GREEN, font=("Segoe UI", 7))
        self.btm_source.pack(anchor="w")

        # center: controls + timer + progress
        bc = tk.Frame(bottom, bg="#0f1117")
        bc.pack(side="left", expand=True, fill="both", padx=12)
        ctrl = tk.Frame(bc, bg="#0f1117")
        ctrl.pack(pady=(8,4))
        tk.Button(ctrl, text="⏮", bg="#0f1117", fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 10), cursor="hand2", command=self.fetch_once).pack(side="left", padx=6)
        self.btm_play = tk.Canvas(ctrl, width=32, height=32, bg="#0f1117", highlightthickness=0)
        self.btm_play.pack(side="left", padx=6)
        self._draw_play(False)
        tk.Button(ctrl, text="⏭", bg="#0f1117", fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 10), cursor="hand2", command=self.fetch_once).pack(side="left", padx=6)
        # progress + time
        prog = tk.Frame(bc, bg="#0f1117")
        prog.pack(fill="x")
        self.btm_time_l = tk.Label(prog, text="0:00", bg="#0f1117", fg=MUTED, font=("Consolas", 7))
        self.btm_time_l.pack(side="left")
        self.btm_progress = tk.Canvas(prog, height=4, bg="#0f1117", highlightthickness=0)
        self.btm_progress.pack(side="left", fill="x", expand=True, padx=8)
        self.btm_time_r = tk.Label(prog, text="LIVE", bg="#0f1117", fg=GREEN, font=("Consolas", 7, "bold"))
        self.btm_time_r.pack(side="right")

        # right: actions
        br = tk.Frame(bottom, bg="#0f1117")
        br.pack(side="right", padx=12, pady=10)
        self.b_update = tk.Button(br, text="↗ Mettre à jour", bg=ACCENT, fg="white", activebackground=ACCENT_H, relief="flat", bd=0, font=("Segoe UI", 8, "bold"), padx=12, pady=7, cursor="hand2", command=self.send_fields)
        br.pack_propagate(False)
        self.b_update.pack(side="left", padx=4); on_hover(self.b_update, ACCENT, ACCENT_H)
        tk.Button(br, text="✕", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=10, pady=7, cursor="hand2", command=self.clear_presence, highlightbackground=BORDER, highlightthickness=1).pack(side="left", padx=4)

        # statusbar
        self.statusbar = tk.Frame(main, bg=BG2, height=20, highlightbackground=BORDER, highlightthickness=1)
        self.statusbar.grid(row=3, column=0, sticky="ew")
        self.statusbar.pack_propagate(False)
        self.sb_left = tk.Label(self.statusbar, text=" ●  Prêt  •  priorité haute active", bg=BG2, fg=SUBTLE, font=("Segoe UI", 7))
        self.sb_left.pack(side="left", padx=10)
        self.sb_right = tk.Label(self.statusbar, text="DeezerRP PRO  •  reste actif en jeu", bg=BG2, fg=SUBTLE, font=("Segoe UI", 7))
        self.sb_right.pack(side="right", padx=10)

    def _switch(self, parent, var, cmd):
        """Canvas switch 44x22."""
        c = tk.Canvas(parent, width=44, height=22, bg=parent["bg"], highlightthickness=0, cursor="hand2")
        def draw():
            c.delete("all")
            on = var.get()
            # track
            fill = ACCENT if on else "#2a2e3d"
            outline = ACCENT if on else BORDER2
            c.create_oval(0,0,22,22, fill=fill, outline=outline)
            c.create_oval(22,0,44,22, fill=fill, outline=outline)
            c.create_rectangle(11,0,33,22, fill=fill, outline=fill)
            # thumb
            x = 32 if on else 12
            c.create_oval(x-8,2,x+8,20, fill="white", outline="#d0d0d0", width=1)
        def toggle(e):
            var.set(not var.get())
            draw()
            if cmd: cmd()
        c.bind("<Button-1>", toggle)
        var.trace_add("write", lambda *_: draw())
        draw()
        return c

    def _sb_dot(self, col):
        self.sb_dot.delete("all"); self.sb_dot.create_oval(1,1,7,7, fill=col, outline="")
    def _draw_dot(self, col):
        self.dot_canvas.delete("all"); self.dot_canvas.create_oval(1,1,9,9, fill=col, outline="")
    def _draw_btm_placeholder(self):
        self.btm_cover.delete("all")
        self.btm_cover.create_rectangle(0,0,52,52, fill=CARD2, outline=BORDER)
        self.btm_cover.create_text(26,26, text="♪", fill=MUTED, font=("Segoe UI", 14, "bold"))
    def _draw_play(self, playing):
        self.btm_play.delete("all")
        self.btm_play.create_oval(2,2,30,30, fill=GREEN if playing else CARD2, outline=BORDER2)
        if playing:
            self.btm_play.create_rectangle(11,10,14,22, fill="white", outline="")
            self.btm_play.create_rectangle(18,10,21,22, fill="white", outline="")
        else:
            self.btm_play.create_polygon(12,9,12,23,22,16, fill="white", outline="")
    def _draw_cover_placeholder_small(self, canvas, w=96, h=96):
        canvas.delete("all")
        canvas.create_rectangle(0,0,w,h, fill=CARD2, outline=BORDER)
        canvas.create_text(w//2, h//2-10, text="♪", fill=MUTED, font=("Segoe UI", 18, "bold"))
        canvas.create_text(w//2, h//2+10, text="pochette", fill=SUBTLE, font=("Segoe UI", 7))

    # ── PAGES ──
    def _build_dashboard(self, parent):
        # hero now playing
        hero = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, bd=0)
        hero.pack(fill="x", padx=14, pady=12)
        # left cover 140
        self.c_cover = tk.Canvas(hero, width=140, height=140, bg=CARD, highlightthickness=0)
        self.c_cover.pack(side="left", padx=14, pady=14)
        self._draw_cover_placeholder_small(self.c_cover, 140, 140)
        # right infos
        info = tk.Frame(hero, bg=CARD)
        info.pack(side="left", fill="both", expand=True, padx=6, pady=14)
        top = tk.Frame(info, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="EN LECTURE", bg=CARD, fg=GREEN, font=("Segoe UI", 7, "bold")).pack(side="left")
        self.prio_badge = tk.Label(top, text="⚡ PRIORITÉ HAUTE", bg=GREEN, fg="white", font=("Segoe UI", 7, "bold"), padx=6, pady=2)
        self.prio_badge.pack(side="left", padx=8)
        self.pv_live = tk.Label(top, text="● VEILLE", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold"))
        self.pv_live.pack(side="right")
        self.l_pv_type = tk.Label(info, text="ÉCOUTE DEEZER", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold"), anchor="w")
        self.l_pv_type.pack(anchor="w", pady=(8,2))
        self.l_pv_title = tk.Label(info, text="—", bg=CARD, fg=TEXT, font=("Segoe UI", 14, "bold"), anchor="w", wraplength=520, justify="left")
        self.l_pv_title.pack(anchor="w")
        self.l_pv_state = tk.Label(info, text="En attente de Deezer…", bg=CARD, fg=MUTED, font=("Segoe UI", 10), anchor="w", wraplength=520)
        self.l_pv_state.pack(anchor="w", pady=2)
        self.l_pv_album = tk.Label(info, text="", bg=CARD, fg=SUBTLE, font=("Segoe UI", 9), anchor="w")
        self.l_pv_album.pack(anchor="w")
        # progress
        self.progress_frame = tk.Frame(info, bg=CARD)
        self.progress_frame.pack(fill="x", pady=(14,0))
        self.progress_bg = tk.Canvas(self.progress_frame, height=6, bg=CARD, highlightthickness=0)
        self.progress_bg.pack(fill="x", expand=True)
        tr = tk.Frame(info, bg=CARD)
        tr.pack(fill="x", pady=(4,0))
        self.l_pv_time = tk.Label(tr, text="", bg=CARD, fg=GREEN, font=("Consolas", 9, "bold"))
        self.l_pv_time.pack(side="left")
        self.l_pv_source = tk.Label(tr, text="", bg=CARD, fg=SUBTLE, font=("Segoe UI", 8))
        self.l_pv_source.pack(side="right")
        # eq
        self.eq_canvas = tk.Canvas(info, width=60, height=14, bg=CARD, highlightthickness=0)
        self.eq_canvas.pack(anchor="w", pady=(6,0))

        # row 2 : 2 colonnes
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="both", expand=True, padx=14, pady=6)
        row.grid_columnconfigure(0, weight=1); row.grid_columnconfigure(1, weight=1)

        # left: aperçu discord
        left = tk.Frame(row, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0,6))
        lh = tk.Frame(left, bg=CARD); lh.pack(fill="x", padx=14, pady=(12,8))
        tk.Label(lh, text="APERÇU DISCORD", bg=CARD, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(lh, text="comme tes amis le voient", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7)).pack(side="right")
        # discord card
        dc = tk.Frame(left, bg="#232428", highlightbackground="#2e2f34", highlightthickness=1)
        dc.pack(fill="x", padx=14, pady=6)
        dc_inner = tk.Frame(dc, bg="#232428"); dc_inner.pack(fill="x", padx=12, pady=12)
        self.c_preview = tk.Canvas(dc_inner, width=72, height=72, bg="#232428", highlightthickness=0)
        self.c_preview.pack(side="left")
        self._draw_cover_placeholder_small(self.c_preview, 72, 72)
        txts = tk.Frame(dc_inner, bg="#232428"); txts.pack(side="left", fill="x", expand=True, padx=10)
        self.l_pre_title = tk.Label(txts, text="—", bg="#232428", fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w", wraplength=200)
        self.l_pre_title.pack(anchor="w")
        self.l_pre_state = tk.Label(txts, text="", bg="#232428", fg="#b5bac1", font=("Segoe UI", 8), anchor="w")
        self.l_pre_state.pack(anchor="w")
        self.l_pre_time = tk.Label(txts, text="", bg="#232428", fg="#00c782", font=("Consolas", 7))
        self.l_pre_time.pack(anchor="w", pady=(4,0))
        # buttons preview
        self.pv_btns = tk.Frame(left, bg=CARD); self.pv_btns.pack(fill="x", padx=14, pady=(8,12))
        self.pv_b1 = tk.Label(self.pv_btns, text="▶ Écouter sur Deezer", bg=CARD2, fg=TEXT, font=("Segoe UI", 8, "bold"), padx=10, pady=7)
        self.pv_b1.pack(side="left", fill="x", expand=True, padx=(0,6))
        self.pv_b2 = tk.Label(self.pv_btns, text="Ouvrir Deezer", bg=CARD2, fg=MUTED, font=("Segoe UI", 8), padx=10, pady=7)
        self.pv_b2.pack(side="left", fill="x", expand=True, padx=(6,0))

        # right: stats + now
        right = tk.Frame(row, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(6,0))
        rh = tk.Frame(right, bg=CARD); rh.pack(fill="x", padx=14, pady=(12,8))
        tk.Label(rh, text="DÉTECTION", bg=CARD, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.mini_live = tk.Label(rh, text="● LIVE", bg=CARD, fg=SUCCESS, font=("Segoe UI", 7, "bold"))
        self.mini_live.pack(side="right", padx=6)
        self.sw_auto = self._switch(rh, self.v_auto, self.toggle_auto)
        self.sw_auto.pack(side="right")
        # now bar
        self.now_frame = tk.Frame(right, bg=BG2, highlightbackground=BORDER2, highlightthickness=1)
        self.now_frame.pack(fill="x", padx=14, pady=4)
        self.now_dot = tk.Canvas(self.now_frame, width=8, height=8, bg=BG2, highlightthickness=0)
        self.now_dot.pack(side="left", padx=10, pady=10)
        self._draw_now_dot(SUBTLE)
        self.l_now = tk.Label(self.now_frame, text="Rien en lecture — lance Deezer", bg=BG2, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.l_now.pack(side="left", fill="x", expand=True)
        self.b_refresh = tk.Button(self.now_frame, text="↻", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 9, "bold"), cursor="hand2", command=self.fetch_once, width=3)
        self.b_refresh.pack(side="right", padx=6)
        # interval
        iv = tk.Frame(right, bg=CARD); iv.pack(fill="x", padx=14, pady=8)
        tk.Label(iv, text="Rafraîchissement", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.e_interval = tk.Spinbox(iv, from_=1, to=30, width=4, bg=ENTRY_BG, fg=TEXT, buttonbackground=CARD2, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 9, "bold"), justify="center")
        self.e_interval.pack(side="left", padx=8)
        tk.Label(iv, text="sec", bg=CARD, fg=SUBTLE, font=("Segoe UI", 8)).pack(side="left")
        self.v_time = tk.BooleanVar(value=True)
        tk.Checkbutton(iv, text="Temps écoulé", variable=self.v_time, bg=CARD, fg=MUTED, selectcolor=CARD2, font=("Segoe UI", 8), command=self._preview).pack(side="right")
        # interval info
        self.stats_track = tk.Label(right, text="—", bg=CARD, fg=MUTED, font=("Segoe UI", 8), wraplength=280, anchor="w")
        self.stats_track.pack(fill="x", padx=14, pady=4)
        self.stats_info = tk.Label(right, text="Polling silencieux • CREATE_NO_WINDOW", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7))
        self.stats_info.pack(fill="x", padx=14, pady=(0,12))
        # actions
        ac = tk.Frame(right, bg=CARD); ac.pack(fill="x", padx=14, pady=(0,12))
        tk.Button(ac, text="↗ Mettre à jour", bg=ACCENT, fg="white", relief="flat", bd=0, font=("Segoe UI", 8, "bold"), padx=12, pady=6, cursor="hand2", command=self.send_fields).pack(side="left", fill="x", expand=True, padx=(0,4))
        tk.Button(ac, text="✕ Effacer", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=12, pady=6, cursor="hand2", command=self.clear_presence, highlightbackground=BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=(4,0))

        # journal en bas dashboard
        jcard = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        jcard.pack(fill="both", expand=True, padx=14, pady=6)
        jh = tk.Frame(jcard, bg=CARD); jh.pack(fill="x", padx=14, pady=(8,6))
        tk.Label(jh, text="JOURNAL", bg=CARD, fg=TEXT, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(jh, text="temps réel", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7)).pack(side="left", padx=8)
        tk.Button(jh, text="Effacer", bg=CARD, fg=SUBTLE, relief="flat", bd=0, font=("Segoe UI", 7), cursor="hand2", command=self._clear_log).pack(side="right")
        log_wrap = tk.Frame(jcard, bg=BG2, highlightbackground=BORDER2, highlightthickness=1)
        log_wrap.pack(fill="both", expand=True, padx=12, pady=(0,10))
        self.log = tk.Text(log_wrap, height=4, bg=BG2, fg="#cfd2da", font=("Consolas", 8), relief="flat", bd=0, highlightthickness=0, state="disabled", wrap="word", padx=8, pady=6)
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log.yview); sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)

    def _build_studio(self, parent):
        # Personnaliser — 2 colonnes
        parent.grid_columnconfigure(0, weight=1); parent.grid_columnconfigure(1, weight=1)
        # Activité
        f1_outer, f1 = self._card(parent, "ACTIVITÉ DISCORD", "🎮")
        f1_outer.grid(row=0, column=0, sticky="nsew", padx=14, pady=8)
        r0 = tk.Frame(f1, bg=CARD); r0.pack(fill="x", pady=4)
        tk.Label(r0, text="Type", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")
        self.c_type = ttk.Combobox(r0, values=list(TYPES), width=12, state="readonly", font=("Segoe UI", 9))
        self.c_type.pack(side="left", padx=8)
        tk.Label(r0, text="Nom", bg=CARD, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(8,4))
        self.e_name = tk.Entry(r0, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 9))
        self.e_name.pack(side="left", fill="x", expand=True, ipady=5, padx=4)
        tk.Label(f1, text="Détails  (titre)", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(10,4))
        self.e_details = tk.Entry(f1, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 10, "bold"))
        self.e_details.pack(fill="x", ipady=7)
        tk.Label(f1, text="État  (artiste)", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(8,4))
        self.e_state = tk.Entry(f1, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 9))
        self.e_state.pack(fill="x", ipady=7)

        f2_outer, f2 = self._card(parent, "IMAGES & BOUTONS", "🖼️")
        f2_outer.grid(row=0, column=1, sticky="nsew", padx=14, pady=8)
        tk.Label(f2, text="Grande image (pochette auto)", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0,4))
        self.e_large = tk.Entry(f2, bg=ENTRY_BG, fg=SUBTLE, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Consolas", 7))
        self.e_large.pack(fill="x", ipady=6)
        row4 = tk.Frame(f2, bg=CARD); row4.pack(fill="x", pady=(8,0))
        tk.Label(row4, text="Texte album", bg=CARD, fg=MUTED, font=("Segoe UI", 7)).pack(side="left")
        self.e_large_txt = tk.Entry(row4, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 8))
        self.e_large_txt.pack(side="left", fill="x", expand=True, padx=6, ipady=5)
        tk.Label(row4, text="Petite", bg=CARD, fg=MUTED, font=("Segoe UI", 7)).pack(side="left", padx=(6,4))
        self.e_small = tk.Entry(row4, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 8), width=10)
        self.e_small.pack(side="left", ipady=5)
        self.v_btns = tk.BooleanVar(value=True)
        tk.Checkbutton(f2, text="Afficher les boutons", variable=self.v_btns, bg=CARD, fg=MUTED, selectcolor=CARD2, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10,6))
        br1 = tk.Frame(f2, bg=CARD); br1.pack(fill="x", pady=2)
        self.e_b1t = tk.Entry(br1, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 8))
        self.e_b1t.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,6))
        self.e_b1u = tk.Entry(br1, bg=ENTRY_BG, fg=SUBTLE, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Consolas", 7))
        self.e_b1u.pack(side="left", fill="x", expand=True, ipady=5)
        br2 = tk.Frame(f2, bg=CARD); br2.pack(fill="x", pady=2)
        self.e_b2t = tk.Entry(br2, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Segoe UI", 8))
        self.e_b2t.pack(side="left", fill="x", expand=True, ipady=5, padx=(0,6))
        self.e_b2u = tk.Entry(br2, bg=ENTRY_BG, fg=SUBTLE, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Consolas", 7))
        self.e_b2u.pack(side="left", fill="x", expand=True, ipady=5)
        # presets
        pre = tk.Frame(f2, bg=CARD); pre.pack(fill="x", pady=(10,0))
        tk.Button(pre, text="💾 Sauver preset", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2", command=self.save_preset, highlightbackground=BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=(0,4))
        tk.Button(pre, text="📂 Charger preset", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=10, pady=6, cursor="hand2", command=self.load_preset, highlightbackground=BORDER, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=(4,0))

    def _build_settings(self, parent):
        # Système & Priorité — pack vertical (pas de grid)
        # Card connexion
        f0_outer, f0 = self._card(parent, "CONNEXION DISCORD", "🔗")
        f0_outer.pack(fill="x", padx=14, pady=10)
        tk.Label(f0, text="Client ID  (Discord Developer Portal → Application ID)", bg=CARD, fg=MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0,4))
        self.e_client = tk.Entry(f0, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, highlightbackground=ENTRY_BD, highlightcolor=ACCENT, highlightthickness=1, font=("Consolas", 10), justify="center")
        self.e_client.pack(fill="x", ipady=8)
        tk.Label(f0, text="https://discord.com/developers/applications", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7)).pack(anchor="w", pady=(4,0))

        # Autostart
        f1_outer, f1 = self._card(parent, "DÉMARRAGE AUTOMATIQUE", "🚀")
        f1_outer.pack(fill="x", padx=14, pady=6)
        tk.Label(f1, text="Se lance tout seul au démarrage du PC — même avant d’ouvrir Discord", bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        row = tk.Frame(f1, bg=CARD); row.pack(fill="x", pady=10)
        self.v_auto_start_ui = tk.BooleanVar(value=False)
        # switch déjà dans sidebar, on duplique bouton ici
        self.btn_auto = tk.Button(row, text="Activer l’auto-start", bg=ACCENT, fg="white", relief="flat", bd=0, font=("Segoe UI", 9, "bold"), padx=14, pady=8, cursor="hand2", command=self.toggle_autostart_btn)
        self.btn_auto.pack(side="left")
        tk.Button(row, text="Diagnostiquer", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=12, pady=8, cursor="hand2", command=self._diag_autostart, highlightbackground=BORDER, highlightthickness=1).pack(side="left", padx=8)
        # détail 4 méthodes
        self.auto_detail = tk.Label(f1, text="", bg=CARD, fg=SUBTLE, font=("Consolas", 7), justify="left", anchor="w")
        self.auto_detail.pack(fill="x", pady=(6,0))

        # Priorité
        f2_outer, f2 = self._card(parent, "PRIORITÉ HAUTE  •  RESTE ACTIF EN JEU", "⚡")
        f2_outer.pack(fill="x", padx=14, pady=6)
        tk.Label(f2, text="Windows ne met plus DeezerRP en pause quand tu joues (Game Mode, plein écran)", bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        row2 = tk.Frame(f2, bg=CARD); row2.pack(fill="x", pady=10)
        self.prio_status = tk.Label(row2, text="Priorité : NORMALE", bg=CARD2, fg=MUTED, font=("Segoe UI", 8, "bold"), padx=10, pady=6)
        self.prio_status.pack(side="left")
        tk.Button(row2, text="Passer en HAUTE", bg=GREEN, fg="white", relief="flat", bd=0, font=("Segoe UI", 8, "bold"), padx=12, pady=6, cursor="hand2", command=lambda: self._force_prio(True)).pack(side="left", padx=8)
        tk.Button(row2, text="Normale", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=12, pady=6, cursor="hand2", command=lambda: self._force_prio(False), highlightbackground=BORDER, highlightthickness=1).pack(side="left")
        self.prio_info = tk.Label(f2, text="HIGH_PRIORITY_CLASS • SetThreadExecutionState • keep-alive 15s", bg=CARD, fg=SUBTLE, font=("Consolas", 7))
        self.prio_info.pack(anchor="w", pady=(6,0))
        # switches
        sw = tk.Frame(f2, bg=CARD); sw.pack(fill="x", pady=8)
        tk.Label(sw, text="Toujours au-dessus", bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")
        tk.Checkbutton(sw, text="Fenêtre toujours visible", variable=self.v_top, command=self.toggle_topmost, bg=CARD, fg=MUTED, selectcolor=CARD2, font=("Segoe UI", 8)).pack(side="left", padx=12)
        self.v_web = tk.BooleanVar()
        tk.Checkbutton(sw, text="Inclure Deezer Web", variable=self.v_web, bg=CARD, fg=MUTED, selectcolor=CARD2, font=("Segoe UI", 8)).pack(side="left", padx=12)

        # Discord Priority (NOUVEAU)
        f2b_outer, f2b = self._card(parent, "PRIORITÉ DISCORD  •  PASSE DEVANT LES JEUX", "🎵")
        f2b_outer.pack(fill="x", padx=14, pady=6)
        tk.Label(f2b, text="Ton activité Deezer reste affichée même quand tu joues (écrase le statut 'Joue à...')", bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w")
        tk.Label(f2b, text="Keepalive agressif + reconnexion auto si Discord redémarre", bg=CARD, fg=SUBTLE, font=("Consolas", 7)).pack(anchor="w", pady=(2,0))
        row_prio = tk.Frame(f2b, bg=CARD); row_prio.pack(fill="x", pady=10)
        self.v_discord_prio = tk.BooleanVar(value=self.cfg.get("discord_priority", True))
        # switch custom
        self.sw_discord_prio = self._switch(row_prio, self.v_discord_prio, self.toggle_discord_priority)
        self.sw_discord_prio.pack(side="left")
        tk.Label(row_prio, text="Activité prioritaire", bg=CARD, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
        self.l_discord_prio = tk.Label(row_prio, text="ON — 5s keepalive", bg=GREEN, fg="white", font=("Segoe UI", 7, "bold"), padx=6, pady=2)
        self.l_discord_prio.pack(side="left", padx=8)
        tk.Label(f2b, text="Astuce Discord : Paramètres → Confidentialité → décoche 'Affiche le jeu en cours' pour 100% priorité", bg=CARD, fg=SUBTLE, font=("Segoe UI", 7)).pack(anchor="w", pady=(6,0))

        # Système
        f3_outer, f3 = self._card(parent, "SYSTÈME", "🖥️")
        f3_outer.pack(fill="x", padx=14, pady=6)
        self.v_web.trace_add("write", lambda *_: save_config(self._fields()))
        tk.Label(f3, text="Raccourci : Win+R → shell:startup → DeezerRP.bat / DeezerRP.vbs", bg=CARD, fg=SUBTLE, font=("Consolas", 7)).pack(anchor="w")
        tk.Label(f3, text="Tâche planifiée : schtasks /query /tn DeezerRP", bg=CARD, fg=SUBTLE, font=("Consolas", 7)).pack(anchor="w", pady=2)
        tk.Button(f3, text="Ouvrir dossier Startup", bg=CARD2, fg=MUTED, relief="flat", bd=0, font=("Segoe UI", 8), padx=12, pady=6, cursor="hand2", command=self._open_startup, highlightbackground=BORDER, highlightthickness=1).pack(anchor="w", pady=8)

    def _card(self, parent, title, icon=""):
        outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1, bd=0)
        hdr = tk.Frame(outer, bg=CARD); hdr.pack(fill="x", padx=14, pady=(12,8))
        tk.Label(hdr, text=f"{icon}  {title}", bg=CARD, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Frame(outer, bg=BORDER, height=1).pack(fill="x", padx=14)
        inner = tk.Frame(outer, bg=CARD); inner.pack(fill="both", expand=True, padx=14, pady=12)
        return outer, inner

    def show_page(self, name):
        self.current_page = name
        for k, f in self.pages.items():
            if k == name:
                f.tkraise()
        # update nav
        titles = {"dashboard": "Tableau de bord", "studio": "Personnaliser", "settings": "Système & Priorité"}
        self.top_title.configure(text=titles.get(name, name))
        for p, (outer, accent, btn) in self.nav_btns.items():
            active = p == name
            outer.configure(bg=ACCENT if active else BG_MAIN)
            accent.configure(bg=ACCENT if active else BG_MAIN)
            btn.configure(bg=CARD if active else BG_MAIN, fg=TEXT if active else MUTED, font=("Segoe UI", 9, "bold" if active else "normal"))

    # ── Helpers toggle ──
    def toggle_autostart(self):
        # appelé depuis le switch sidebar (var déjà basculée)
        want = self.v_autostart.get()
        if want:
            ok = autostart.enable()
            self.say("auto-start activé (BAT+VBS+Registre+Tâche)", "ok" if ok else "warn")
        else:
            autostart.disable()
            self.say("auto-start désactivé", "warn")
        self._sync_autostart_ui()
        self._persist()

    def toggle_autostart_btn(self):
        # appelé depuis le bouton "Activer/Désactiver" — on inverse l'état réel
        want = not autostart.is_enabled()
        self.v_autostart.set(want)
        if want:
            ok = autostart.enable()
            self.say("auto-start activé (BAT+VBS+Registre+Tâche)", "ok" if ok else "warn")
        else:
            autostart.disable()
            self.say("auto-start désactivé", "warn")
        self._sync_autostart_ui()
        self._persist()

    def _sync_autostart_ui(self):
        en = autostart.is_enabled()
        try: self.v_autostart.set(en)
        except: pass
        det = autostart.status_detail()
        txt = f"BAT:{'✓' if det['bat'] else '✗'}  VBS:{'✓' if det['vbs'] else '✗'}  Registre:{'✓' if det['registry'] else '✗'}  Tâche:{'✓' if det['task'] else '✗'}"
        try:
            self.auto_detail.configure(text=txt + ("  →  activé" if en else "  →  désactivé"))
            self.btn_auto.configure(text="Désactiver l’auto-start" if en else "Activer l’auto-start", bg=DANGER if en else ACCENT)
        except: pass
        # sidebar status
        try:
            self.sb_status.configure(text="Auto-start ON" if en else "Déconnecté" if not self.connected else "Connecté")
        except: pass

    def _diag_autostart(self):
        det = autostart.status_detail()
        messagebox.showinfo("DeezerRP — Auto-start", f"Détail :\nBAT Startup : {det['bat']}\nVBS Startup : {det['vbs']}\nRegistre Run : {det['registry']}\nTâche planifiée : {det['task']}\n\nDossier : {autostart.STARTUP_DIR}")

    def _open_startup(self):
        try:
            os.startfile(autostart.STARTUP_DIR)
        except Exception as e:
            messagebox.showinfo("Startup", str(autostart.STARTUP_DIR))

    def toggle_priority(self):
        want = self.v_prio.get()
        prio.boost(want)
        self.cfg["priority_high"] = want
        self._sync_priority_ui()
        self._persist()
        self.say(f"priorité {'HAUTE' if want else 'normale'}", "ok" if want else "warn")

    def _force_prio(self, high):
        prio.boost(high)
        self.v_prio.set(high)
        self.cfg["priority_high"] = high
        self._sync_priority_ui()
        self._persist()
        self.say(f"priorité forcée : {'HAUTE' if high else 'NORMALE'}", "ok")

    def _sync_priority_ui(self):
        high = self.v_prio.get() if hasattr(self, "v_prio") else self.cfg.get("priority_high", True)
        name = prio.current_priority_name()
        try:
            self.prio_status.configure(text=f"Priorité : {name}", bg=GREEN if "HAUTE" in name else CARD2, fg="white" if "HAUTE" in name else MUTED)
            self.prio_badge.configure(text=f"⚡ {name}", bg=GREEN if "HAUTE" in name else CARD2, fg="white" if "HAUTE" in name else MUTED)
            self.btm_source.configure(text=f"⚡ {name}" if "HAUTE" in name else self.current_source or "")
        except: pass
        # keep SB
        try:
            self.sb_left.configure(text=f" ●  Priorité {name}  •  reste actif en jeu" if "HAUTE" in name else " ●  Priorité normale")
        except: pass

    def toggle_discord_priority(self):
        want = self.v_discord_prio.get()
        self.discord_priority = want
        self.keepalive_interval = 5 if want else 12
        self.cfg["discord_priority"] = want
        try:
            self.l_discord_prio.configure(text="ON — 5s keepalive" if want else "OFF — 12s", bg=GREEN if want else CARD2, fg="white" if want else MUTED)
        except: pass
        self._persist()
        self.say(f"priorité Discord {'activée (prioritaire sur les jeux)' if want else 'désactivée'}", "ok" if want else "warn")

    def toggle_topmost(self):
        val = self.v_top.get()
        try: self.root.attributes("-topmost", val)
        except: pass
        self.cfg["always_on_top"] = val
        self._persist()

    # ── Config ──
    def _fields(self):
        # fallback aux defaults si champ vide (évite le wipe de config)
        act = self.c_type.get().strip() or DEFAULTS["activity"]
        name = self.e_name.get().strip() or DEFAULTS["app_name"]
        b1t = self.e_b1t.get().strip() or DEFAULTS["btn1_text"]
        b2t = self.e_b2t.get().strip() or DEFAULTS["btn2_text"]
        # si l'utilisateur a vidé volontairement, on garde vide seulement si c'est un URL, pas le texte
        if not self.e_b1t.get().strip():
            b1t = DEFAULTS["btn1_text"]
        if not self.e_b2t.get().strip():
            b2t = DEFAULTS["btn2_text"]
        return {
            "discord_client_id": self.e_client.get().strip(),
            "interval": self.e_interval.get().strip() or str(DEFAULTS["interval"]),
            "include_browser": self.v_web.get(),
            "show_buttons": self.v_btns.get(),
            "activity": act,
            "app_name": name,
            "show_time": self.v_time.get(),
            "small_image": self.e_small.get().strip(),
            "btn1_text": b1t, "btn1_url": self.e_b1u.get().strip(),
            "btn2_text": b2t, "btn2_url": self.e_b2u.get().strip(),
            "autostart": autostart.is_enabled(),
            "priority_high": self.v_prio.get(),
            "always_on_top": self.v_top.get(),
            "discord_priority": self.v_discord_prio.get() if hasattr(self, "v_discord_prio") else self.cfg.get("discord_priority", True),
            "minimize_to_tray": True,
        }

    def _load_cfg(self):
        c = self.cfg
        try: self.e_client.insert(0, c["discord_client_id"])
        except: pass
        try:
            self.e_interval.delete(0,"end"); self.e_interval.insert(0, str(c["interval"]))
        except: pass
        try: self.v_web.set(c["include_browser"])
        except: pass
        try: self.v_btns.set(c["show_buttons"])
        except: pass
        try: self.c_type.set(c["activity"] if c["activity"] in TYPES else "Ecoute")
        except: pass
        try: self.e_name.insert(0, c["app_name"])
        except: pass
        try: self.v_time.set(c["show_time"])
        except: pass
        try: self.e_small.insert(0, c["small_image"])
        except: pass
        try:
            self.e_b1t.delete(0,"end"); self.e_b1t.insert(0, c.get("btn1_text",""))
            self.e_b1u.delete(0,"end"); self.e_b1u.insert(0, c.get("btn1_url",""))
            self.e_b2t.delete(0,"end"); self.e_b2t.insert(0, c.get("btn2_text",""))
            self.e_b2u.delete(0,"end"); self.e_b2u.insert(0, c.get("btn2_url",""))
        except: pass
        try: self.v_prio.set(c.get("priority_high", True))
        except: pass
        try: self.v_top.set(c.get("always_on_top", False))
        except: pass
        try:
            if hasattr(self, "v_discord_prio"):
                self.v_discord_prio.set(c.get("discord_priority", True))
                self.discord_priority = c.get("discord_priority", True)
                self.keepalive_interval = 5 if self.discord_priority else 12
                try:
                    self.l_discord_prio.configure(text="ON — 5s keepalive" if self.discord_priority else "OFF — 12s", bg=GREEN if self.discord_priority else CARD2, fg="white" if self.discord_priority else MUTED)
                except: pass
        except: pass
        self._preview(); self._update_btn_preview()

    def _persist(self):
        d = self._fields()
        try: d["interval"] = int(float(d["interval"]))
        except: d["interval"] = 2
        save_config(d)

    # ── Journal / preview ──
    def say(self, msg, level="info"):
        col = {"info": "#b5bac1", "ok": GREEN, "warn": WARN, "err": DANGER}.get(level, MUTED)
        try:
            self.log.configure(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.log.insert("end", f"[{ts}] {msg}\n")
            try:
                s = self.log.index("end-2l"); e = self.log.index("end-1l")
                tag = level+ts+str(time.time())
                self.log.tag_add(tag, s, e); self.log.tag_config(tag, foreground=col)
            except: pass
            if len(self.log.get("1.0","end").splitlines()) > 120:
                self.log.delete("1.0", "2.0")
            self.log.configure(state="disabled"); self.log.see("end")
            self.sb_left.configure(text=f" ●  {msg}")
        except: pass

    def _clear_log(self):
        try:
            self.log.configure(state="normal"); self.log.delete("1.0","end"); self.log.configure(state="disabled")
        except: pass

    def _cover_photo(self, url):
        if not url or not HAS_PIL: return None
        if url in self.img_cache: return self.img_cache[url]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DeezerRP/2"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            pil = Image.open(io.BytesIO(data)).convert("RGB")
            ph = rounded_image(pil, size=140, radius=18)
            ph_small = rounded_image(pil, size=52, radius=10)
            self.img_cache[url] = ph
            self.img_cache[url+"_small"] = ph_small
            return ph
        except: return None

    def _preview(self):
        act = self.c_type.get() or "Ecoute"
        name = self.e_name.get().strip() or "Deezer"
        det = self.e_details.get().strip() or "—"
        st = self.e_state.get().strip()
        al = self.e_large_txt.get().strip()
        prefix = {"Ecoute":"ÉCOUTE","Joue":"JOUE À","Regarde":"REGARDE"}.get(act, act.upper())
        try:
            self.l_pv_type.configure(text=f"{prefix}  {name.upper()}")
            self.l_pv_title.configure(text=det[:48])
            self.l_pre_title.configure(text=det[:32])
            self.btm_title.configure(text=det[:28] if det!="—" else "Aucune lecture")
            if st:
                self.l_pv_state.configure(text=f"par {st[:48]}")
                self.l_pre_state.configure(text=f"par {st[:24]}")
                self.btm_artist.configure(text=st[:28])
            else:
                self.l_pv_state.configure(text="par —" if det!="—" else "En attente…")
                self.l_pre_state.configure(text="" if det!="—" else "En attente")
                self.btm_artist.configure(text=al[:28] if al else "Deezer")
            self.l_pv_album.configure(text=al[:60] if al else "")
            if self.v_time.get() and self.start_time:
                el = int(time.time()-self.start_time); mm, ss = divmod(el,60); hh, mm = divmod(mm,60)
                fmt = f"{hh:02d}:{mm:02d}:{ss:02d}" if hh else f"{mm:02d}:{ss:02d}"
                self.l_pv_time.configure(text=f"{fmt} écoulées"); self.l_pre_time.configure(text=fmt)
                self.btm_time_l.configure(text=fmt); self.btm_time_r.configure(text="LIVE")
            else:
                self.l_pv_time.configure(text="temps masqué" if not self.v_time.get() else "")
                self.l_pre_time.configure(text="")
                self.btm_time_l.configure(text="0:00"); self.btm_time_r.configure(text="VEILLE" if not self.start_time else "LIVE")
            if self.current_source:
                self.l_pv_source.configure(text=self.current_source)
                if "HAUTE" not in (prio.current_priority_name() or ""):
                    self.btm_source.configure(text=self.current_source)
            url = self.e_large.get().strip()
            if url:
                ph = self._cover_photo(url)
                if ph:
                    self.cover_photo = ph
                    self.c_cover.delete("all"); self.c_cover.create_image(70,70, image=self.cover_photo)
                    # small btm
                    small = self.img_cache.get(url+"_small")
                    if small:
                        self.coversmall = small
                        self.btm_cover.delete("all"); self.btm_cover.create_image(26,26, image=self.coversmall)
                        self.c_preview.delete("all"); self.c_preview.create_image(36,36, image=small)
            else:
                if not self.current_track:
                    self._draw_cover_placeholder_small(self.c_cover,140,140)
            self._update_btn_preview()
        except Exception as e:
            pass

    def _update_btn_preview(self):
        try:
            show = self.v_btns.get()
            if show:
                self.pv_btns.pack(fill="x", padx=14, pady=(8,12))
                t1 = self.e_b1t.get().strip() or "Écouter sur Deezer"; t2 = self.e_b2t.get().strip() or "Ouvrir Deezer"
                self.pv_b1.configure(text=f"▶ {t1[:22]}"); self.pv_b2.configure(text=t2[:18])
                if not self.e_b2u.get().strip() or not self.e_b2t.get().strip():
                    self.pv_b2.pack_forget()
                else:
                    if not self.pv_b2.winfo_manager():
                        self.pv_b2.pack(side="left", fill="x", expand=True, padx=(6,0))
            else:
                self.pv_btns.pack_forget()
        except: pass

    def _bind_preview(self):
        for w in (self.e_details, self.e_state, self.e_name, self.e_large, self.e_large_txt, self.c_type):
            try: w.bind("<KeyRelease>", lambda e: self._preview()); w.bind("<<ComboboxSelected>>", lambda e: self._preview())
            except: pass

    # ── Connexion ──
    def do_connect(self, silent=False):
        cid = self.e_client.get().strip()
        if not cid:
            if not silent:
                messagebox.showwarning("DeezerRP", "Colle ton Client ID Discord.\nPortal → discord.com/developers/applications")
            return
        try:
            self.presence = DeezerPresence(cid); self.presence.connect()
        except Exception as e:
            self.say(f"connexion impossible : {e}", "err")
            if not silent:
                messagebox.showerror("DeezerRP", f"Connexion impossible : {e}\nOuvre Discord Desktop.")
            self.presence=None; return
        self._persist(); self.connected=True
        self.b_connect.configure(state="disabled", bg=CARD2, fg=MUTED)
        self.b_disconnect.configure(state="normal", bg=CARD2, fg=TEXT)
        self._draw_dot(SUCCESS); self.l_status.configure(text="Connecté", fg=SUCCESS)
        self._sb_dot(SUCCESS); self.sb_status.configure(text="Connecté", fg=SUCCESS)
        self.live_label.configure(text="CONNECTÉ", fg=SUCCESS)
        self._draw_now_dot(SUCCESS)
        self.say("connecté à Discord ✓", "ok")
        if self.v_auto.get() and not self.auto_on:
            self.toggle_auto()

    def do_disconnect(self):
        self.auto_on=False; self.v_auto.set(False)
        try: self.mini_live.configure(text="● PAUSE", fg=MUTED)
        except: pass
        if self.presence:
            self.presence.disconnect(); self.presence=None
        self.connected=False; self.last_key=None
        self.b_connect.configure(state="normal", bg=ACCENT, fg="white")
        self.b_disconnect.configure(state="disabled", bg=CARD2, fg=MUTED)
        self._draw_dot(SUBTLE); self.l_status.configure(text="Déconnecté", fg=MUTED)
        self._sb_dot(SUBTLE); self.sb_status.configure(text="Déconnecté", fg=MUTED)
        self.live_label.configure(text="VEILLE", fg=MUTED)
        self._draw_now_dot(SUBTLE)
        self._draw_play(False)
        self.say("déconnecté", "warn")

    def clear_presence(self):
        if self.presence and self.presence.connected:
            try: self.presence.rpc.clear(); self.say("statut effacé","warn")
            except Exception as e: self.say(f"erreur : {e}", "err")
        self.last_key=None; self.start_time=None; self._preview()

    # ── Auto ──
    def toggle_auto(self):
        if self.v_auto.get() and not self.auto_on:
            self.auto_on=True
            try: self.mini_live.configure(text="● LIVE", fg=SUCCESS); self.live_label.configure(text="LIVE", fg=SUCCESS)
            except: pass
            threading.Thread(target=self._worker, daemon=True).start()
            self.say("détection Deezer LIVE — silencieux", "ok")
        else:
            self.auto_on=False
            try: self.mini_live.configure(text="● PAUSE", fg=MUTED)
            except: pass
            if not self.connected:
                try: self.live_label.configure(text="VEILLE", fg=MUTED)
                except: pass
            self.say("détection en pause","warn")

    def fetch_once(self):
        try: self.b_refresh.configure(text="…")
        except: pass
        threading.Thread(target=self._fetch_and_fill, daemon=True).start()
        self.root.after(800, lambda: self.b_refresh.configure(text="↻") if hasattr(self, 'b_refresh') else None)

    def _interval(self):
        try: return max(1, min(30, float(self.e_interval.get().strip().replace(",","."))))
        except: return 2

    def _worker(self):
        while self.auto_on:
            try: self._fetch_and_fill(send=True)
            except: pass
            iv=self._interval()
            for _ in range(int(iv*5)):
                if not self.auto_on: break
                time.sleep(0.2)

    def _fetch_and_fill(self, send=False):
        track=deezer.current_track(include_browser=self.v_web.get())
        if track is None:
            self.events.put(("idle",)); return
        info=deezer.track_info(track["artist"], track["title"])
        self.events.put(("track", track, info, send))

    def _drain(self):
        try:
            while True:
                ev=self.events.get_nowait()
                if ev[0]=="idle":
                    try:
                        self.l_now.configure(text="Rien en lecture — en attente…", fg=MUTED)
                        self.stats_track.configure(text="Aucun morceau")
                        self._draw_now_dot(SUBTLE)
                        self.pv_live.configure(text="● VEILLE", fg=MUTED)
                        self.btm_time_r.configure(text="VEILLE")
                        self._draw_play(False)
                        if self.last_key is not None:
                            self.last_key=None; self.start_time=None; self.current_track=None
                            self.clear_presence(); self.say("pause : statut effacé","warn")
                        self._preview()
                    except: pass
                else:
                    _, track, info, send = ev
                    self._fill(track, info)
                    if send and self.presence and self.presence.connected:
                        self._send_current()
        except queue.Empty:
            pass
        self.root.after(280, self._drain)

    def _fill(self, track, info):
        cover, album, link = info
        title=track["title"]; artist=track["artist"] or ""
        self.current_track=track
        try:
            self.l_now.configure(text=f"▶ {artist+' — ' if artist else ''}{title}", fg=TEXT)
            self.stats_track.configure(text=f"▶ {artist+' — ' if artist else ''}{title}  [{track['source']}]")
            self._draw_now_dot(SUCCESS); self.pv_live.configure(text="● EN ÉCOUTE", fg=SUCCESS)
            self.btm_time_r.configure(text="LIVE"); self._draw_play(True)
        except: pass
        self.current_source=track["source"]
        self._set(self.e_details, title); self._set(self.e_state, artist)
        if cover: self._set(self.e_large, cover)
        self._set(self.e_large_txt, album or "")
        if link: self._set(self.e_b1u, link)
        elif not self.e_b1u.get().strip(): self._set(self.e_b1u, deezer.search_url(track["artist"], title))
        self._preview()

    @staticmethod
    def _set(entry, value):
        try: entry.delete(0,"end"); entry.insert(0, value or "")
        except: pass

    def _send_current(self, force=False):
        details=self.e_details.get().strip()
        if not details: return
        key=(self.c_type.get(), self.e_name.get(), details, self.e_state.get(), self.e_large.get(), self.e_b1u.get())
        # si même morceau mais force (keepalive) on renvoie quand même pour rester prioritaire sur le jeu
        is_new = key != self.last_key
        if is_new:
            self.last_key=key; self.start_time=int(time.time()) if self.v_time.get() else None
        elif not force:
            # anti-spam : ne renvoie pas si < keepalive et même clé
            if time.time() - self.last_send < self.keepalive_interval:
                return
        if not self.presence or not self.presence.connected:
            # tentative de reconnexion auto (prioritaire)
            try:
                cid = self.e_client.get().strip()
                if cid:
                    self.presence = DeezerPresence(cid)
                    self.presence.connect()
                    self.connected = True
                    self.b_connect.configure(state="disabled", bg=CARD2, fg=MUTED)
                    self.b_disconnect.configure(state="normal", bg=CARD2, fg=TEXT)
                    self._draw_dot(SUCCESS); self.l_status.configure(text="Connecté", fg=SUCCESS)
                    self._sb_dot(SUCCESS); self.sb_status.configure(text="Connecté", fg=SUCCESS)
                    self.say("reconnexion Discord auto ✓", "ok")
            except Exception as e:
                self.say(f"reconnexion échouée : {e}", "err")
                return
        buttons=None
        if self.v_btns.get():
            buttons=[]
            if self.e_b1t.get().strip() and self.e_b1u.get().strip():
                buttons.append({"label": self.e_b1t.get().strip()[:32], "url": self.e_b1u.get().strip()})
            if self.e_b2t.get().strip() and self.e_b2u.get().strip():
                buttons.append({"label": self.e_b2t.get().strip()[:32], "url": self.e_b2u.get().strip()})
        try:
            # priorité Discord : on force l'update même si Discord affiche un jeu
            self.presence.update(activity=self.c_type.get() or "Ecoute", name=self.e_name.get().strip() or "Deezer",
                                 details=details[:128], state=self.e_state.get().strip()[:128] or None,
                                 start=self.start_time, large_image=self.e_large.get().strip() or None,
                                 large_text=self.e_large_txt.get().strip()[:128] or None,
                                 small_image=self.e_small.get().strip() or None, small_text=self.current_source,
                                 buttons=buttons or None)
            self.last_send = time.time()
            self.say(f"envoyé → {details}" + (" (keepalive prioritaire)" if not is_new and force else ""), "ok")
            self.sb_right.configure(text=f"✓ prioritaire {time.strftime('%H:%M:%S')}")
        except Exception as e:
            msg = str(e).lower()
            # si pipe fermé, on tente reconnect au prochain tick
            if "pipe" in msg or "closed" in msg or "not connected" in msg or "connection" in msg:
                self.connected = False
                try:
                    if self.presence:
                        self.presence.disconnect()
                except: pass
                self.presence = None
                self._draw_dot(WARN); self.l_status.configure(text="Reconnexion…", fg=WARN)
                self.say(f"Discord déconnecté, reconnexion auto… : {e}", "warn")
            else:
                self.say(f"erreur Discord : {e}", "err")
                self.sb_right.configure(text=f"✕ {e}")
        self._persist()

    def send_fields(self):
        if not self.presence or not self.presence.connected:
            messagebox.showwarning("DeezerRP","Connecte-toi d'abord."); return
        self.last_key=None; self._send_current(); self._preview()

    # ── Animations ──
    def _pulse(self):
        self.pulse=(self.pulse+1)%20
        try:
            if self.auto_on and self.connected:
                self.live_canvas.delete("all")
                r=5+(self.pulse%10)*0.25
                self.live_canvas.create_oval(9-r,9-r,9+r,9+r, outline="#1a2e1a", width=1)
                self.live_canvas.create_oval(5,5,13,13, fill=SUCCESS, outline="")
            elif self.auto_on:
                self.live_canvas.delete("all")
                col=WARN if self.pulse<10 else SUCCESS
                self.live_canvas.create_oval(5,5,13,13, fill=col, outline="")
            else:
                self.live_canvas.delete("all")
                self.live_canvas.create_oval(5,5,13,13, fill=SUBTLE, outline="")
        except: pass
        self.root.after(120, self._pulse)

    def _tick(self):
        self._preview()
        try:
            self.eq_canvas.delete("all")
            playing=self.current_track is not None and self.last_key is not None and self.auto_on
            import random
            for i in range(5):
                h=4 if not playing else random.randint(3,12) if i%2==0 else random.randint(2,8)
                x0=i*9+2
                self.eq_canvas.create_rectangle(x0,14-h,x0+5,14, fill=GREEN if playing else SUBTLE, outline="")
            # sidebar eq
            self.sb_eq.delete("all")
            for i in range(6):
                h=3 if not playing else random.randint(2,10)
                x0=i*8+2
                self.sb_eq.create_rectangle(x0,12-h,x0+4,12, fill=GREEN if playing else SUBTLE, outline="")
            self._draw_play(playing)
        except: pass
        # keepalive prioritaire Discord : renvoie même morceau toutes les X sec pour passer devant le jeu
        try:
            if self.connected and self.presence and self.presence.connected and self.last_key and self.auto_on:
                if time.time() - self.last_send >= self.keepalive_interval:
                    self._send_current(force=True)
        except: pass
        self.root.after(500, self._tick)

    def _shimmer_tick(self):
        try:
            self.progress_bg.delete("all")
            w=self.progress_bg.winfo_width() or 400
            self.progress_bg.create_rectangle(0,0,w,6, fill="#1e1f2a", outline="")
            if self.current_track and self.start_time and self.v_time.get():
                self.shimmer=(self.shimmer+4)%(w+50)
                self.progress_bg.create_rectangle(self.shimmer-50,0,self.shimmer,6, fill="#2a2f45", outline="")
                self.progress_bg.create_rectangle(self.shimmer-14,0,self.shimmer-6,6, fill=ACCENT, outline="")
                # bottom too
                self.btm_progress.delete("all")
                self.btm_progress.create_rectangle(0,0,w,4, fill="#1a1c26", outline="")
                self.btm_progress.create_rectangle(self.shimmer-50,0,self.shimmer,4, fill="#2a2f45", outline="")
                self.btm_progress.create_rectangle(self.shimmer-14,0,self.shimmer-6,4, fill=GREEN, outline="")
            else:
                self.progress_bg.create_rectangle(0,0,int(w*0.15),6, fill="#2a2f45", outline="")
                self.btm_progress.delete("all")
                self.btm_progress.create_rectangle(0,0,int(w*0.12),4, fill="#2a2f45", outline="")
        except: pass
        self.root.after(45, self._shimmer_tick)

    def _draw_now_dot(self, col):
        try: self.now_dot.delete("all"); self.now_dot.create_oval(0,0,8,8, fill=col, outline="")
        except: pass

    # ── Preset / fermeture ──
    def save_preset(self):
        p=filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Preset","*.json")])
        if p:
            save_config(self._fields())
            try: Path(p).write_text(json.dumps(self._fields(), indent=2, ensure_ascii=False), encoding="utf-8"); self.say(f"preset sauvé → {p}","ok")
            except Exception as e: self.say(f"erreur preset : {e}", "err")
    def load_preset(self):
        p=filedialog.askopenfilename(filetypes=[("Preset","*.json")])
        if not p: return
        try:
            d={**DEFAULTS, **json.loads(Path(p).read_text(encoding="utf-8"))}
            self.e_client.delete(0,"end"); self.e_client.insert(0, d["discord_client_id"])
            self.c_type.set(d["activity"] if d["activity"] in TYPES else "Ecoute")
            for e,k in [(self.e_name,"app_name"),(self.e_details,"details"),(self.e_state,"state"),(self.e_large,"large"),(self.e_large_txt,"large_text"),(self.e_small,"small_image"),(self.e_b1t,"btn1_text"),(self.e_b1u,"btn1_url"),(self.e_b2t,"btn2_text"),(self.e_b2u,"btn2_url")]:
                try: e.delete(0,"end"); e.insert(0, str(d.get(k,"")))
                except: pass
            self._preview(); self._update_btn_preview(); self.say(f"preset chargé → {p}","ok")
        except Exception as e: self.say(f"erreur preset : {e}", "err")

    # ── Tray & arrière-plan ──
    def _init_tray(self):
        if not HAS_TRAY or tray_utils is None:
            return
        try:
            self.tray_manager = tray_utils.TrayManager(self)
            self.tray_manager.run()
        except Exception as e:
            print("tray init fail", e)
            self.tray_manager = None

    def _show_toast(self, title, msg, duration=4000):
        """Notification Windows + fallback tkinter."""
        # essaie tray -> plyer -> fallback
        try:
            if HAS_TRAY and tray_utils:
                tray_utils.notify(title, msg, icon=getattr(self, 'tray_manager', None) and self.tray_manager.icon, fallback_tk=lambda t,m: self._tk_toast(t,m,duration))
                return
        except: pass
        self._tk_toast(title, msg, duration)

    def _tk_toast(self, title, msg, duration=4000):
        """Toast custom tkinter (coin bas-droit, style Discord/Spotify)."""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes("-topmost", True)
            toast.configure(bg=CARD)
            # taille
            w, h = 360, 84
            # position bas-droit
            try:
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                x = sw - w - 18
                y = sh - h - 48
                toast.geometry(f"{w}x{h}+{x}+{y}")
            except:
                toast.geometry(f"{w}x{h}+{100}+{100}")
            # bordure
            outer = tk.Frame(toast, bg=CARD, highlightbackground=BORDER2, highlightthickness=1)
            outer.pack(fill="both", expand=True)
            head = tk.Frame(outer, bg=CARD)
            head.pack(fill="x", padx=14, pady=(12,4))
            tk.Label(head, text="♪", bg=CARD, fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(side="left")
            tk.Label(head, text=title, bg=CARD, fg=TEXT, font=("Segoe UI", 9, "bold")).pack(side="left", padx=8)
            tk.Label(head, text="✕", bg=CARD, fg=MUTED, font=("Segoe UI", 8), cursor="hand2").pack(side="right")
            tk.Label(outer, text=msg, bg=CARD, fg=MUTED, font=("Segoe UI", 8), wraplength=330, justify="left", anchor="w").pack(fill="x", padx=14, pady=(0,12))
            # barre verte
            bar = tk.Frame(outer, bg=GREEN, height=3)
            bar.pack(fill="x", side="bottom")
            # auto close
            toast.after(duration, toast.destroy)
            # anim slide
            toast.attributes("-alpha", 0.0)
            def fade_in(a=0.0):
                if a < 1.0:
                    try: toast.attributes("-alpha", a)
                    except: pass
                    toast.after(20, lambda: fade_in(a+0.12))
            fade_in()
        except Exception as e:
            print("toast fail", e)

    def show_from_tray(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except: pass

    def toggle_auto_from_tray(self):
        self.v_auto.set(not self.v_auto.get())
        self.toggle_auto()
        if self.tray_manager:
            self.tray_manager.update_menu()

    def really_quit(self):
        self._force_quit = True
        self.on_close()

    def on_close(self):
        # si minimize_to_tray et pas force_quit → passe en arrière-plan
        if not self._force_quit and self.cfg.get("minimize_to_tray", True):
            self._persist()
            try:
                self.root.withdraw()
            except: pass
            # toast + tray
            self._show_toast("DeezerRP — arrière-plan", "♪ Tourne en arrière-plan\nTon activité Discord reste prioritaire même en jeu.\n(Clic droit sur l'icône tray → Quitter pour fermer)")
            self.say("réduit en arrière-plan — tray actif (Discord prioritaire)", "ok")
            # assure que le tray est lancé
            if not self.tray_manager or not self.tray_manager.running:
                self._init_tray()
            # keepalive continue
            return
        # vrai quit
        self._persist()
        self.auto_on=False
        if self.presence:
            try: self.presence.disconnect()
            except: pass
        try:
            if self.tray_manager:
                self.tray_manager.stop()
        except: pass
        self.root.destroy()

def main():
    root=tk.Tk()
    # cacher console si python.exe
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except: pass
    # boost priorité très tôt
    try:
        cfg=load_config()
        if cfg.get("priority_high", True):
            prio.boost(True)
    except: pass
    App(root)
    root.mainloop()

if __name__=="__main__":
    main()
