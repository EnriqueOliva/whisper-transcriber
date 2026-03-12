import os
import re
import time
import math
import random
import threading
import tkinter as tk
from tkinter import filedialog
import tkinterdnd2 as tkdnd
from faster_whisper import WhisperModel

from constants import (
    SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS, DEFAULT_OUTPUT_DIR, LANG_MAP,
)
from engine import extract_audio, transcribe_audio, save_output


P = {
    "bg":           "#08080f",
    "elevated":     "#111119",
    "surface":      "#1a1a24",
    "border":       "#252530",
    "text":         "#f5f0eb",
    "text_sec":     "#b0a8c0",
    "text_dim":     "#5a5570",
    "accent":       "#a78bfa",
    "accent_hover": "#c4b5fd",
    "accent_press": "#8b5cf6",
    "cyan":         "#67e8f9",
    "green":        "#86efac",
    "amber":        "#fbbf24",
    "red":          "#f87171",
    "red_hover":    "#fca5a5",
    "log_bg":       "#0a0a12",
    "log_fg":       "#8b85a0",
    "entry_bg":     "#0e0e16",
    "entry_fg":     "#d8d0e8",
}


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r, g, b):
    return f"#{max(0,min(255,int(r))):02x}{max(0,min(255,int(g))):02x}{max(0,min(255,int(b))):02x}"


