import os
import re
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import tkinterdnd2 as tkdnd
from faster_whisper import WhisperModel

from constants import (
    SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS, DEFAULT_OUTPUT_DIR, LANG_MAP,
)
from engine import extract_audio, transcribe_audio, save_output

P = {
    "bg":           "#0d1117",
    "surface":      "#151b23",
    "elevated":     "#1c2333",
    "border":       "#30363d",
    "border_sub":   "#21262d",
    "text":         "#f0f6fc",
    "text_sec":     "#c9d1d9",
    "text_dim":     "#8b949e",
    "text_muted":   "#484f58",
    "accent":       "#00d4aa",
    "accent_hover": "#2effcc",
    "accent_press": "#00b892",
    "accent_glow":  "#00d4aa",
    "tag_vid":      "#ffa657",
    "tag_aud":      "#79c0ff",
    "red":          "#ff7b72",
    "red_hover":    "#ffa198",
    "green":        "#7ee787",
    "log_bg":       "#010409",
    "log_fg":       "#7ee787",
    "entry_bg":     "#0d1117",
    "entry_fg":     "#c9d1d9",
    "row_alt":      "#131a24",
}


class TranscriberApp:
    def __init__(self):
        self.root = tkdnd.Tk()
        self.root.title("Whisper Transcriber")
        self.root.geometry("800x800")
        self.root.minsize(700, 680)
        self.root.configure(bg=P["bg"])

        self.files = []
        self.model = None
        self._loaded_model_name = None
        self.is_transcribing = False
        self.cancel_requested = False
        self.copy_renamed_var = tk.BooleanVar(value=False)
        self._drop_hover = False
        self._progress_value = 0

        self._setup_styles()
        self._build_menu_bar()
        self._build_ui()

        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Main.TFrame", background=P["bg"])
        style.configure("Surface.TFrame", background=P["surface"])

        style.configure("Title.TLabel", background=P["bg"], foreground=P["text"],
                         font=("Bahnschrift SemiBold", 20))
        style.configure("Sub.TLabel", background=P["bg"], foreground=P["text_muted"],
                         font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=P["bg"], foreground=P["text_dim"],
                         font=("Bahnschrift SemiBold", 9))
        style.configure("Dim.TLabel", background=P["bg"], foreground=P["text_muted"],
                         font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=P["bg"], foreground=P["text_dim"],
                         font=("Segoe UI", 9))

        style.configure("Subtle.TButton", font=("Segoe UI", 9), padding=(8, 3),
                         background=P["surface"], foreground=P["text_dim"])
        style.map("Subtle.TButton",
                  background=[("active", P["border"])],
                  foreground=[("active", P["text_sec"])])

        style.configure("Link.TButton", font=("Segoe UI", 9), padding=(10, 6),
                         background=P["bg"], foreground=P["text_dim"])
        style.map("Link.TButton",
                  background=[("active", P["surface"])],
                  foreground=[("active", P["accent"])])

        style.configure("TCombobox", fieldbackground=P["entry_bg"], background=P["surface"],
                         foreground=P["entry_fg"], arrowcolor=P["text_dim"],
                         selectbackground=P["accent"], selectforeground=P["text"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", P["entry_bg"])],
                  foreground=[("readonly", P["entry_fg"])])

        style.configure("TEntry", fieldbackground=P["entry_bg"], foreground=P["entry_fg"],
                         insertcolor=P["accent"])

        style.configure("TScrollbar", background=P["surface"], troughcolor=P["bg"],
                         arrowcolor=P["text_muted"], bordercolor=P["bg"], width=8)
        style.map("TScrollbar", background=[("active", P["border"])])

    def _build_menu_bar(self):
        menubar = tk.Menu(self.root, bg=P["surface"], fg=P["text_sec"],
                          activebackground=P["accent"], activeforeground=P["bg"],
                          font=("Segoe UI", 9), borderwidth=0, relief="flat")

        settings_menu = tk.Menu(menubar, tearoff=0, bg=P["surface"], fg=P["text_sec"],
                                activebackground=P["accent"], activeforeground=P["bg"],
                                font=("Segoe UI", 9), borderwidth=1, relief="solid")

        features_menu = tk.Menu(settings_menu, tearoff=0, bg=P["surface"], fg=P["text_sec"],
                                activebackground=P["accent"], activeforeground=P["bg"],
                                font=("Segoe UI", 9), borderwidth=1, relief="solid")

        features_menu.add_checkbutton(
            label="Copy source file renamed by transcript content",
            variable=self.copy_renamed_var,
            onvalue=True, offvalue=False
        )

        settings_menu.add_cascade(label="Special features", menu=features_menu)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        accent_line = tk.Frame(self.root, bg=P["accent"], height=2)
        accent_line.pack(fill="x")

        main = ttk.Frame(self.root, style="Main.TFrame")
        main.pack(fill="both", expand=True, padx=26, pady=(16, 20))

        self._build_header(main)
        self._build_drop_zone(main)
        self._build_file_queue(main)
        self._build_settings(main)
        self._build_action_bar(main)
        self._build_progress(main)
        self._build_log(main)

    def _build_header(self, parent):
        title_row = ttk.Frame(parent, style="Main.TFrame")
        title_row.pack(fill="x", pady=(0, 2))

        dot = tk.Label(title_row, text="\u25cf", bg=P["bg"], fg=P["accent"],
                       font=("Segoe UI", 8))
        dot.pack(side="left", padx=(0, 8))

        ttk.Label(title_row, text="Whisper Transcriber", style="Title.TLabel").pack(side="left")

        ttk.Label(parent, text="Local AI transcription  \u00b7  GPU accelerated  \u00b7  100% offline",
                  style="Sub.TLabel").pack(anchor="w", pady=(0, 18))

    def _build_drop_zone(self, parent):
        self.drop_canvas = tk.Canvas(parent, bg=P["bg"], highlightthickness=0,
                                      height=85, cursor="hand2")
        self.drop_canvas.pack(fill="x", pady=(0, 18))

        self.drop_canvas.bind("<Configure>", self._redraw_drop_zone)
        self.drop_canvas.bind("<Enter>", lambda e: self._redraw_drop_zone(None, hover=True))
        self.drop_canvas.bind("<Leave>", lambda e: self._redraw_drop_zone(None, hover=False))
        self.drop_canvas.bind("<Button-1>", lambda e: self._browse_files())

        self.drop_canvas.drop_target_register(tkdnd.DND_FILES)
        self.drop_canvas.dnd_bind("<<Drop>>", self._on_drop)

    def _redraw_drop_zone(self, event=None, hover=None):
        if hover is not None:
            self._drop_hover = hover

        c = self.drop_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()

        if w < 10:
            return

        border_color = P["accent"] if self._drop_hover else P["border"]
        text_color = P["accent"] if self._drop_hover else P["text_dim"]

        c.create_rectangle(2, 2, w - 2, h - 2, outline=border_color, width=1, dash=(8, 5))

        c.create_text(w // 2, h // 2 - 10,
                      text="Drop audio or video files here",
                      fill=text_color, font=("Bahnschrift", 11))
        c.create_text(w // 2, h // 2 + 12,
                      text="or click to browse",
                      fill=P["text_muted"], font=("Segoe UI", 9))

    def _build_file_queue(self, parent):
        header = ttk.Frame(parent, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 6))

        ttk.Label(header, text="QUEUE", style="Section.TLabel").pack(side="left")

        sep = tk.Frame(header, bg=P["border_sub"], height=1)
        sep.pack(side="left", fill="x", expand=True, padx=(12, 12), pady=1)

        self.file_count_label = ttk.Label(header, text="0 files", style="Dim.TLabel")
        self.file_count_label.pack(side="left", padx=(0, 10))

        ttk.Button(header, text="Clear", style="Subtle.TButton",
                   command=self._clear_files).pack(side="right")

        list_container = tk.Frame(parent, bg=P["surface"], highlightbackground=P["border_sub"],
                                   highlightthickness=1)
        list_container.pack(fill="both", expand=True, pady=(0, 16))

        self.file_canvas = tk.Canvas(list_container, bg=P["surface"], highlightthickness=0,
                                      height=115)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.file_canvas.yview)
        self.file_inner = tk.Frame(self.file_canvas, bg=P["surface"])

        self.file_inner.bind("<Configure>",
                             lambda e: self.file_canvas.configure(scrollregion=self.file_canvas.bbox("all")))
        self.file_canvas.create_window((0, 0), window=self.file_inner, anchor="nw")
        self.file_canvas.configure(yscrollcommand=scrollbar.set)

        self.file_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.file_canvas.bind("<Enter>",
                              lambda e: self.file_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.file_canvas.bind("<Leave>",
                              lambda e: self.file_canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.file_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_settings(self, parent):
        row1 = ttk.Frame(parent, style="Main.TFrame")
        row1.pack(fill="x", pady=(0, 8))

        ttk.Label(row1, text="Language", style="Section.TLabel").pack(side="left")
        self.language_var = tk.StringVar(value="Spanish")
        ttk.Combobox(row1, textvariable=self.language_var, width=14, state="readonly",
                     values=["Auto-detect", "Spanish", "English", "Portuguese", "French",
                             "German", "Italian", "Japanese", "Chinese", "Korean"]
                     ).pack(side="left", padx=(8, 28))

        ttk.Label(row1, text="Model", style="Section.TLabel").pack(side="left")
        self.model_var = tk.StringVar(value="large-v3")
        ttk.Combobox(row1, textvariable=self.model_var, width=14, state="readonly",
                     values=["large-v3", "medium", "small", "base", "tiny"]
                     ).pack(side="left", padx=(8, 0))

        row2 = ttk.Frame(parent, style="Main.TFrame")
        row2.pack(fill="x", pady=(0, 14))

        ttk.Label(row2, text="Output", style="Section.TLabel").pack(side="left")
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        ttk.Entry(row2, textvariable=self.output_var, width=52
                  ).pack(side="left", padx=(10, 6), fill="x", expand=True)
        ttk.Button(row2, text="Browse", style="Subtle.TButton",
                   command=self._browse_output).pack(side="left")

    def _build_action_bar(self, parent):
        action = ttk.Frame(parent, style="Main.TFrame")
        action.pack(fill="x", pady=(0, 16))

        self.transcribe_btn = tk.Button(
            action, text="\u25b6  TRANSCRIBE", font=("Bahnschrift SemiBold", 11),
            bg=P["accent"], fg=P["bg"], activebackground=P["accent_hover"],
            activeforeground=P["bg"], borderwidth=0, cursor="hand2",
            padx=34, pady=11, relief="flat"
        )
        self.transcribe_btn.configure(command=self._toggle_transcription)
        self.transcribe_btn.pack(side="left")

        def _btn_enter(e):
            text = self.transcribe_btn.cget("text")
            if "TRANSCRIBE" in text:
                self.transcribe_btn.configure(bg=P["accent_hover"])
            elif "CANCEL" in text and "CANCELLING" not in text:
                self.transcribe_btn.configure(bg=P["red_hover"])

        def _btn_leave(e):
            text = self.transcribe_btn.cget("text")
            if "TRANSCRIBE" in text:
                self.transcribe_btn.configure(bg=P["accent"])
            elif "CANCEL" in text and "CANCELLING" not in text:
                self.transcribe_btn.configure(bg=P["red"])

        self.transcribe_btn.bind("<Enter>", _btn_enter)
        self.transcribe_btn.bind("<Leave>", _btn_leave)

        ttk.Button(action, text="Open output  \u2192", style="Link.TButton",
                   command=self._open_output).pack(side="right")

    def _build_progress(self, parent):
        status_row = ttk.Frame(parent, style="Main.TFrame")
        status_row.pack(fill="x", pady=(0, 6))

        self.progress_label = ttk.Label(status_row, text="Ready", style="Status.TLabel")
        self.progress_label.pack(side="left")

        self.progress_pct = ttk.Label(status_row, text="", style="Dim.TLabel")
        self.progress_pct.pack(side="right")

        self.progress_canvas = tk.Canvas(parent, bg=P["surface"], highlightthickness=0, height=4)
        self.progress_canvas.pack(fill="x", pady=(0, 12))
        self.progress_canvas.bind("<Configure>", lambda e: self._redraw_progress())

    def _redraw_progress(self):
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

    def _build_log(self, parent):
        log_container = tk.Frame(parent, bg=P["log_bg"], highlightbackground=P["border_sub"],
                                  highlightthickness=1)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_container, bg=P["log_bg"], fg=P["log_fg"],
                                font=("Cascadia Code", 9), height=8, wrap="word",
                                state="disabled", borderwidth=6, relief="flat",
                                highlightthickness=0, insertbackground=P["accent"],
                                selectbackground=P["accent"], selectforeground=P["text"])
        log_scroll = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

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

        count = len(self.files)
        self.file_count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")

        for idx, path in enumerate(self.files):
            bg = P["surface"] if idx % 2 == 0 else P["row_alt"]
            row = tk.Frame(self.file_inner, bg=bg)
            row.pack(fill="x")

            name = os.path.basename(path)
            ext = os.path.splitext(path)[1].lower()
            is_video = ext in VIDEO_EXTENSIONS
            tag = "VID" if is_video else "AUD"
            color = P["tag_vid"] if is_video else P["tag_aud"]

            tk.Label(row, text=tag, bg=bg, fg=color,
                     font=("Cascadia Code", 7, "bold")).pack(side="left", padx=(10, 10), pady=4)

            tk.Label(row, text=name, bg=bg, fg=P["text_sec"],
                     font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

            remove_btn = tk.Button(row, text="\u00d7", bg=bg, fg=P["text_muted"],
                                   font=("Segoe UI", 10), borderwidth=0, cursor="hand2",
                                   activebackground=bg, activeforeground=P["red"],
                                   command=lambda p=path: self._remove_file(p))
            remove_btn.pack(side="right", padx=(0, 10))

    def _toggle_transcription(self):
        if self.is_transcribing:
            self.cancel_requested = True
            self.transcribe_btn.configure(text="CANCELLING...", bg=P["text_dim"],
                                           activebackground=P["text_dim"], state="disabled")
            return

        if not self.files:
            self._log("\u25b8 No files to transcribe. Add some files first.")
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

            self._log(f"\u25b8 Model '{model_name}' loaded on GPU")

            language = self.language_var.get()
            lang_code = None if language == "Auto-detect" else LANG_MAP.get(language)

            for i, filepath in enumerate(self.files):
                if self.cancel_requested:
                    self._log("\u25b8 Transcription cancelled")
                    break

                name = os.path.basename(filepath)
                self._update_status(f"[{i + 1}/{total}] {name}")
                self._set_progress((i / total) * 100)
                self._log(f"\u25b8 Processing: {name}")

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

                    saved_name = save_output(
                        filepath, full_text, output_dir, self.copy_renamed_var.get()
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
                self._log(f"\u25b8 All done. Output: {output_dir}")

        except Exception as e:
            self._log(f"\u25b8 Fatal error: {str(e)}")
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
            self._redraw_progress()
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
