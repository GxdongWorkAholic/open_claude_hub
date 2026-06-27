import os
import json
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import time
import ctypes
import threading

# -- Fix DPI blurriness on Windows --
if os.name == "nt":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

# -- Color scheme --------------------------------------------------
COLORS = {
    "bg":            "#f2f3f7",
    "card":          "#ffffff",
    "card_hover":    "#f8f9fc",
    "card_selected": "#f4f2ff",
    "primary":       "#5b4af5",
    "primary_light": "#eeebff",
    "primary_hover": "#4a3ad4",
    "success":       "#16a34a",
    "danger":        "#dc2626",
    "warning":       "#ea580c",
    "text":          "#1e293b",
    "text_soft":     "#64748b",
    "text_muted":    "#94a3b8",
    "border":        "#e5e7eb",
    "accent_strip":  "#5b4af5",
    "accent_off":    "#d1d5db",
    "headroom_on":   "#22c55e",
    "headroom_off":  "#94a3b8",
}

FONTS = {
    "title":      ("Microsoft YaHei UI", 16, "bold"),
    "heading":    ("Microsoft YaHei UI", 11, "bold"),
    "body":       ("Microsoft YaHei UI", 10),
    "body_bold":  ("Microsoft YaHei UI", 10, "bold"),
    "small":      ("Microsoft YaHei UI", 9),
    "btn":        ("Microsoft YaHei UI", 10),
    "btn_big":    ("Microsoft YaHei UI", 11, "bold"),
    "stat_value": ("Microsoft YaHei UI", 20, "bold"),
    "stat_label": ("Microsoft YaHei UI", 9),
}

STATS_REFRESH_MS = 5000  # Poll /stats every 5 seconds


class ClaudeLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Open Claude Hub")
        self.root.geometry("640x910")
        self.root.resizable(True, True)
        self.root.minsize(500, 400)
        self.root.configure(bg=COLORS["bg"])

        # -- Load config --
        self.config = self.load_config()
        if self.config is None:
            root.destroy()
            return

        self.headroom_port = self.config["headroom"]["port"]
        self.headroom_host = self.config["headroom"].get("host", "127.0.0.1")
        self.headroom_url = f"http://{self.headroom_host}:{self.headroom_port}"
        self.upstream = self.config["headroom"]["upstream"]
        self.projects = self.config["projects"]

        # -- State --
        self.selected: dict[str, tk.BooleanVar] = {}
        self.spawned_processes: list[subprocess.Popen] = []
        self.headroom_running = False
        self._card_widgets: dict[str, dict] = {}
        self._stats_job = None

        # -- Close window -> cleanup children --
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # -- Style ttk for tabs --
        self._setup_ttk_style()

        # -- Build UI --
        self._build_ui()

        # -- Auto start headroom --
        self.root.after(300, self._auto_start_headroom)

    # ================================================================
    #  Config loading
    # ================================================================

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "claude_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Config not found:\n{config_path}")
            return None
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON:\n{e}")
            return None

    # ================================================================
    #  ttk style (for Notebook tabs)
    # ================================================================

    def _setup_ttk_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=COLORS["bg"],
            foreground=COLORS["text_muted"],
            font=FONTS["btn"],
            padding=[18, 8],
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["bg"]), ("active", COLORS["bg"])],
            foreground=[("selected", COLORS["text"]), ("active", COLORS["text_soft"])],
            font=[("selected", FONTS["body_bold"])],
        )
    # ================================================================
    #  UI building
    # ================================================================

    def _build_ui(self):
        # -- Top header --
        header = tk.Frame(self.root, bg=COLORS["primary"])
        header.pack(fill="x")

        header_inner = tk.Frame(header, bg=COLORS["primary"])
        header_inner.pack(fill="x", padx=24, pady=(16, 10))

        tk.Label(
            header_inner, text="Open Claude Hub",
            font=FONTS["title"], bg=COLORS["primary"], fg="#ffffff",
        ).pack(side="left")

        self._build_status_pill(header_inner)

        # -- Notebook (tab control) --
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=0, pady=0)

        # -- Tab 1: Projects --
        self._build_projects_tab()

        # -- Tab 2: Headroom Stats --
        self._build_headroom_tab()

        # -- Bottom bar --
        footer = tk.Frame(self.root, bg=COLORS["bg"])
        footer.pack(fill="x", padx=24, pady=(4, 12))

        sep = tk.Frame(footer, bg=COLORS["border"], height=1)
        sep.pack(fill="x", pady=(0, 12))

        btn_row = tk.Frame(footer, bg=COLORS["bg"])
        btn_row.pack(fill="x")

        self.footer_actions = tk.Frame(btn_row, bg=COLORS["bg"])
        self.footer_actions.pack(side="left")

        self.all_selected = False
        self.toggle_sel_btn = self._make_btn(self.footer_actions, "Select All", self._toggle_select, "text")
        self.toggle_sel_btn.pack(side="left", padx=(0, 12))
        self.launch_btn = self._make_btn(self.footer_actions, "Launch Selected", self.launch, "primary")
        self.launch_btn.pack(side="left")

        # Hide footer actions on non-Project tabs
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    # ================================================================
    #  Tab 1: Projects
    # ================================================================

    def _build_projects_tab(self):
        tab = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(tab, text="Projects")

        # Scrollable canvas
        canvas_frame = tk.Frame(tab, bg=COLORS["bg"])
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=(12, 0))

        self.project_canvas = tk.Canvas(
            canvas_frame, bg=COLORS["bg"], highlightthickness=0, bd=0,
        )
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.project_canvas.yview,
        )
        self.project_container = tk.Frame(self.project_canvas, bg=COLORS["bg"])

        self.project_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.project_canvas.pack(side="left", fill="both", expand=True)

        self._canvas_window = self.project_canvas.create_window(
            (0, 0), window=self.project_container, anchor="nw",
        )
        self.project_container.bind("<Configure>", self._on_frame_resize)
        self.project_canvas.bind("<Configure>", self._on_canvas_resize)
        self.project_canvas.bind("<Enter>", lambda _: self._bind_scroll())
        self.project_canvas.bind("<Leave>", lambda _: self._unbind_scroll())

        # Draw cards
        self._build_project_cards()

    def _on_tab_change(self, event=None):
        """Hide footer action buttons when not on the Projects tab."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:  # Projects tab
            self.footer_actions.pack(side="left")
        else:  # Headroom tab
            self.footer_actions.pack_forget()

    # ================================================================
    #  Tab 2: Headroom Stats
    # ================================================================

    def _build_headroom_tab(self):
        self.stats_tab = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.stats_tab, text="Headroom")

        # Scrollable container
        canvas_frame = tk.Frame(self.stats_tab, bg=COLORS["bg"])
        canvas_frame.pack(fill="both", expand=True)

        self.stats_canvas = tk.Canvas(
            canvas_frame, bg=COLORS["bg"], highlightthickness=0, bd=0,
        )
        stats_scroll = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.stats_canvas.yview,
        )
        self.stats_inner = tk.Frame(self.stats_canvas, bg=COLORS["bg"])

        self.stats_canvas.configure(yscrollcommand=stats_scroll.set)
        stats_scroll.pack(side="right", fill="y")
        self.stats_canvas.pack(side="left", fill="both", expand=True)

        self._stats_canvas_win = self.stats_canvas.create_window(
            (0, 0), window=self.stats_inner, anchor="nw",
        )
        self.stats_inner.bind("<Configure>", lambda e: self.stats_canvas.configure(
            scrollregion=self.stats_canvas.bbox("all")))
        self.stats_canvas.bind("<Configure>", lambda e: self.stats_canvas.itemconfig(
            self._stats_canvas_win, width=e.width))

        # -- Stat cards placeholder --
        # Top summary cards
        self.stats_summary_frame = tk.Frame(self.stats_inner, bg=COLORS["bg"])
        self.stats_summary_frame.pack(fill="x", padx=24, pady=(18, 0))

        self.stat_cards = {}
        for key, label in [
            ("tokens_saved", "Tokens Saved"),
            ("requests", "API Requests"),
            ("savings_pct", "Savings %"),
        ]:
            card = self._create_stat_card(self.stats_summary_frame, label)
            card.pack(side="left", padx=(0, 12), fill="both", expand=True)
            self.stat_cards[key] = card
            # Store value label reference
            card._val = card.winfo_children()[0]  # first child is the value

        # Per-project section
        self.stats_project_label = tk.Label(
            self.stats_inner, text="Per Project",
            font=FONTS["heading"], bg=COLORS["bg"], fg=COLORS["text"],
            anchor="w",
        )
        self.stats_project_label.pack(fill="x", padx=24, pady=(20, 8))

        self.stats_project_container = tk.Frame(self.stats_inner, bg=COLORS["bg"])
        self.stats_project_container.pack(fill="x", padx=24)

        # RTK section
        self.stats_rtk_label = tk.Label(
            self.stats_inner, text="RTK",
            font=FONTS["heading"], bg=COLORS["bg"], fg=COLORS["text"],
            anchor="w",
        )
        self.stats_rtk_label.pack(fill="x", padx=24, pady=(20, 8))

        self.stats_rtk_frame = tk.Frame(self.stats_inner, bg=COLORS["bg"])
        self.stats_rtk_frame.pack(fill="x", padx=24)

        self.rtk_cards = {}
        for key, label in [
            ("commands", "Commands"),
            ("tokens_saved", "Tokens Saved"),
            ("savings_pct", "Avg Savings"),
        ]:
            card = self._create_stat_card(self.stats_rtk_frame, label)
            card.pack(side="left", padx=(0, 12), fill="both", expand=True)
            self.rtk_cards[key] = card

        # Cost section
        self.stats_cost_label = tk.Label(
            self.stats_inner, text="Cost",
            font=FONTS["heading"], bg=COLORS["bg"], fg=COLORS["text"],
            anchor="w",
        )
        self.stats_cost_label.pack(fill="x", padx=24, pady=(20, 8))

        self.stats_cost_frame = tk.Frame(self.stats_inner, bg=COLORS["bg"])
        self.stats_cost_frame.pack(fill="x", padx=24, pady=(0, 20))

        self.cost_cards = {}
        for key, label in [
            ("savings_usd", "Saved (USD)"),
            ("input_cost", "Input Cost"),
            ("with_headroom", "With Headroom"),
        ]:
            card = self._create_stat_card(self.stats_cost_frame, label)
            card.pack(side="left", padx=(0, 12), fill="both", expand=True)
            self.cost_cards[key] = card

        # Start periodic stats refresh
        self._refresh_stats()

    def _create_stat_card(self, parent, label_text):
        """Create a small stats card with value + label."""
        card = tk.Frame(
            parent,
            bg=COLORS["card"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
        )
        val = tk.Label(
            card, text="--",
            font=FONTS["stat_value"], bg=COLORS["card"], fg=COLORS["primary"],
            anchor="w",
        )
        val.pack(fill="x", padx=14, pady=(14, 0))
        lbl = tk.Label(
            card, text=label_text,
            font=FONTS["stat_label"], bg=COLORS["card"], fg=COLORS["text_muted"],
            anchor="w",
        )
        lbl.pack(fill="x", padx=14, pady=(0, 10))
        card._val = val
        card._lbl = lbl
        return card

    def _set_stat_value(self, frame, value):
        """Set the value text of a stat card."""
        if hasattr(frame, "_val"):
            frame._val.configure(text=str(value))

    # ================================================================
    #  Stats fetching & refresh
    # ================================================================

    def _refresh_stats(self):
        """Fetch /stats in background and update the Headroom tab."""
        def _fetch():
            try:
                req = urllib.request.urlopen(f"{self.headroom_url}/stats", timeout=4)
                data = json.loads(req.read().decode("utf-8"))
            except Exception:
                data = None
            self.root.after(0, lambda: self._apply_stats(data))
            # Drive the header pill via the same probe
            self.root.after(0, lambda: self._set_headroom_status(data is not None))
            # Schedule next refresh
            self._stats_job = self.root.after(STATS_REFRESH_MS, self._refresh_stats)

        t = threading.Thread(target=_fetch, daemon=True)
        t.start()

    def _apply_stats(self, data):
        if data is None:
            self._set_stat_value(self.stat_cards["tokens_saved"], "N/A")
            self._set_stat_value(self.stat_cards["requests"], "N/A")
            self._set_stat_value(self.stat_cards["savings_pct"], "N/A")
            for key in self.rtk_cards:
                self._set_stat_value(self.rtk_cards[key], "N/A")
            for key in self.cost_cards:
                self._set_stat_value(self.cost_cards[key], "N/A")
            return

        # -- Top summary --
        summary = data.get("summary", {})
        tokens_saved = data.get("tokens", {}).get("saved", 0)
        api_requests = summary.get("api_requests", 0)
        savings = data.get("savings", {})

        self._set_stat_value(self.stat_cards["tokens_saved"], self._fmt_num(tokens_saved))
        self._set_stat_value(self.stat_cards["requests"], str(api_requests))
        self._set_stat_value(self.stat_cards["savings_pct"], self._fmt_pct(
            data.get("tokens", {}).get("savings_percent", 0)))

        # -- Per-project --
        for w in self.stats_project_container.winfo_children():
            w.destroy()

        per_project = savings.get("per_project", {})
        if per_project:
            for proj_name, pd in per_project.items():
                row = tk.Frame(self.stats_project_container, bg=COLORS["bg"])
                row.pack(fill="x", pady=(0, 6))

                card = tk.Frame(
                    row, bg=COLORS["card"],
                    highlightbackground=COLORS["border"], highlightthickness=1,
                )
                card.pack(fill="x", ipadx=14, ipady=8)

                tk.Label(
                    card, text=proj_name,
                    font=FONTS["body_bold"], bg=COLORS["card"], fg=COLORS["text"],
                ).pack(side="left", padx=(14, 0))

                detail = f"{pd.get('requests', 0)} requests  |  {self._fmt_num(pd.get('tokens_saved', 0))} tokens saved  |  {self._fmt_pct(pd.get('savings_percent', 0))}"
                tk.Label(
                    card, text=detail,
                    font=FONTS["small"], bg=COLORS["card"], fg=COLORS["text_soft"],
                ).pack(side="right", padx=(0, 14))
        else:
            tk.Label(
                self.stats_project_container, text="No project data yet",
                font=FONTS["small"], bg=COLORS["bg"], fg=COLORS["text_muted"],
            ).pack()

        # -- RTK --
        cli = data.get("cli_filtering", {}) or data.get("context_tool", {}).get("stats", {})
        self._set_stat_value(self.rtk_cards["commands"], str(cli.get("lifetime", {}).get("commands", 0)))
        self._set_stat_value(self.rtk_cards["tokens_saved"], self._fmt_num(
            cli.get("lifetime", {}).get("tokens_saved", 0)))
        self._set_stat_value(self.rtk_cards["savings_pct"], self._fmt_pct(
            cli.get("lifetime", {}).get("savings_pct", 0)))

        # -- Cost --
        cost = data.get("cost", {})
        saved = cost.get("savings_usd", 0)
        input_cost = cost.get("total_input_cost_usd", 0)
        with_hr = cost.get("cost_with_headroom_usd", 0)
        self._set_stat_value(self.cost_cards["savings_usd"], f"${saved:.4f}")
        self._set_stat_value(self.cost_cards["input_cost"], f"${input_cost:.4f}")
        self._set_stat_value(self.cost_cards["with_headroom"], f"${with_hr:.4f}")

    @staticmethod
    def _fmt_num(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(int(n))

    @staticmethod
    def _fmt_pct(pct):
        return f"{pct:.1f}%"

    # ================================================================
    #  Header status pill
    # ================================================================

    def _build_status_pill(self, parent):
        pill = tk.Frame(parent, bg=COLORS["primary"])
        pill.pack(side="right")

        self.headroom_dot = tk.Canvas(
            pill, width=8, height=8,
            bg=COLORS["primary"], highlightthickness=0,
        )
        self.headroom_dot.pack(side="left", padx=(10, 4))
        self._dot_id = self.headroom_dot.create_oval(
            1, 1, 7, 7, fill=COLORS["headroom_off"], outline=""
        )

        self.headroom_label = tk.Label(
            pill, text="Proxy off",
            font=FONTS["small"], bg=COLORS["primary"], fg="#c7d2fe",
        )
        self.headroom_label.pack(side="left", padx=(0, 10))

    # ================================================================
    #  Canvas scrolling
    # ================================================================

    def _on_frame_resize(self, event):
        self.project_canvas.configure(scrollregion=self.project_canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self.project_canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_scroll(self):
        self.project_canvas.bind_all("<MouseWheel>", self._on_scroll)
        self.stats_canvas.bind_all("<MouseWheel>", self._on_scroll)

    def _unbind_scroll(self):
        self.project_canvas.unbind_all("<MouseWheel>")
        self.stats_canvas.unbind_all("<MouseWheel>")

    def _on_scroll(self, event):
        """Pixel-precise scroll via yview_moveto — never overshoots scrollregion."""
        w = event.widget
        canvas = w if isinstance(w, tk.Canvas) else self.project_canvas

        # Refresh scrollregion before computing
        canvas.configure(scrollregion=canvas.bbox("all"))
        sr = canvas.bbox("all")
        if not sr:
            return
        content_h = sr[3]             # total content height (pixels)
        viewport_h = canvas.winfo_height()
        if content_h <= viewport_h:
            return                     # all visible, nothing to scroll

        scroll_range = content_h - viewport_h
        step_px = 40                   # pixels per mouse-wheel notch
        # Windows: event.delta positive = up
        delta_px = int(event.delta / 120) * step_px

        cur_px = canvas.yview()[0] * content_h
        new_px = max(0.0, min(scroll_range, cur_px - delta_px))
        canvas.yview_moveto(new_px / content_h)

    # ================================================================
    #  Buttons
    # ================================================================

    def _make_btn(self, parent, text, command, kind="primary"):
        if kind == "primary":
            bg = COLORS["primary"]
            fg = "#ffffff"
            hover_bg = COLORS["primary_hover"]
            active_bg = COLORS["primary_hover"]
            font = FONTS["btn_big"]
            padx, pady = 24, 8
        elif kind == "danger":
            bg = COLORS["bg"]
            fg = COLORS["danger"]
            hover_bg = "#fef2f2"
            active_bg = "#fee2e2"
            font = FONTS["btn"]
            padx, pady = 16, 6
        else:
            bg = COLORS["bg"]
            fg = COLORS["text_soft"]
            hover_bg = "#f1f5f9"
            active_bg = "#e2e8f0"
            font = FONTS["btn"]
            padx, pady = 14, 6

        btn = tk.Label(
            parent, text=text, font=font,
            bg=bg, fg=fg,
            padx=padx, pady=pady,
            cursor="hand2", bd=0,
        )
        if kind == "primary":
            btn.configure(highlightbackground=COLORS["primary"], highlightthickness=1)

        btn.bind("<Enter>",            lambda e, hb=hover_bg: e.widget.configure(bg=hb))
        btn.bind("<Leave>",            lambda e, ob=bg:       e.widget.configure(bg=ob))
        btn.bind("<Button-1>",         lambda e, c=command, hb=hover_bg: (e.widget.configure(bg=hb), c()))
        return btn

    # ================================================================
    #  Project cards
    # ================================================================

    def _build_project_cards(self):
        for w in self.project_container.winfo_children():
            w.destroy()
        self._card_widgets.clear()

        exist_count = 0
        missing_count = 0

        for p in self.projects:
            path_ok = os.path.isdir(p["path"])
            var = tk.BooleanVar(value=path_ok)
            self.selected[p["name"]] = var
            self._create_card(p, path_ok, var)

        pass  # cards built

    def _recursive_bind(self, widget, seq, callback):
        widget.bind(seq, callback, add="+")
        for child in widget.winfo_children():
            self._recursive_bind(child, seq, callback)

    def _create_card(self, project, path_ok, var):
        name, path = project["name"], project["path"]

        wrapper = tk.Frame(self.project_container, bg=COLORS["bg"])
        wrapper.pack(fill="x", pady=(0, 8))

        card = tk.Frame(wrapper, bg=COLORS["card"], highlightthickness=0, bd=0)
        card.pack(fill="x", ipady=1)

        accent = tk.Frame(card, bg=COLORS["accent_off"], width=4)
        accent.pack(side="left", fill="y")

        body = tk.Frame(card, bg=COLORS["card"])
        body.pack(side="left", fill="both", expand=True, padx=(14, 12), pady=12)

        tk.Label(
            body, text=name,
            font=FONTS["body_bold"], bg=COLORS["card"], fg=COLORS["text"],
            anchor="w",
        ).pack(fill="x")

        path_row = tk.Frame(body, bg=COLORS["card"])
        path_row.pack(fill="x", pady=(2, 0))

        tk.Label(
            path_row, text=path,
            font=FONTS["small"], bg=COLORS["card"],
            fg=COLORS["text_muted"] if path_ok else COLORS["danger"],
            anchor="w",
        ).pack(side="left")

        right = tk.Frame(card, bg=COLORS["card"])
        right.pack(side="right", padx=(0, 14), pady=12)

        dot_size = 20
        dot_canvas = tk.Canvas(
            right, width=dot_size, height=dot_size,
            bg=COLORS["card"], highlightthickness=0,
        )
        dot_canvas.pack()
        dot_canvas.create_oval(3, 3, dot_size - 3, dot_size - 3,
                               fill="", outline=COLORS["text_muted"], width=2)
        dot_inner = dot_canvas.create_oval(5, 5, dot_size - 5, dot_size - 5,
                                           fill=COLORS["primary"], outline="")

        # ---- Visual helpers for this card ----
        widgets_to_update = [card, body, path_row, right, dot_canvas]
        label_children = [c for c in body.winfo_children() if isinstance(c, tk.Label)]
        label_children += [c for c in path_row.winfo_children() if isinstance(c, tk.Label)]
        # (pre-warm: can't winfo_children until packed, so do it lazily in the helpers)

        def _update_bg(frame_widgets, bg_color):
            for w in frame_widgets:
                try:
                    w.configure(bg=bg_color)
                except Exception:
                    pass
            # also all Labels inside body and path_row
            for c in body.winfo_children():
                try:
                    c.configure(bg=bg_color)
                except Exception:
                    pass
            for c in path_row.winfo_children():
                try:
                    c.configure(bg=bg_color)
                except Exception:
                    pass

        def _apply_selected():
            accent.configure(bg=COLORS["accent_strip"])
            _update_bg(widgets_to_update, COLORS["card_selected"])
            dot_canvas.itemconfig(dot_inner, state="normal")

        def _apply_unselected():
            accent.configure(bg=COLORS["accent_off"])
            _update_bg(widgets_to_update, COLORS["card"])
            dot_canvas.itemconfig(dot_inner, state="hidden")

        def _apply_hover(event=None):
            bg = "#eeebff" if var.get() else COLORS["card_hover"]
            _update_bg(widgets_to_update, bg)
            card.configure(cursor="hand2")

        def _apply_normal(event=None):
            _apply_selected() if var.get() else _apply_unselected()

        def toggle(event=None):
            var.set(not var.get())

        self._recursive_bind(card, "<Button-1>", toggle)
        card.bind("<Enter>", _apply_hover, add="+")
        card.bind("<Leave>", _apply_normal, add="+")

        var.trace_add("write", lambda *_: _apply_selected() if var.get() else _apply_unselected())

        (_apply_selected() if var.get() else _apply_unselected())

        self._card_widgets[name] = {
            "card": card, "accent": accent, "dot_canvas": dot_canvas,
            "dot_inner": dot_inner,
        }

    # ================================================================
    #  Headroom proxy
    # ================================================================

    def _auto_start_headroom(self):
        def _run():
            self._update_status("Checking proxy...")
            if self.check_headroom():
                self._set_headroom_status(True)
                self._update_status("Proxy connected")
                return
            self._update_status("Starting proxy...")
            if self.start_headroom():
                self._set_headroom_status(True)
                self._update_status("Proxy started")
            else:
                self._set_headroom_status(False)
                self._update_status("Proxy failed to start")

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _update_status(self, msg: str):
        self.root.after(0, lambda: None)

    def check_headroom(self) -> bool:
        try:
            urllib.request.urlopen(f"{self.headroom_url}/health", timeout=3)
            return True
        except Exception:
            return False

    def start_headroom(self) -> bool:
        try:
            proc = subprocess.Popen(
                ["headroom", "proxy", "--port", str(self.headroom_port),
                 "--anthropic-api-url", self.upstream],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.spawned_processes.append(proc)
            for _ in range(8):
                time.sleep(1)
                if self.check_headroom():
                    return True
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Headroom:\n{e}")
            return False

    def _set_headroom_status(self, running: bool):
        def _apply():
            self.headroom_running = running
            if running:
                self.headroom_dot.itemconfig(self._dot_id, fill=COLORS["headroom_on"])
                self.headroom_label.configure(text="Proxy on", fg="#bbf7d0")
            else:
                self.headroom_dot.itemconfig(self._dot_id, fill=COLORS["headroom_off"])
                self.headroom_label.configure(text="Proxy off", fg="#c7d2fe")
        self.root.after(0, _apply)

    # ================================================================
    #  Project launch
    # ================================================================

    def launch(self):
        selected = [p for p in self.projects if self.selected[p["name"]].get()]
        if not selected:
            messagebox.showwarning("Warning", "Please select at least one project")
            return

        valid = [p for p in selected if os.path.isdir(p["path"])]
        skipped = len(selected) - len(valid)

        if skipped > 0:
            names = [p["name"] for p in selected if not os.path.isdir(p["path"])]
            if not messagebox.askyesno(
                "Path not found",
                f"Skipping:\n{chr(10).join(names)}\n\nContinue with {len(valid)} project(s)?",
            ):
                return

        if not valid:
            return

        if not self.check_headroom():
            if not messagebox.askyesno(
                "Proxy not connected",
                "Headroom is not running. Try to start it?",
            ):
                return
# status removed
            if not self.start_headroom():
                return
            self._set_headroom_status(True)

        count = 0
        for p in valid:
            try:
                env = os.environ.copy()
                env["ANTHROPIC_BASE_URL"] = self.headroom_url
                proc = subprocess.Popen(
                    ["cmd", "/k", "claude"],
                    cwd=p["path"],
                    env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                self.spawned_processes.append(proc)
                count += 1
# status removed
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {p['name']}\n{e}")

# status removed

    # ================================================================
    #  Selection controls
    # ================================================================

    def _toggle_select(self):
        """Toggle between select-all and deselect-all."""
        self.all_selected = not self.all_selected
        for v in self.selected.values():
            v.set(self.all_selected)
        if self.all_selected:
            self.toggle_sel_btn.configure(text="Deselect All")
# status removed
        else:
            self.toggle_sel_btn.configure(text="Select All")
# status removed

    def select_all(self):
        for v in self.selected.values():
            v.set(True)
# status removed
        self.all_selected = True
        self.toggle_sel_btn.configure(text="Deselect All")

    def deselect_all(self):
        for v in self.selected.values():
            v.set(False)
# status removed
        self.all_selected = False
        self.toggle_sel_btn.configure(text="Select All")

    # ================================================================
    #  Cleanup & exit
    # ================================================================

    def cleanup(self):
        if self._stats_job:
            self.root.after_cancel(self._stats_job)
        if getattr(self, '_heartbeat_job', None):
            self.root.after_cancel(self._heartbeat_job)
        for proc in self.spawned_processes:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass
        self.spawned_processes.clear()
        # Also stop headroom itself if we started it
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "headroom.exe"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    def on_close(self):
        if self.spawned_processes:
            if messagebox.askokcancel("Exit", "Kill all child processes and exit?"):
                self.cleanup()
                self.root.destroy()
        else:
            self.cleanup()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ClaudeLauncher(root)
    root.mainloop()