def _lerp(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


def _ease(t):
    return t * t * (3 - 2 * t)


class TranscriberApp:
    def __init__(self):
        self.root = tkdnd.Tk()
        self.root.title("Whisper Transcriber")
        _s = self.root.winfo_fpixels('1i') / 96.0
        self.root.geometry(f"{int(840 * _s)}x{int(800 * _s)}")
        self.root.minsize(int(700 * _s), int(660 * _s))
        self.root.configure(bg=P["bg"])

        self.files = []
        self.model = None
        self._loaded_model_name = None
        self.is_transcribing = False
        self.cancel_requested = False
        self._progress_value = 0
        self._tick_count = 0
        self._shimmer_phase = 0.0
        self._particles = []
        self._waves = []

        self.language_var = tk.StringVar(value="Spanish")
        self.model_var = tk.StringVar(value="large-v3")
        self.output_mode_var = tk.StringVar(value="Transcript (.txt)")
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)

        self._build_ui()
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        self._tick()

    def _hover_bind(self, widget, bg_from, bg_to):
        anim = [0.0, 0, None]

        def step():
            if anim[2]:
                widget.after_cancel(anim[2])
                anim[2] = None
            anim[0] = max(0.0, min(1.0, anim[0] + 0.1 * anim[1]))
            color = _lerp(bg_from, bg_to, _ease(anim[0]))
            widget.configure(bg=color, activebackground=bg_to)
            if 0.0 < anim[0] < 1.0:
                anim[2] = widget.after(16, step)

        widget.bind("<Enter>", lambda e: (anim.__setitem__(1, 1), step()))
        widget.bind("<Leave>", lambda e: (anim.__setitem__(1, -1), step()))

    def _dropdown(self, parent, variable, values, width=16):
        outer = tk.Frame(parent, bg=P["entry_bg"], highlightbackground=P["border"],
                         highlightthickness=1, cursor="hand2")
        lbl = tk.Label(outer, textvariable=variable, font=("Bahnschrift", 10),
                       bg=P["entry_bg"], fg=P["entry_fg"], anchor="w",
                       width=width, padx=8, pady=4, cursor="hand2")
        lbl.pack(side="left", fill="both", expand=True)
        arrow = tk.Label(outer, text="\u25be", font=("Bahnschrift", 11),
                         bg=P["entry_bg"], fg=P["text_dim"], padx=6, cursor="hand2")
        arrow.pack(side="right")
        menu = tk.Menu(outer, tearoff=0, bg=P["surface"], fg=P["text_sec"],
                       activebackground=P["accent"], activeforeground=P["text"],
                       font=("Bahnschrift", 10), borderwidth=1, relief="solid")
        for val in values:
            menu.add_command(label=val, command=lambda v=val: variable.set(v))

        def show(e=None):
            menu.post(outer.winfo_rootx(), outer.winfo_rooty() + outer.winfo_height())

        for w in (outer, lbl, arrow):
            w.bind("<Button-1>", show)
        outer.bind("<Enter>", lambda e: outer.configure(highlightbackground=P["accent"]))
        outer.bind("<Leave>", lambda e: outer.configure(highlightbackground=P["border"]))
        return outer

    def _build_ui(self):
        main = tk.Frame(self.root, bg=P["bg"])
        main.pack(fill="both", expand=True, padx=26, pady=(0, 20))

        self._build_header(main)
        self._build_drop_zone(main)
        self._build_file_list(main)
        self._build_settings(main)
        self._build_action_bar(main)
        self._build_progress(main)

    def _build_header(self, parent):
        self.header_canvas = tk.Canvas(parent, bg=P["bg"], highlightthickness=0, height=72)
        self.header_canvas.pack(fill="x", pady=(14, 14))

        wave_alphas = [0.07, 0.10, 0.05]
        for a in wave_alphas:
            color = _lerp(P["bg"], P["accent"], a)
            line = self.header_canvas.create_line(0, 36, 1, 36, fill=color, width=1.5, smooth=True)
            self._waves.append(line)

        self.header_canvas.create_text(
            26, 16, text="WHISPER TRANSCRIBER", anchor="w",
            fill=P["text"], font=("Bahnschrift SemiBold", 18)
        )
        self.header_canvas.create_text(
            26, 54, text="Drag & drop audio/video files to transcribe them locally using AI",
            anchor="w", fill=P["text_dim"], font=("Bahnschrift Light", 9)
        )

    def _build_drop_zone(self, parent):
        self.drop_canvas = tk.Canvas(parent, bg=P["surface"], highlightthickness=0,
                                      height=90, cursor="hand2")
        self.drop_canvas.pack(fill="x", pady=(0, 12))

        self._init_particles()

        self.drop_canvas.create_text(0, 0, text="", tags="drop_main",
                                      fill=P["text_dim"], font=("Bahnschrift", 11))
        self.drop_canvas.create_text(0, 0, text="", tags="drop_sub",
                                      fill=P["text_dim"], font=("Bahnschrift Light", 9))

        self.drop_canvas.bind("<Configure>", self._redraw_drop_zone)
        self.drop_canvas.bind("<Enter>", lambda e: self._redraw_drop_zone(None, hover=True))
        self.drop_canvas.bind("<Leave>", lambda e: self._redraw_drop_zone(None, hover=False))
        self.drop_canvas.bind("<Button-1>", lambda e: self._browse_files())

        self.drop_canvas.drop_target_register(tkdnd.DND_FILES)
        self.drop_canvas.dnd_bind("<<Drop>>", self._on_drop)
        self._drop_hover = False

    def _init_particles(self):
        self._particles = []
        for _ in range(18):
            self._particles.append({
                "x": random.random(), "y": random.random(),
                "dx": random.uniform(-0.0008, 0.0008),
                "dy": random.uniform(-0.0008, 0.0008),
                "r": random.uniform(1.5, 3.0),
                "phase": random.uniform(0, math.pi * 2),
                "id": None,
            })

    def _create_particle_items(self):
        for p in self._particles:
            if p["id"] is None:
                p["id"] = self.drop_canvas.create_oval(0, 0, 1, 1, fill=P["surface"], outline="")
                self.drop_canvas.tag_lower(p["id"])

    def _redraw_drop_zone(self, event=None, hover=None):
        if hover is not None:
            self._drop_hover = hover
        w = self.drop_canvas.winfo_width()
        h = self.drop_canvas.winfo_height()
        if w < 10:
            return
        text_color = P["accent"] if self._drop_hover else P["text_dim"]
        self.drop_canvas.itemconfigure("drop_main", fill=text_color,
                                        text="Drop audio or video files here")
        self.drop_canvas.coords("drop_main", w // 2, h // 2 - 10)
        sub_color = P["text_sec"] if self._drop_hover else _lerp(P["text_dim"], P["bg"], 0.3)
        self.drop_canvas.itemconfigure("drop_sub", fill=sub_color,
                                        text="or click to browse")
        self.drop_canvas.coords("drop_sub", w // 2, h // 2 + 14)
        self._create_particle_items()

    def _build_file_list(self, parent):
        list_frame = tk.Frame(parent, bg=P["elevated"])
        list_frame.pack(fill="both", expand=True, pady=(0, 12))

        header = tk.Frame(list_frame, bg=P["elevated"])
        header.pack(fill="x", padx=(14, 44), pady=(10, 0))
        self.file_count_label = tk.Label(header, text="Files (0)", bg=P["elevated"],
                                          fg=P["text"], font=("Bahnschrift SemiBold", 10))
        self.file_count_label.pack(side="left")

        clear_frame = tk.Frame(header, bg=P["border"], padx=1, pady=1)
        clear_frame.pack(side="right")
        clear_btn = tk.Button(clear_frame, text="Clear all", font=("Bahnschrift", 9),
                              bg=P["surface"], fg=P["text_sec"],
                              activebackground=P["border"], activeforeground=P["accent"],
                              borderwidth=0, relief="flat", cursor="hand2",
                              padx=14, pady=7, command=self._clear_files)
        clear_btn.pack()
        self._hover_bind(clear_btn, P["surface"], P["border"])

        canvas_frame = tk.Frame(list_frame, bg=P["elevated"])
        canvas_frame.pack(fill="both", expand=True, padx=14, pady=(6, 12))

        self.file_canvas = tk.Canvas(canvas_frame, bg=P["elevated"], highlightthickness=0, height=120)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.file_canvas.yview,
                                 bg=P["surface"], troughcolor=P["elevated"],
                                 activebackground=P["border"], width=6,
                                 highlightthickness=0, bd=0, relief="flat")
        self.file_inner = tk.Frame(self.file_canvas, bg=P["elevated"])

        self.file_inner.bind("<Configure>",
                             lambda e: self.file_canvas.configure(scrollregion=self.file_canvas.bbox("all")))
        self._file_window_id = self.file_canvas.create_window((0, 0), window=self.file_inner, anchor="nw")
        self.file_canvas.configure(yscrollcommand=scrollbar.set)

        self.file_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.file_canvas.bind("<Configure>", self._on_file_canvas_configure)
        self.file_canvas.bind("<Enter>", lambda e: self.file_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.file_canvas.bind("<Leave>", lambda e: self.file_canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.file_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_file_canvas_configure(self, event):
        self.file_canvas.itemconfigure(self._file_window_id, width=event.width)

    def _build_settings(self, parent):
        settings = tk.Frame(parent, bg=P["elevated"])
        settings.pack(fill="x", pady=(0, 12))

        inner = tk.Frame(settings, bg=P["elevated"])
        inner.pack(fill="x", padx=14, pady=12)

        row1 = tk.Frame(inner, bg=P["elevated"])
        row1.pack(fill="x", pady=(0, 8))

        tk.Label(row1, text="Language", bg=P["elevated"], fg=P["text_sec"],
                 font=("Bahnschrift", 10)).pack(side="left")
        self._dropdown(row1, self.language_var,
                       ["Auto-detect", "Spanish", "English", "Portuguese", "French",
                        "German", "Italian", "Japanese", "Chinese", "Korean"],
                       width=14).pack(side="left", padx=(8, 28))

        tk.Label(row1, text="Model", bg=P["elevated"], fg=P["text_sec"],
                 font=("Bahnschrift", 10)).pack(side="left")
        self._dropdown(row1, self.model_var,
                       ["large-v3", "medium", "small", "base", "tiny"],
                       width=14).pack(side="left", padx=(8, 0))

        row2 = tk.Frame(inner, bg=P["elevated"])
        row2.pack(fill="x", pady=(0, 8))

        tk.Label(row2, text="Output format", bg=P["elevated"], fg=P["text_sec"],
                 font=("Bahnschrift", 10)).pack(side="left")
        self._dropdown(row2, self.output_mode_var,
                       ["Transcript (.txt)", "Rename source by transcript"],
                       width=28).pack(side="left", padx=(8, 0))

        row3 = tk.Frame(inner, bg=P["elevated"])
        row3.pack(fill="x")

        tk.Label(row3, text="Output path", bg=P["elevated"], fg=P["text_sec"],
                 font=("Bahnschrift", 10)).pack(side="left")
        output_entry = tk.Entry(row3, textvariable=self.output_var, font=("Bahnschrift", 10),
                                bg=P["entry_bg"], fg=P["entry_fg"], insertbackground=P["accent"],
                                relief="flat", highlightbackground=P["border"], highlightthickness=1)
        output_entry.pack(side="left", padx=(8, 8), fill="x", expand=True, ipady=4)

        browse_frame = tk.Frame(row3, bg=P["border"], padx=1, pady=1)
        browse_frame.pack(side="left")
        browse_btn = tk.Button(browse_frame, text="Browse", font=("Bahnschrift", 9),
                               bg=P["surface"], fg=P["text_sec"],
                               activebackground=P["border"], activeforeground=P["accent"],
                               borderwidth=0, relief="flat", cursor="hand2",
                               padx=14, pady=7, command=self._browse_output)
        browse_btn.pack()
        self._hover_bind(browse_btn, P["surface"], P["border"])

    def _build_action_bar(self, parent):
        action = tk.Frame(parent, bg=P["bg"])
        action.pack(fill="x", pady=(0, 12))

        self.transcribe_btn = tk.Button(
            action, text="\u25b6  TRANSCRIBE", font=("Bahnschrift SemiBold", 11),
            bg=P["accent"], fg=P["bg"], activebackground=P["accent_hover"],
            activeforeground=P["bg"], borderwidth=0, cursor="hand2",
            padx=32, pady=11, relief="flat"
        )
        self.transcribe_btn.configure(command=self._toggle_transcription)
        self.transcribe_btn.pack(side="left")

        self._btn_anim = [0.0, 0, None]

        def btn_step():
            if self._btn_anim[2]:
                self.transcribe_btn.after_cancel(self._btn_anim[2])
                self._btn_anim[2] = None
            self._btn_anim[0] = max(0.0, min(1.0, self._btn_anim[0] + 0.1 * self._btn_anim[1]))
            text = self.transcribe_btn.cget("text")
            if "TRANSCRIBE" in text:
                color = _lerp(P["accent"], P["accent_hover"], _ease(self._btn_anim[0]))
                self.transcribe_btn.configure(bg=color)
            elif "CANCEL" in text and "CANCELLING" not in text:
                color = _lerp(P["red"], P["red_hover"], _ease(self._btn_anim[0]))
                self.transcribe_btn.configure(bg=color)
            if 0.0 < self._btn_anim[0] < 1.0:
                self._btn_anim[2] = self.transcribe_btn.after(16, btn_step)

        self.transcribe_btn.bind("<Enter>", lambda e: (self._btn_anim.__setitem__(1, 1), btn_step()))
        self.transcribe_btn.bind("<Leave>", lambda e: (self._btn_anim.__setitem__(1, -1), btn_step()))

        open_frame = tk.Frame(action, bg=P["border"], padx=1, pady=1)
        open_frame.pack(side="right")
        open_btn = tk.Button(open_frame, text="Open output \u2192", font=("Bahnschrift", 9),
                             bg=P["surface"], fg=P["text_sec"],
                             activebackground=P["border"], activeforeground=P["accent"],
                             borderwidth=0, relief="flat", cursor="hand2",
                             padx=14, pady=7, command=self._open_output)
        open_btn.pack()
        self._hover_bind(open_btn, P["surface"], P["border"])

    def _build_progress(self, parent):
        prog_frame = tk.Frame(parent, bg=P["elevated"])
        prog_frame.pack(fill="both", expand=True)

        inner = tk.Frame(prog_frame, bg=P["elevated"])
        inner.pack(fill="both", expand=True, padx=14, pady=12)

        status_row = tk.Frame(inner, bg=P["elevated"])
        status_row.pack(fill="x")

        self.progress_label = tk.Label(status_row, text="Ready", bg=P["elevated"],
                                        fg=P["text_sec"], font=("Bahnschrift", 9), anchor="w")
        self.progress_label.pack(side="left")

        self.progress_pct = tk.Label(status_row, text="", bg=P["elevated"],
                                      fg=P["text_dim"], font=("Bahnschrift", 9))
        self.progress_pct.pack(side="right")

        self.progress_canvas = tk.Canvas(inner, bg=P["surface"], highlightthickness=0, height=5)
        self.progress_canvas.pack(fill="x", pady=(8, 10))

        log_frame = tk.Frame(inner, bg=P["log_bg"], highlightbackground=P["border"],
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg=P["log_bg"], fg=P["log_fg"],
                                font=("Cascadia Mono", 9), height=7, wrap="word",
                                state="disabled", borderwidth=6, relief="flat",
                                highlightthickness=0, insertbackground=P["accent"],
                                selectbackground=P["accent"], selectforeground=P["text"])
        log_scroll = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview,
                                  bg=P["surface"], troughcolor=P["log_bg"],
                                  activebackground=P["border"], width=6,
                                  highlightthickness=0, bd=0, relief="flat")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _tick(self):
        self._tick_count += 1
        self._animate_waveform()
        self._animate_particles()
        if self.is_transcribing and self._progress_value > 0:
            self._shimmer_phase = (self._shimmer_phase + 0.025) % 1.0
            self._draw_progress()
        self.root.after(33, self._tick)

    def _animate_waveform(self):
        w = self.header_canvas.winfo_width()
        if w < 20:
            return
        t = self._tick_count * 0.04
        configs = [
            (14, 0.012, 1.0),
            (10, 0.018, 1.4),
            (8, 0.008, 0.6),
        ]
        for i, line_id in enumerate(self._waves):
            amp, freq, speed = configs[i]
            phase = t * speed
            points = []
            for x in range(0, w, 5):
                y = 36 + math.sin(x * freq + phase) * amp + math.sin(x * freq * 2.3 + phase * 0.7) * amp * 0.3
                points.extend([x, y])
            if len(points) >= 4:
                self.header_canvas.coords(line_id, *points)

    def _animate_particles(self):
        w = self.drop_canvas.winfo_width()
        h = self.drop_canvas.winfo_height()
        if w < 10 or h < 10:
            return
        t = self._tick_count * 0.03
        for p in self._particles:
            if p["id"] is None:
                continue
            p["x"] += p["dx"]
            p["y"] += p["dy"]
            if p["x"] < 0: p["x"] += 1
            if p["x"] > 1: p["x"] -= 1
            if p["y"] < 0: p["y"] += 1
            if p["y"] > 1: p["y"] -= 1
            brightness = 0.12 + 0.08 * math.sin(t + p["phase"])
            color = _lerp(P["surface"], P["accent"], brightness)
            px, py, r = p["x"] * w, p["y"] * h, p["r"]
            self.drop_canvas.coords(p["id"], px - r, py - r, px + r, py + r)
            self.drop_canvas.itemconfig(p["id"], fill=color)

    def _draw_progress(self):
        c = self.progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4:
            return
        c.create_rectangle(0, 0, w, h, fill=P["surface"], outline="")
        if self._progress_value > 0:
            fill_w = max(2, int(w * self._progress_value / 100))
            c.create_rectangle(0, 0, fill_w, h, fill=P["accent"], outline="")
            band_w = 60
            band_pos = self._shimmer_phase * (fill_w + band_w) - band_w
            bx0 = max(0, int(band_pos))
            bx1 = min(fill_w, int(band_pos + band_w))
            if bx1 > bx0:
                mid = (bx0 + bx1) / 2
                half = (bx1 - bx0) / 2
                for i in range(3):
                    frac = 1.0 - i * 0.3
                    sx0 = int(mid - half * frac)
                    sx1 = int(mid + half * frac)
                    alpha = 0.4 - i * 0.12
                    shimmer_color = _lerp(P["accent"], P["cyan"], alpha)
                    c.create_rectangle(sx0, 0, sx1, h, fill=shimmer_color, outline="")

    def _on_drop(self, event):
        raw = event.data
        paths = []
        for match in re.finditer(r'\{([^}]+)\}|(\S+)', raw):
            p = match.group(1) or match.group(2)
            if p:
                paths.append(p)
        self._add_files(paths)

    def _browse_files(self):
        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        paths = filedialog.askopenfilenames(
            title="Select audio/video files",
            filetypes=[("Media files", exts), ("All files", "*.*")]
        )
        if paths:
            self._add_files(paths)

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.output_var.set(d)

    def _add_files(self, paths):
        added = 0
        for p in paths:
            p = p.strip('"').strip("'")
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_EXTENSIONS and p not in self.files:
                self.files.append(p)
                added += 1
        if added:
            self._refresh_file_list()
        elif paths:
            self._log("No supported files found in the dropped items.")

    def _remove_file(self, path):
        if path in self.files:
            self.files.remove(path)
            self._refresh_file_list()

    def _clear_files(self):
        self.files.clear()
        self._refresh_file_list()

    def _refresh_file_list(self):
        for widget in self.file_inner.winfo_children():
            widget.destroy()

        self.file_count_label.configure(text=f"Files ({len(self.files)})")

        for idx, path in enumerate(self.files):
            bg = P["elevated"] if idx % 2 == 0 else _lerp(P["elevated"], P["surface"], 0.3)
            row = tk.Frame(self.file_inner, bg=bg)
            row.pack(fill="x", pady=0)

            name = os.path.basename(path)
            ext = os.path.splitext(path)[1].lower()
            is_video = ext in VIDEO_EXTENSIONS
            tag = "VID" if is_video else "AUD"
            color = P["amber"] if is_video else P["cyan"]

            tk.Label(row, text=tag, bg=bg, fg=color,
                     font=("Cascadia Mono", 7, "bold")).pack(side="left", padx=(10, 10), pady=5)

            tk.Label(row, text=name, bg=bg, fg=P["text_sec"],
                     font=("Bahnschrift", 10), anchor="w").pack(side="left", fill="x", expand=True)

            remove_btn = tk.Button(row, text="\u00d7", bg=bg, fg=P["text_dim"],
                                   font=("Bahnschrift", 14), borderwidth=0, cursor="hand2",
                                   activebackground=bg, activeforeground=P["red"],
                                   padx=6, pady=2,
                                   command=lambda p=path: self._remove_file(p))
            remove_btn.pack(side="right", padx=(0, 10))

    def _toggle_transcription(self):
        if self.is_transcribing:
            self.cancel_requested = True
            self.transcribe_btn.configure(text="CANCELLING...", bg=P["text_dim"],
                                           activebackground=P["text_dim"], state="disabled")
            return

        if not self.files:
            self._log("No files to transcribe. Add some files first.")
            return

        self.is_transcribing = True
        self.cancel_requested = False
        self.transcribe_btn.configure(text="\u25a0  CANCEL", bg=P["red"],
                                       activebackground=P["red_hover"])
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _transcribe_worker(self):
        output_dir = self.output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        total = len(self.files)

        try:
            model_name = self.model_var.get()
            self._update_status(f"Loading model '{model_name}'...")
            self._set_progress(0)

            if self.model is None or self._loaded_model_name != model_name:
                self.model = WhisperModel(model_name, device="cuda", compute_type="float16")
                self._loaded_model_name = model_name

            self._log(f"Model '{model_name}' loaded on GPU")

            language = self.language_var.get()
            lang_code = None if language == "Auto-detect" else LANG_MAP.get(language)

            for i, filepath in enumerate(self.files):
                if self.cancel_requested:
                    self._log("Transcription cancelled.")
                    break

                name = os.path.basename(filepath)
                self._update_status(f"[{i + 1}/{total}] {name}")
                self._set_progress((i / total) * 100)
                self._log(f"Processing: {name}")

                start_time = time.time()

                try:
                    audio_path = filepath
                    ext = os.path.splitext(filepath)[1].lower()
                    temp_audio = None

                    if ext in VIDEO_EXTENSIONS:
                        self._log(f"  Extracting audio from video...")
                        temp_audio = extract_audio(filepath, output_dir)
                        audio_path = temp_audio

                    def on_progress(seg_end, duration):
                        pct = (i / total + (seg_end / duration) / total) * 100
                        self._set_progress(min(pct, 99))

                    text_parts, info, status = transcribe_audio(
                        self.model, audio_path, lang_code,
                        on_progress=on_progress,
                        is_cancelled=lambda: self.cancel_requested
                    )

                    if status == "timed_out":
                        self._log(f"  Timed out, skipping")
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        continue

                    if status == "retry_timed_out":
                        self._log(f"  Retry timed out, skipping")

                    if self.cancel_requested:
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        break

                    full_text = "\n".join(text_parts)

                    if not full_text.strip():
                        self._log(f"  No speech detected, skipping")
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        continue

                    copy_renamed = self.output_mode_var.get() != "Transcript (.txt)"
                    saved_name = save_output(
                        filepath, full_text, output_dir, copy_renamed
                    )

                    elapsed = time.time() - start_time
                    detected = info.language if language == "Auto-detect" else language
                    self._log(f"  Done in {elapsed:.1f}s \u00b7 {detected} \u00b7 {saved_name}")

                    if temp_audio and os.path.exists(temp_audio):
                        os.remove(temp_audio)

                except Exception as e:
                    self._log(f"  Error: {str(e)}")
                    continue

            if not self.cancel_requested:
                self._set_progress(100)
                self._update_status(f"Complete \u2014 {total} file(s) processed")
                self._log(f"All done. Output: {output_dir}")

        except Exception as e:
            self._log(f"Fatal error: {str(e)}")
            self._update_status("Error occurred")

        finally:
            self.is_transcribing = False
            self.cancel_requested = False
            self.root.after(0, lambda: self.transcribe_btn.configure(
                text="\u25b6  TRANSCRIBE", bg=P["accent"],
                activebackground=P["accent_hover"], state="normal"))

    def _open_output(self):
        output_dir = self.output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)

    def _update_status(self, text):
        self.root.after(0, lambda: self.progress_label.configure(text=text))

    def _set_progress(self, value):
        self._progress_value = value
        def _update():
            self._draw_progress()
            self.progress_pct.configure(text=f"{int(value)}%" if value > 0 else "")
        self.root.after(0, _update)

    def _log(self, text):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _append)

    def run(self):
        self.root.mainloop()
