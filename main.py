#!/usr/bin/env python3
"""SSH Starter desktop application. Python standard library only."""
from __future__ import annotations

import base64
from datetime import datetime
import json
import os
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

APP_NAME = "SSH Starter"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "SSHStarter"
CONFIG = APP_DIR / "settings.json"
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ICON_PATH = RESOURCE_DIR / "assets" / "ssh-starter.ico"
GREEN = "#b5f275"
BG = "#101313"
PANEL = "#171b1b"
ENTRY = "#111514"
TEXT = "#f0f2ed"
MUTED = "#89938d"
LINE = "#2a302e"


def defaults():
    return {"host": "", "port": 22, "user": "", "target_os": "linux", "program": "", "args": "", "workdir": "", "geometry": "1050x760+120+90"}


def read_config():
    try:
        return {**defaults(), **json.loads(CONFIG.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return defaults()


def save_config(cfg):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def ssh_base(cfg):
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("OpenSSH istemcisi bulunamadı. Windows Ayarları > İsteğe bağlı özellikler bölümünden OpenSSH Client'ı kur.")
    host = cfg["host"].strip()
    if not host or host.startswith("-"):
        raise ValueError("Geçerli bir SSH host adı veya IP adresi gir.")
    user = cfg["user"].strip()
    if user.startswith("-") or "@" in user:
        raise ValueError("Kullanıcı adı '-' ile başlayamaz ve '@' içeremez.")
    destination = f"{user}@{host}" if user else host
    args = [ssh, "-T"]
    if int(cfg["port"]) != 22:
        args.extend(["-p", str(int(cfg["port"]))])
    args.extend(["-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", destination])
    return args


def run_ssh(cfg, remote, timeout=20):
    result = subprocess.run(ssh_base(cfg) + [remote], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError((result.stderr.strip() or result.stdout.strip() or f"SSH komutu {result.returncode} koduyla tamamlandı.")[-2500:])
    return result.stdout.strip()


def ps_quote(value):
    return "'" + value.replace("'", "''") + "'"


def powershell_remote(script):
    payload = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return "powershell -NoProfile -NonInteractive -EncodedCommand " + payload


def start_command(cfg):
    program, args, cwd = cfg["program"].strip(), cfg["args"].strip(), cfg["workdir"].strip()
    if not program:
        raise ValueError("Çalıştırılacak uzak dosyanın yolunu gir.")
    if cfg["target_os"] == "windows":
        ps = "$ErrorActionPreference='Stop'; $p=" + ps_quote(program) + "; $a=" + ps_quote(args) + "; $wd=" + ps_quote(cwd)
        ps += "; $out=Join-Path $env:TEMP 'ssh-starter.out.log'; $err=Join-Path $env:TEMP 'ssh-starter.err.log'; $pidFile=Join-Path $env:TEMP 'ssh-starter.pid'; $start=@{FilePath=$p; ArgumentList=$a; RedirectStandardOutput=$out; RedirectStandardError=$err; PassThru=$true}; if ($wd) { $start.WorkingDirectory=$wd }; if ($p.ToLower().EndsWith('.bat')) { $start.FilePath='cmd.exe'; $start.ArgumentList='/d /s /c ""'+$p+'" '+$a+'"' }; $proc=Start-Process @start; $proc.Id | Out-File -Encoding ascii $pidFile -Force; $proc.Id"
        return powershell_remote(ps)
    command = "exec " + shlex.quote(program)
    if args:
        command += " " + " ".join(shlex.quote(arg) for arg in shlex.split(args))
    body = ("cd " + shlex.quote(cwd) + " && " if cwd else "") + command
    return "nohup sh -lc " + shlex.quote(body) + " > /tmp/ssh-starter.log 2>&1 < /dev/null & echo $! > /tmp/ssh-starter.pid; sleep .3; cat /tmp/ssh-starter.pid"


def snapshot_remote(cfg):
    if cfg["target_os"] == "windows":
        script = "$p=Get-Process -Id (Get-Content (Join-Path $env:TEMP 'ssh-starter.pid') -ErrorAction SilentlyContinue) -ErrorAction SilentlyContinue; if ($p) {$s='running:'+ $p.Id} else {$s='stopped'}; Write-Output ('__SSH_STARTER_STATUS__:'+$s); Get-Content (Join-Path $env:TEMP 'ssh-starter.out.log'),(Join-Path $env:TEMP 'ssh-starter.err.log') -Tail 100 -ErrorAction SilentlyContinue"
        return powershell_remote(script)
    return "if test -f /tmp/ssh-starter.pid; then p=$(cat /tmp/ssh-starter.pid); if kill -0 \"$p\" 2>/dev/null; then s=running:$p; else s=stopped; fi; else s=stopped; fi; printf '__SSH_STARTER_STATUS__:%s\\n' \"$s\"; tail -n 100 /tmp/ssh-starter.log 2>/dev/null || true"


class SSHStarter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = read_config()
        self._custom_window = sys.platform == "win32"
        self.running = False
        self.busy = False
        self.polling = False
        self.closing = False
        self.ui_events = queue.Queue()
        self._maximized = False
        self._restore_geometry = ""
        self.poll_after_id = None
        self.geometry_after_id = None
        self.last_remote_logs = ""
        self.last_process_state = None
        self.title("SSH Starter")
        if sys.platform == "win32":
            try:
                self.iconbitmap(default=str(ICON_PATH))
            except tk.TclError:
                pass
        if self._custom_window:
            # Set the redirect flag while withdrawn so Windows never paints
            # its own caption before our custom title bar is ready.
            self.withdraw()
            self.update_idletasks()
            self.overrideredirect(True)
        self.geometry(self.cfg["geometry"])
        self.minsize(760, 600)
        self.configure(bg=BG)
        # Pass the family as one Tcl list element; a space-delimited string is
        # parsed as separate font fields (family, size, weight) by Tk on Windows.
        self.option_add("*Font", ("Segoe UI", 10))
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._style()
        self._build()
        self._load_fields()
        self.bind("<Configure>", self._geometry_changed)
        if self._custom_window:
            self.update_idletasks()
            self._enable_taskbar_button()
            self.deiconify()
        self.after(100, self._process_ui_events)
        self.after(900, self._poll)

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=ENTRY, background=ENTRY, foreground=TEXT, arrowcolor=GREEN, bordercolor=LINE, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", ENTRY)], foreground=[("readonly", TEXT)])
        style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=ENTRY, arrowcolor=MUTED, bordercolor=ENTRY)

    def _window_button(self, parent, text, command, hover, fg="#c7cec8"):
        button = tk.Button(parent, text=text, command=command, bg="#151a17", fg=fg, activebackground=hover,
                           activeforeground="#ffffff", relief="flat", bd=0, width=5,
                           font=("Segoe UI", 10), cursor="hand2")
        button.bind("<Enter>", lambda _e: button.configure(bg=hover))
        button.bind("<Leave>", lambda _e: button.configure(bg="#151a17"))
        return button

    def _enable_taskbar_button(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetAncestor(self.winfo_id(), 2)  # GA_ROOT
            if not hwnd:
                hwnd = self.winfo_id()
            # A borderless Tk window is otherwise omitted from the taskbar.
            # Set only the extended app-window flag while the window is hidden.
            exstyle = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            exstyle = (exstyle | 0x00040000) & ~0x00000080  # APPWINDOW, not TOOLWINDOW
            user32.SetWindowLongW(hwnd, -20, exstyle)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27)
        except (AttributeError, OSError):
            pass

    def _begin_window_drag(self, event):
        if self._maximized:
            self._toggle_maximize()
        self._drag_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y())

    def _move_window_drag(self, event):
        if not hasattr(self, "_drag_origin"):
            return
        x0, y0, wx, wy = self._drag_origin
        self.geometry(f"+{wx + event.x_root - x0}+{wy + event.y_root - y0}")

    def _begin_resize(self, event, direction):
        self._resize_origin = (event.x_root, event.y_root, self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height(), direction)

    def _resize_window(self, event):
        if not hasattr(self, "_resize_origin") or self._maximized:
            return
        x0, y0, wx, wy, width, height, direction = self._resize_origin
        dx, dy = event.x_root - x0, event.y_root - y0
        min_w, min_h = self.minsize()
        if "e" in direction:
            width = max(min_w, width + dx)
        if "s" in direction:
            height = max(min_h, height + dy)
        if "w" in direction:
            new_width = max(min_w, width - dx)
            wx += width - new_width
            width = new_width
        self.geometry(f"{width}x{height}+{wx}+{wy}")

    def _add_resize_handles(self):
        handles = [
            ("w", {"x": 0, "y": 42, "width": 6, "relheight": 1, "height": -48}, "sb_h_double_arrow"),
            ("e", {"relx": 1, "x": -6, "y": 42, "width": 6, "relheight": 1, "height": -48}, "sb_h_double_arrow"),
            ("s", {"x": 6, "rely": 1, "y": -6, "relwidth": 1, "width": -12, "height": 6}, "sb_v_double_arrow"),
            ("sw", {"x": 0, "rely": 1, "y": -6, "width": 9, "height": 6}, "sb_h_double_arrow"),
            ("se", {"relx": 1, "x": -9, "rely": 1, "y": -6, "width": 9, "height": 6}, "sb_h_double_arrow"),
        ]
        for direction, geometry, cursor in handles:
            handle = tk.Frame(self, bg=BG, cursor=cursor, takefocus=False)
            handle.place(**geometry)
            handle.bind("<ButtonPress-1>", lambda event, d=direction: self._begin_resize(event, d))
            handle.bind("<B1-Motion>", self._resize_window)

    def _toggle_maximize(self):
        if self._maximized:
            if self._restore_geometry:
                self.geometry(self._restore_geometry)
            self._maximized = False
            self.maximize_btn.configure(text="□")
            return
        self._restore_geometry = self.geometry()
        left, top, right, bottom = self._work_area()
        self.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
        self._maximized = True
        self.maximize_btn.configure(text="❐")

    def _work_area(self):
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class RECT(ctypes.Structure):
                    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

                rect = RECT()
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                    return rect.left, rect.top, rect.right, rect.bottom
            except (AttributeError, OSError):
                pass
        return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def _minimize_window(self):
        if sys.platform == "win32":
            try:
                hwnd = self.winfo_id()
                import ctypes
                hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2) or hwnd
                ctypes.windll.user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
                return
            except (AttributeError, OSError):
                pass
        self.iconify()

    def _build(self):
        self.titlebar = tk.Frame(self, bg="#101513", height=42, highlightbackground="#29342e", highlightthickness=1)
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)
        dots = tk.Frame(self.titlebar, bg="#101513")
        dots.pack(side="right", padx=(0, 14))
        self._title_dot(dots, "#e47768", self.on_close).pack(side="left", padx=(0, 5))
        self._title_dot(dots, "#e5bd58", self._minimize_window).pack(side="left", padx=5)
        self._title_dot(dots, "#8fc66a", self._toggle_maximize).pack(side="left", padx=(5, 0))
        title = tk.Label(self.titlebar, text="ssh-starter · kontrol paneli", bg="#101513", fg="#8da49a", font=("Consolas", 9))
        title.place(relx=0.5, rely=0.5, anchor="center")
        # A quiet green-gray rule echoes the reference's thin lower edge.
        tk.Frame(self.titlebar, bg="#26372d", height=1).place(relx=0, rely=1, relwidth=1, anchor="sw")
        for widget in (self.titlebar, title):
            widget.bind("<ButtonPress-1>", self._begin_window_drag)
            widget.bind("<B1-Motion>", self._move_window_drag)

        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        self.side = tk.Frame(outer, bg="#111414", width=210, highlightbackground="#242928", highlightthickness=1)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        logo = tk.Frame(self.side, bg="#111414"); logo.pack(fill="x", padx=20, pady=(28, 42))
        mark = tk.Label(logo, text="›_", font=("Consolas", 18, "bold"), fg=GREEN, bg="#1b2417", width=3, height=1); mark.pack(side="left", padx=(0, 10))
        tk.Label(logo, text="ssh", fg=TEXT, bg="#111414", font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(logo, text="starter", fg=GREEN, bg="#111414", font=("Segoe UI", 16)).pack(side="left")
        self._label(self.side, "ÇALIŞMA ALANI", 8, MUTED).pack(anchor="w", padx=20, pady=(0, 12))
        tk.Label(self.side, text="  ◈   Kontrol paneli", anchor="w", fg=GREEN, bg="#202622", font=("Segoe UI", 10, "bold"), padx=10, pady=10).pack(fill="x", padx=12)
        bottom = tk.Frame(self.side, bg="#111414"); bottom.pack(side="bottom", fill="x", padx=14, pady=16)
        card = tk.Frame(bottom, bg=PANEL, highlightbackground=LINE, highlightthickness=1); card.pack(fill="x", pady=(0, 12))
        tk.Label(card, text="⌘  OpenSSH kullanılıyor", fg=TEXT, bg=PANEL, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 3))
        tk.Label(card, text="Anahtarların yerel bilgisayarında kalır.", fg=MUTED, bg=PANEL, font=("Segoe UI", 8), wraplength=160, justify="left").pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(bottom, text="●  YEREL MASAÜSTÜ UYGULAMASI", fg="#849087", bg="#111414", font=("Consolas", 7)).pack(anchor="w")

        main = tk.Frame(outer, bg=BG); main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=BG, highlightbackground="#242928", highlightthickness=1, height=48); top.pack(fill="x"); top.pack_propagate(False)
        tk.Label(top, text="Çalışma alanı   /   Kontrol paneli", bg=BG, fg="#aab2ac", font=("Segoe UI", 9)).pack(side="left", padx=25)
        self.connection_state = tk.Label(top, text="●  SSH BEKLENİYOR", bg="#1b211d", fg="#aab2ac", font=("Consolas", 8), padx=10, pady=6)
        self.connection_state.pack(side="right", padx=18)
        area = tk.Frame(main, bg=BG); area.pack(fill="both", expand=True, padx=27, pady=22)
        heading = tk.Frame(area, bg=BG); heading.pack(fill="x", pady=(0, 18))
        self._label(heading, "—  SSH İLE UZAK ÇALIŞTIRMA", 8, GREEN).pack(anchor="w")
        tk.Label(heading, text="Sunucunu çalıştır.", bg=BG, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=(7, 2))
        tk.Label(heading, text="SSH ile bağlan, programını başlat ve çıktıları takip et.", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w")

        self._panel(area, "SSH BAĞLANTISI", "Sunucu ayarları", "Bağlantı bilgileri ve uzak dosyanın konumu").pack(fill="x", pady=(0, 13))
        form = self._last_panel
        grid = tk.Frame(form, bg=PANEL); grid.pack(fill="x", padx=17, pady=(0, 14))
        self.entry_widgets = {}
        self.placeholders = {}
        self.vars = {k: tk.StringVar() for k in ("host", "user", "port", "program", "args", "workdir")}
        self._entry(grid, "HOST ADI VEYA IP", "host", "ör. 192.168.1.42", 0, 0, 2)
        self._entry(grid, "KULLANICI ADI", "user", "ör. deploy", 1, 0)
        self._entry(grid, "SSH PORTU", "port", "22", 1, 1)
        tk.Frame(grid, bg=LINE, height=1).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(18, 14))
        self._label(grid, "HEDEF SİSTEM", 8, MUTED).grid(row=3, column=0, sticky="w", pady=(0, 7))
        self.os_var = tk.StringVar(value="Linux")
        combo = ttk.Combobox(grid, textvariable=self.os_var, values=("Linux", "Windows"), state="readonly", width=18)
        combo.grid(row=4, column=0, sticky="ew", padx=(0, 7)); combo.bind("<<ComboboxSelected>>", self._os_changed)
        self._entry(grid, "DOSYA YOLU", "program", "/home/deploy/app/server", 3, 1, 1, below="Örn: Linux çalıştırılabilir dosya, Windows .exe veya .bat")
        self._entry(grid, "ARGÜMANLAR · İSTEĞE BAĞLI", "args", "--port 3000", 5, 0)
        self._entry(grid, "ÇALIŞMA DİZİNİ · İSTEĞE BAĞLI", "workdir", "/home/deploy/app", 5, 1)
        controls = tk.Frame(form, bg=PANEL); controls.pack(fill="x", padx=17, pady=(0, 14))
        self.autostart = tk.BooleanVar(value=self._autostart_enabled())
        tk.Checkbutton(controls, text="Bilgisayar açılınca uygulamayı başlat", variable=self.autostart, command=self._toggle_autostart, bg=PANEL, fg=MUTED, selectcolor=ENTRY, activebackground=PANEL, activeforeground=TEXT, font=("Segoe UI", 8), cursor="hand2").pack(side="left")
        self._button(controls, "Ayarları kaydet", self._save, primary=False).pack(side="right")
        self._button(controls, "SSH bağlantısını test et", self._connect, primary=False).pack(side="right", padx=8)

        run_panel = tk.Frame(area, bg=PANEL, highlightbackground=LINE, highlightthickness=1); run_panel.pack(fill="x", pady=(0, 13))
        head = tk.Frame(run_panel, bg=PANEL); head.pack(fill="x", padx=17, pady=(14, 9))
        tk.Label(head, text="ÇALIŞTIRMA", bg=PANEL, fg=GREEN, font=("Consolas", 8)).pack(anchor="w")
        tk.Label(head, text="Sunucuyu başlat", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(4, 0))
        status_box = tk.Frame(run_panel, bg=ENTRY, highlightbackground="#303832", highlightthickness=1)
        status_box.pack(fill="x", padx=17)
        status_top = tk.Frame(status_box, bg=ENTRY); status_top.pack(fill="x", padx=12, pady=(9, 2))
        self.status_dot = tk.Label(status_top, text="●", bg=ENTRY, fg="#6e7971", font=("Segoe UI", 10))
        self.status_dot.pack(side="left", padx=(0, 7))
        self.proc_label = tk.Label(status_top, text="Kontrol bekleniyor", bg=ENTRY, fg=MUTED, anchor="w", font=("Segoe UI", 9, "bold"))
        self.proc_label.pack(side="left")
        self.check_label = tk.Label(status_top, text="Henüz kontrol edilmedi", bg=ENTRY, fg="#6f7a72", font=("Segoe UI", 8))
        self.check_label.pack(side="right")
        self.proc_detail = tk.Label(status_box, text="SSH bağlantısı kurulduğunda uzak dosyanın durumu burada görünür.", bg=ENTRY, fg="#7d8981", anchor="w", padx=25, pady=4, font=("Segoe UI", 8))
        self.proc_detail.pack(fill="x")
        actions = tk.Frame(run_panel, bg=PANEL); actions.pack(fill="x", padx=17, pady=10)
        self.start_btn = self._button(actions, "▶   Başlat", self._start, primary=True); self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.stop_btn = self._button(actions, "■   Durdur", self._stop, primary=False); self.stop_btn.pack(side="left", fill="x", expand=True, padx=(5, 0)); self.stop_btn.configure(state="disabled")

        log_panel = tk.Frame(area, bg=PANEL, highlightbackground=LINE, highlightthickness=1); log_panel.pack(fill="both", expand=True)
        loghead = tk.Frame(log_panel, bg=PANEL); loghead.pack(fill="x", padx=14, pady=10)
        tk.Label(loghead, text="›_  Canlı günlükler", bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
        self._button(loghead, "Temizle", self._clear_logs, primary=False).pack(side="right")
        self.logbox = tk.Text(log_panel, bg="#0e1110", fg="#b3c0b5", insertbackground=GREEN, relief="flat", font=("Consolas", 9), height=7, wrap="word", padx=12, pady=10, state="disabled")
        self.logbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._log("SSH bağlantısı hazır olduğunda sunucu çıktıları burada görünür.")
        if self._custom_window:
            self._add_resize_handles()

    def _title_dot(self, parent, color, command):
        dot = tk.Label(parent, text="●", bg="#101513", fg=color, font=("Segoe UI", 10), cursor="hand2")
        dot.bind("<Button-1>", lambda _event: (command(), "break")[1])
        return dot

    def _panel(self, parent, eyebrow, title, subtitle):
        panel = tk.Frame(parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        head = tk.Frame(panel, bg=PANEL); head.pack(fill="x", padx=17, pady=(13, 9))
        self._label(head, eyebrow, 8, GREEN).pack(anchor="w")
        tk.Label(head, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(4, 1))
        tk.Label(head, text=subtitle, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w")
        self._last_panel = panel
        return panel

    @staticmethod
    def _label(parent, text, size, color):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, font=("Consolas", size))

    def _entry(self, parent, title, key, placeholder, row, col, colspan=1, below=None):
        cell = tk.Frame(parent, bg=PANEL); cell.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(0 if col == 0 else 7, 7 if col == 0 else 0), pady=(0, 10))
        self._label(cell, title, 8, MUTED).pack(anchor="w", pady=(0, 6))
        entry = tk.Entry(cell, textvariable=self.vars[key], bg=ENTRY, fg=TEXT, insertbackground=GREEN, relief="flat", highlightthickness=1, highlightbackground=LINE, highlightcolor="#71875a", font=("Segoe UI", 9))
        entry.pack(fill="x", ipady=8, ipadx=8)
        entry.field_key = key
        entry._placeholder_active = False
        self.entry_widgets[key] = entry
        self.placeholders[key] = placeholder
        entry.bind("<FocusIn>", self._clear_placeholder)
        entry.bind("<FocusOut>", self._restore_placeholder)
        if below:
            tk.Label(cell, text=below, bg=PANEL, fg="#68736b", font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))
        parent.grid_columnconfigure(col, weight=1)

    def _button(self, parent, text, command, primary):
        bg, fg = (GREEN, "#15200f") if primary else ("#202522", "#c4cbc5")
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground="#c9f995" if primary else "#303832", activeforeground=fg, relief="flat", bd=0, padx=12, pady=8, font=("Segoe UI", 9, "bold"), cursor="hand2", highlightthickness=1, highlightbackground=GREEN if primary else "#363d38")

    def _load_fields(self):
        for key, var in self.vars.items():
            var.set(str(self.cfg.get(key, "")))
            if not var.get():
                self._show_placeholder(self.entry_widgets[key])
        self.os_var.set("Windows" if self.cfg.get("target_os") == "windows" else "Linux")
        self._os_changed()

    def _collect(self):
        cfg = {k: ("" if self.entry_widgets[k]._placeholder_active else v.get().strip()) for k, v in self.vars.items()}
        try:
            cfg["port"] = int(cfg["port"] or 22)
        except ValueError:
            raise ValueError("Port sayısal olmalı.")
        if not 1 <= cfg["port"] <= 65535:
            raise ValueError("Port 1 ile 65535 arasında olmalı.")
        cfg["target_os"] = "windows" if self.os_var.get() == "Windows" else "linux"
        cfg["geometry"] = self.geometry()
        return cfg

    def _save(self, quiet=False):
        try:
            self.cfg = self._collect(); save_config(self.cfg)
            if not quiet: self._notify("Ayarlar bu bilgisayara kaydedildi.")
            return True
        except (ValueError, OSError) as exc:
            self._notify(str(exc), error=True); return False

    def _notify(self, text, error=False):
        self.title(("Hata: " if error else "SSH Starter — ") + text[:100])
        if hasattr(self, "title_status"):
            self.title_status.configure(text="●  " + text[:45], fg="#f29a89" if error else GREEN)
        self.after(3500, lambda: self.title("SSH Starter"))
        if error: self._log("HATA: " + text)

    def _log(self, text):
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text.rstrip() + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def _post_ui(self, callback, *args):
        if not self.closing:
            self.ui_events.put((callback, args))

    def _process_ui_events(self):
        if self.closing:
            return
        while True:
            try:
                callback, args = self.ui_events.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args)
            except tk.TclError:
                if not self.closing:
                    raise
        self.after(100, self._process_ui_events)

    def _async(self, fn, success=None):
        if self.busy: return
        self.busy = True
        def work():
            try:
                result = fn()
                if success:
                    self._post_ui(success, result)
            except Exception as exc:
                self._post_ui(self._notify, str(exc), True)
            finally:
                self._post_ui(setattr, self, "busy", False)
        threading.Thread(target=work, daemon=True).start()

    def _connect(self):
        if not self._save(quiet=True): return
        self._notify("SSH sunucusuna bağlanıyor…")
        self._async(lambda: run_ssh(self.cfg, "echo SSH_OK", timeout=14), lambda _: (self._notify("SSH bağlantısı hazır."), self._log("SSH bağlantısı başarıyla kuruldu.")))

    def _start(self):
        if not self._save(quiet=True): return
        if not self.cfg["host"] or not self.cfg["program"]:
            self._notify("Host ve çalıştırılacak dosyanın yolunu gir.", error=True); return
        self._notify("Uzak program başlatılıyor…")
        def done(pid):
            self._notify("Program uzak sunucuda başlatıldı."); self._log("Program başlatıldı. PID " + pid); self._poll()
        self._async(lambda: run_ssh(self.cfg, start_command(self.cfg)), done)

    def _stop(self):
        if not self.cfg["host"]: return
        remote = (powershell_remote("$pidFile=Join-Path $env:TEMP 'ssh-starter.pid'; $id=Get-Content $pidFile -ErrorAction SilentlyContinue; if ($id) { & taskkill.exe /PID $id /T /F | Out-Null; Remove-Item $pidFile -Force -ErrorAction SilentlyContinue }") if self.cfg["target_os"] == "windows" else "if test -f /tmp/ssh-starter.pid; then kill \"$(cat /tmp/ssh-starter.pid)\" 2>/dev/null || true; rm -f /tmp/ssh-starter.pid; fi")
        self._async(lambda: run_ssh(self.cfg, remote), lambda _: (self._set_running(False), self._log("Durdurma sinyali gönderildi.")))

    def _poll(self):
        if self.poll_after_id is not None:
            try: self.after_cancel(self.poll_after_id)
            except tk.TclError: pass
            self.poll_after_id = None
        if self.winfo_exists() and self.cfg["host"] and not self.busy and not self.polling:
            self.polling = True
            def work():
                try:
                    output = run_ssh(self.cfg, snapshot_remote(self.cfg), timeout=16)
                    status_line, _separator, logs = output.partition("\n")
                    prefix = "__SSH_STARTER_STATUS__:"
                    if not status_line.startswith(prefix):
                        raise RuntimeError("Uzak sunucudan süreç durumu alınamadı.")
                    status = status_line[len(prefix):]
                    self._post_ui(self._poll_result, status, logs)
                except Exception as exc:
                    self._post_ui(self._set_offline, str(exc))
                finally:
                    self._post_ui(setattr, self, "polling", False)
            threading.Thread(target=work, daemon=True).start()
        self.poll_after_id = self.after(5000, self._poll)

    def _poll_result(self, status, logs):
        running = status.startswith("running:")
        pid = status.partition(":")[2]
        self._set_running(running, pid)
        if logs != self.last_remote_logs:
            if logs.startswith(self.last_remote_logs):
                new_output = logs[len(self.last_remote_logs):]
            else:
                new_output = logs
            if new_output.strip():
                self._log(new_output)
            self.last_remote_logs = logs
        self.connection_state.configure(text="●  SSH BAĞLI", fg=GREEN)
        self.check_label.configure(text="Son kontrol: " + datetime.now().strftime("%H:%M:%S"))

    def _set_running(self, running, pid=""):
        self.running = running
        if self.last_process_state is not None and self.last_process_state != running:
            self._log("Uzak program durumu değişti: " + ("AÇIK" if running else "KAPALI"))
        self.last_process_state = running
        if running:
            self.status_dot.configure(fg=GREEN)
            self.proc_label.configure(text="Dosya açık · Program çalışıyor", fg=GREEN)
            self.proc_detail.configure(text=f"Uzak sunucuda çalışan işlem  ·  PID {pid}", fg="#a3b29d")
            self.start_btn.configure(state="disabled"); self.stop_btn.configure(state="normal")
        else:
            self.status_dot.configure(fg="#758078")
            self.proc_label.configure(text="Dosya kapalı · Program çalışmıyor", fg=MUTED)
            self.proc_detail.configure(text="Başlat düğmesine bastığında uygulama durumu otomatik izlenir.", fg="#7d8981")
            self.start_btn.configure(state="normal"); self.stop_btn.configure(state="disabled")

    def _set_offline(self, message):
        self.connection_state.configure(text="●  SSH BAĞLANTISI YOK", fg="#e7a17f")
        self.check_label.configure(text="Son kontrol başarısız")
        self.proc_label.configure(text="Durum kontrol edilemiyor", fg="#e7a17f")
        self.proc_detail.configure(text="SSH bağlantısını kontrol et; son durum doğrulanamadı.", fg="#b68a73")

    def _clear_logs(self):
        self.logbox.configure(state="normal"); self.logbox.delete("1.0", "end"); self.logbox.configure(state="disabled")
        self.last_remote_logs = ""

    def _os_changed(self, _event=None):
        if self.os_var.get() == "Windows":
            self._set_placeholder("program", r"C:\Users\deploy\server.exe")
            self._set_placeholder("workdir", r"C:\Users\deploy\app")
        else:
            self._set_placeholder("program", "/home/deploy/app/server")
            self._set_placeholder("workdir", "/home/deploy/app")

    def _set_placeholder(self, key, value):
        self.placeholders[key] = value
        entry = self.entry_widgets[key]
        if not self.vars[key].get() or entry._placeholder_active:
            self._show_placeholder(entry)

    def _show_placeholder(self, entry):
        key = entry.field_key
        if not self.vars[key].get() or entry._placeholder_active:
            self.vars[key].set(self.placeholders[key])
            entry._placeholder_active = True
            entry.configure(fg="#59635e")

    def _clear_placeholder(self, event):
        entry = event.widget
        if entry._placeholder_active:
            self.vars[entry.field_key].set("")
            entry._placeholder_active = False
            entry.configure(fg=TEXT)

    def _restore_placeholder(self, event):
        self._show_placeholder(event.widget)

    def _geometry_changed(self, _event=None):
        if self.geometry_after_id:
            try: self.after_cancel(self.geometry_after_id)
            except tk.TclError: pass
        self.geometry_after_id = self.after(800, self._persist_geometry)

    def _persist_geometry(self):
        try:
            if not self._maximized and self.state() == "normal":
                self.cfg["geometry"] = self.geometry(); save_config(self.cfg)
        except OSError:
            pass

    def _autostart_enabled(self):
        if sys.platform != "win32": return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "SSHStarter")
                return True
        except (OSError, ImportError):
            return False

    def _toggle_autostart(self):
        if sys.platform != "win32":
            messagebox.showinfo("Otomatik başlatma", "Otomatik başlatma şu anda Windows için kullanılabilir.")
            self.autostart.set(False); return
        try:
            import winreg
            keypath = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, keypath, 0, winreg.KEY_SET_VALUE) as key:
                if self.autostart.get():
                    if getattr(sys, "frozen", False):
                        command = subprocess.list2cmdline([sys.executable, "--startup"])
                    else:
                        python = Path(sys.executable)
                        pythonw = python.with_name("pythonw.exe")
                        executable = pythonw if pythonw.exists() else python
                        command = subprocess.list2cmdline([str(executable), str(Path(__file__).resolve()), "--startup"])
                    winreg.SetValueEx(key, "SSHStarter", 0, winreg.REG_SZ, command)
                    self._notify("Bilgisayar açılışında başlatma etkin.")
                else:
                    try: winreg.DeleteValue(key, "SSHStarter")
                    except FileNotFoundError: pass
                    self._notify("Otomatik başlatma kapatıldı.")
        except OSError as exc:
            self.autostart.set(not self.autostart.get()); self._notify("Başlangıç ayarı kaydedilemedi: " + str(exc), error=True)

    def on_close(self):
        self._persist_geometry()
        self.destroy()


if __name__ == "__main__":
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SSHStarter().mainloop()
