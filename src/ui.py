import os
import re
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import tkinterdnd2 as tkdnd
from faster_whisper import WhisperModel

from constants import (
    C, SUPPORTED_EXTENSIONS, VIDEO_EXTENSIONS, DEFAULT_OUTPUT_DIR, LANG_MAP,
)
from engine import extract_audio, transcribe_audio, save_output


class TranscriberApp:
    def __init__(self):
        self.root = tkdnd.Tk()
        self.root.title("Whisper Transcriber")
        self.root.geometry("740x720")
        self.root.minsize(640, 620)
        self.root.configure(bg=C["bg"])

        self.files = []
        self.model = None
        self.is_transcribing = False
        self.cancel_requested = False
        self.copy_renamed_var = tk.BooleanVar(value=False)

        self._setup_styles()
        self._build_menu_bar()
        self._build_ui()

        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Main.TFrame", background=C["bg"])
        style.configure("Card.TFrame", background=C["elevated"])

        style.configure("Title.TLabel", background=C["bg"], foreground=C["text"],
                         font=("Segoe UI Semibold", 17))
        style.configure("Subtitle.TLabel", background=C["bg"], foreground=C["text_dim"],
                         font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=C["elevated"], foreground=C["text"],
                         font=("Segoe UI Semibold", 10))
        style.configure("Card.TLabel", background=C["elevated"], foreground=C["text_sec"],
                         font=("Segoe UI", 9))

        style.configure("Small.TButton", font=("Segoe UI", 9), padding=(10, 4),
                         background=C["surface"], foreground=C["text_sec"])
        style.map("Small.TButton",
                  background=[("active", C["border"])],
                  foreground=[("active", C["text"])])

        style.configure("Open.TButton", font=("Segoe UI", 9), padding=(12, 7),
                         background=C["surface"], foreground=C["text_sec"])
        style.map("Open.TButton",
                  background=[("active", C["border"])],
                  foreground=[("active", C["text"])])

        style.configure("Custom.Horizontal.TProgressbar",
                         troughcolor=C["surface"], background=C["accent"],
                         bordercolor=C["surface"], lightcolor=C["accent"],
                         darkcolor=C["accent_press"], thickness=6)

        style.configure("TCombobox", fieldbackground=C["entry_bg"], background=C["surface"],
                         foreground=C["entry_fg"], arrowcolor=C["text_sec"],
                         selectbackground=C["accent"], selectforeground=C["text"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", C["entry_bg"])],
                  foreground=[("readonly", C["entry_fg"])])

        style.configure("TEntry", fieldbackground=C["entry_bg"], foreground=C["entry_fg"],
                         insertcolor=C["accent"])

        style.configure("TScrollbar", background=C["surface"], troughcolor=C["elevated"],
                         arrowcolor=C["text_dim"], bordercolor=C["elevated"])
        style.map("TScrollbar", background=[("active", C["border"])])

    def _build_menu_bar(self):
        menubar = tk.Menu(self.root, bg=C["elevated"], fg=C["text_sec"],
                          activebackground=C["accent"], activeforeground=C["text"],
                          font=("Segoe UI", 9), borderwidth=0, relief="flat")

        settings_menu = tk.Menu(menubar, tearoff=0, bg=C["elevated"], fg=C["text_sec"],
                                activebackground=C["accent"], activeforeground=C["text"],
                                font=("Segoe UI", 9), borderwidth=1, relief="solid")

        features_menu = tk.Menu(settings_menu, tearoff=0, bg=C["elevated"], fg=C["text_sec"],
                                activebackground=C["accent"], activeforeground=C["text"],
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
        main_frame = ttk.Frame(self.root, style="Main.TFrame")
        main_frame.pack(fill="both", expand=True, padx=22, pady=(10, 16))

        ttk.Label(main_frame, text="Whisper Transcriber", style="Title.TLabel").pack(anchor="w")
        ttk.Label(main_frame, text="Drag & drop audio/video files to transcribe them locally using AI",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(2, 14))

        self._build_drop_zone(main_frame)
        self._build_file_list(main_frame)
        self._build_settings(main_frame)
        self._build_action_bar(main_frame)
        self._build_progress_area(main_frame)

    def _build_drop_zone(self, parent):
        self.drop_frame = tk.Frame(parent, bg=C["surface"], highlightbackground=C["border"],
                                   highlightthickness=1, cursor="hand2")
        self.drop_frame.pack(fill="x", pady=(0, 10), ipady=22)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="\u2591\u2591\u2591    Drop files here  \u00b7  click to browse    \u2591\u2591\u2591",
            bg=C["surface"], fg=C["text_dim"], font=("Consolas", 10)
        )
        self.drop_label.pack(expand=True, fill="both", padx=10, pady=10)

        for widget in (self.drop_frame, self.drop_label):
            widget.drop_target_register(tkdnd.DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)
            widget.bind("<Button-1>", lambda e: self._browse_files())

        self.drop_frame.bind("<Enter>", lambda e: (
            self.drop_frame.configure(highlightbackground=C["accent"]),
            self.drop_label.configure(fg=C["accent"])
        ))
        self.drop_frame.bind("<Leave>", lambda e: (
            self.drop_frame.configure(highlightbackground=C["border"]),
            self.drop_label.configure(fg=C["text_dim"])
        ))

    def _build_file_list(self, parent):
        list_frame = ttk.Frame(parent, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        header = ttk.Frame(list_frame, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(8, 0))
        self.file_count_label = ttk.Label(header, text="Files (0)", style="CardTitle.TLabel")
        self.file_count_label.pack(side="left")

        clear_btn = ttk.Button(header, text="Clear all", style="Small.TButton",
                               command=self._clear_files)
        clear_btn.pack(side="right")

        canvas_frame = ttk.Frame(list_frame, style="Card.TFrame")
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.file_canvas = tk.Canvas(canvas_frame, bg=C["elevated"], highlightthickness=0, height=120)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.file_canvas.yview)
        self.file_inner = tk.Frame(self.file_canvas, bg=C["elevated"])

        self.file_inner.bind("<Configure>",
                             lambda e: self.file_canvas.configure(scrollregion=self.file_canvas.bbox("all")))
        self.file_canvas.create_window((0, 0), window=self.file_inner, anchor="nw")
        self.file_canvas.configure(yscrollcommand=scrollbar.set)

        self.file_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.file_canvas.bind("<Enter>", lambda e: self.file_canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.file_canvas.bind("<Leave>", lambda e: self.file_canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self.file_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_settings(self, parent):
        settings_frame = ttk.Frame(parent, style="Card.TFrame")
        settings_frame.pack(fill="x", pady=(0, 10))

        inner = ttk.Frame(settings_frame, style="Card.TFrame")
        inner.pack(fill="x", padx=12, pady=10)

        row1 = ttk.Frame(inner, style="Card.TFrame")
        row1.pack(fill="x", pady=(0, 6))

        ttk.Label(row1, text="Language", style="Card.TLabel").pack(side="left")
        self.language_var = tk.StringVar(value="Spanish")
        lang_combo = ttk.Combobox(row1, textvariable=self.language_var, width=14, state="readonly",
                                   values=["Auto-detect", "Spanish", "English", "Portuguese", "French",
                                            "German", "Italian", "Japanese", "Chinese", "Korean"])
        lang_combo.pack(side="left", padx=(8, 24))

        ttk.Label(row1, text="Model", style="Card.TLabel").pack(side="left")
        self.model_var = tk.StringVar(value="large-v3")
        model_combo = ttk.Combobox(row1, textvariable=self.model_var, width=14, state="readonly",
                                    values=["large-v3", "medium", "small", "base", "tiny"])
        model_combo.pack(side="left", padx=(8, 0))

        row2 = ttk.Frame(inner, style="Card.TFrame")
        row2.pack(fill="x")

        ttk.Label(row2, text="Output", style="Card.TLabel").pack(side="left")
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        output_entry = ttk.Entry(row2, textvariable=self.output_var, width=50)
        output_entry.pack(side="left", padx=(8, 6), fill="x", expand=True)
        ttk.Button(row2, text="Browse", style="Small.TButton",
                   command=self._browse_output).pack(side="left")

    def _build_action_bar(self, parent):
        action_frame = ttk.Frame(parent, style="Main.TFrame")
        action_frame.pack(fill="x", pady=(0, 10))

        self.transcribe_btn = tk.Button(
            action_frame, text="TRANSCRIBE", font=("Segoe UI Semibold", 10),
            bg=C["accent"], fg="#13131a", activebackground=C["accent_hover"],
            activeforeground="#13131a", borderwidth=0, cursor="hand2",
            padx=28, pady=9, relief="flat"
        )
        self.transcribe_btn.configure(command=self._toggle_transcription)
        self.transcribe_btn.pack(side="left")

        self.transcribe_btn.bind("<Enter>", lambda e: self.transcribe_btn.configure(bg=C["accent_hover"]))
        self.transcribe_btn.bind("<Leave>", lambda e: self.transcribe_btn.configure(
            bg=C["accent"] if self.transcribe_btn.cget("text") != "CANCELLING..." else C["text_dim"]
        ))

        self.open_btn = ttk.Button(action_frame, text="Open output folder", style="Open.TButton",
                                    command=self._open_output)
        self.open_btn.pack(side="right")

    def _build_progress_area(self, parent):
        progress_frame = ttk.Frame(parent, style="Card.TFrame")
        progress_frame.pack(fill="both", expand=True)

        inner = ttk.Frame(progress_frame, style="Card.TFrame")
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        self.progress_label = ttk.Label(inner, text="Ready", style="Card.TLabel")
        self.progress_label.pack(anchor="w")

        self.progress_bar = ttk.Progressbar(inner, style="Custom.Horizontal.TProgressbar",
                                             mode="determinate", length=400)
        self.progress_bar.pack(fill="x", pady=(6, 8))

        log_frame = tk.Frame(inner, bg=C["log_bg"], highlightbackground=C["border"],
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg=C["log_bg"], fg=C["log_fg"],
                                font=("Cascadia Code", 9), height=6, wrap="word",
                                state="disabled", borderwidth=4, relief="flat",
                                highlightthickness=0, insertbackground=C["accent"],
                                selectbackground=C["accent"], selectforeground=C["text"])
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
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

        self.file_count_label.configure(text=f"Files ({len(self.files)})")

        for path in self.files:
            row = tk.Frame(self.file_inner, bg=C["elevated"])
            row.pack(fill="x", pady=1)

            name = os.path.basename(path)
            ext = os.path.splitext(path)[1].lower()
            is_video = ext in VIDEO_EXTENSIONS
            tag = "VID" if is_video else "AUD"
            color = C["amber"] if is_video else C["green"]

            tag_frame = tk.Frame(row, bg=color, padx=1, pady=0)
            tag_frame.pack(side="left", padx=(6, 6), pady=2)
            tk.Label(tag_frame, text=tag, bg=color, fg=C["bg"],
                     font=("Consolas", 7, "bold")).pack(padx=3)

            tk.Label(row, text=name, bg=C["elevated"], fg=C["text"],
                     font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True)

            remove_btn = tk.Button(row, text="\u00d7", bg=C["elevated"], fg=C["text_dim"],
                                   font=("Segoe UI", 10), borderwidth=0, cursor="hand2",
                                   activebackground=C["elevated"], activeforeground=C["red"],
                                   command=lambda p=path: self._remove_file(p))
            remove_btn.pack(side="right", padx=(0, 8))

    def _toggle_transcription(self):
        if self.is_transcribing:
            self.cancel_requested = True
            self.transcribe_btn.configure(text="CANCELLING...", bg=C["text_dim"],
                                           activebackground=C["text_dim"], state="disabled")
            return

        if not self.files:
            self._log("No files to transcribe. Add some files first.")
            return

        self.is_transcribing = True
        self.cancel_requested = False
        self.transcribe_btn.configure(text="CANCEL", bg=C["red"], activebackground=C["red_hover"])
        threading.Thread(target=self._transcribe_worker, daemon=True).start()

    def _transcribe_worker(self):
        output_dir = self.output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        total = len(self.files)

        try:
            model_name = self.model_var.get()
            self._update_status(f"Loading model '{model_name}'... (first time may download ~1.5 GB)")
            self._set_progress(0)

            if self.model is None or self._loaded_model_name != model_name:
                self.model = WhisperModel(model_name, device="cuda", compute_type="float16")
                self._loaded_model_name = model_name

            self._log(f"Model '{model_name}' loaded on GPU.")

            language = self.language_var.get()
            lang_code = None if language == "Auto-detect" else LANG_MAP.get(language)

            for i, filepath in enumerate(self.files):
                if self.cancel_requested:
                    self._log("Transcription cancelled.")
                    break

                name = os.path.basename(filepath)
                self._update_status(f"[{i + 1}/{total}] Transcribing: {name}")
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
                        self._log(f"  Timed out, skipping...")
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        continue

                    if status == "retry_timed_out":
                        self._log(f"  Retry timed out, skipping...")

                    if self.cancel_requested:
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        break

                    full_text = "\n".join(text_parts)

                    if not full_text.strip():
                        self._log(f"  No speech detected, skipping: {name}")
                        if temp_audio and os.path.exists(temp_audio):
                            os.remove(temp_audio)
                        continue

                    saved_name = save_output(
                        filepath, full_text, output_dir, self.copy_renamed_var.get()
                    )

                    elapsed = time.time() - start_time
                    detected = info.language if language == "Auto-detect" else language
                    self._log(f"  Done in {elapsed:.1f}s | Language: {detected} | Saved: {saved_name}")

                    if temp_audio and os.path.exists(temp_audio):
                        os.remove(temp_audio)

                except Exception as e:
                    self._log(f"  Error: {str(e)}")
                    continue

            if not self.cancel_requested:
                self._set_progress(100)
                self._update_status(f"Finished! {total} file(s) transcribed to: {output_dir}")
                self._log(f"All done. Output: {output_dir}")

        except Exception as e:
            self._log(f"Fatal error: {str(e)}")
            self._update_status("Error occurred. Check log.")

        finally:
            self.is_transcribing = False
            self.cancel_requested = False
            self.root.after(0, lambda: self.transcribe_btn.configure(
                text="TRANSCRIBE", bg=C["accent"], activebackground=C["accent_hover"], state="normal"))

    def _open_output(self):
        output_dir = self.output_var.get()
        os.makedirs(output_dir, exist_ok=True)
        os.startfile(output_dir)

    def _update_status(self, text):
        self.root.after(0, lambda: self.progress_label.configure(text=text))

    def _set_progress(self, value):
        self.root.after(0, lambda: self.progress_bar.configure(value=value))

    def _log(self, text):
        def _append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(0, _append)

    def run(self):
        self.root.mainloop()
