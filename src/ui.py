import os
import re
import time
import threading
import tkinter as tk
from tkinter import filedialog
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
        _s = self.root.winfo_fpixels('1i') / 96.0
        self.root.geometry(f"{int(820 * _s)}x{int(780 * _s)}")
        self.root.minsize(int(700 * _s), int(660 * _s))
        self.root.configure(bg=C["bg"])

        self.files = []
        self.model = None
        self.is_transcribing = False
        self.cancel_requested = False
        self._progress_value = 0

        self.language_var = tk.StringVar(value="Spanish")
        self.model_var = tk.StringVar(value="large-v3")
        self.output_mode_var = tk.StringVar(value="Transcript (.txt)")
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_DIR)

        self._build_ui()
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

    def _dropdown(self, parent, variable, values, width=16):
        outer = tk.Frame(parent, bg=C["entry_bg"], highlightbackground=C["border"],
                         highlightthickness=1, cursor="hand2")

        lbl = tk.Label(outer, textvariable=variable,
                       font=("Segoe UI", 10), bg=C["entry_bg"], fg=C["entry_fg"],
                       anchor="w", width=width, padx=8, pady=4, cursor="hand2")
        lbl.pack(side="left", fill="both", expand=True)

        arrow = tk.Label(outer, text="\u25be", font=("Segoe UI", 11),
                         bg=C["entry_bg"], fg=C["text_sec"], padx=6, cursor="hand2")
        arrow.pack(side="right")

        menu = tk.Menu(outer, tearoff=0, bg=C["surface"], fg=C["text_sec"],
                       activebackground=C["accent"], activeforeground=C["text"],
                       font=("Segoe UI", 10), borderwidth=1, relief="solid")

        for val in values:
            menu.add_command(label=val, command=lambda v=val: variable.set(v))

        def show_menu(e=None):
            menu.post(outer.winfo_rootx(), outer.winfo_rooty() + outer.winfo_height())

        for w in (outer, lbl, arrow):
            w.bind("<Button-1>", show_menu)

        outer.bind("<Enter>", lambda e: outer.configure(highlightbackground=C["accent"]))
        outer.bind("<Leave>", lambda e: outer.configure(highlightbackground=C["border"]))

        return outer

    def _build_ui(self):
        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=24, pady=(12, 18))

        tk.Label(main, text="Whisper Transcriber", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI Semibold", 18), anchor="w").pack(fill="x")
        tk.Label(main, text="Drag & drop audio/video files to transcribe them locally using AI",
                 bg=C["bg"], fg=C["text_dim"], font=("Segoe UI", 9), anchor="w"
                 ).pack(fill="x", pady=(2, 14))

        self._build_drop_zone(main)
        self._build_file_list(main)
        self._build_settings(main)
        self._build_action_bar(main)
        self._build_progress(main)

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
        list_frame = tk.Frame(parent, bg=C["elevated"])
        list_frame.pack(fill="both", expand=True, pady=(0, 10))

        header = tk.Frame(list_frame, bg=C["elevated"])
        header.pack(fill="x", padx=12, pady=(8, 0))
        self.file_count_label = tk.Label(header, text="Files (0)", bg=C["elevated"],
                                          fg=C["text"], font=("Segoe UI Semibold", 10))
        self.file_count_label.pack(side="left")

        clear_btn = tk.Button(header, text="Clear all", font=("Segoe UI", 9),
                              bg=C["surface"], fg=C["text_sec"],
                              activebackground=C["border"], activeforeground=C["text"],
                              borderwidth=0, relief="flat", cursor="hand2",
                              padx=12, pady=5, command=self._clear_files)
        clear_btn.pack(side="right")

        canvas_frame = tk.Frame(list_frame, bg=C["elevated"])
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.file_canvas = tk.Canvas(canvas_frame, bg=C["elevated"], highlightthickness=0, height=120)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.file_canvas.yview,
                                 bg=C["surface"], troughcolor=C["elevated"],
                                 activebackground=C["border"], width=14,
                                 highlightthickness=0, bd=0)
        self.file_inner = tk.Frame(self.file_canvas, bg=C["elevated"])

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
        settings = tk.Frame(parent, bg=C["elevated"])
        settings.pack(fill="x", pady=(0, 10))

        inner = tk.Frame(settings, bg=C["elevated"])
        inner.pack(fill="x", padx=12, pady=10)

        row1 = tk.Frame(inner, bg=C["elevated"])
        row1.pack(fill="x", pady=(0, 6))

        tk.Label(row1, text="Language", bg=C["elevated"], fg=C["text_sec"],
                 font=("Segoe UI", 10)).pack(side="left")
        self._dropdown(row1, self.language_var,
                       ["Auto-detect", "Spanish", "English", "Portuguese", "French",
                        "German", "Italian", "Japanese", "Chinese", "Korean"],
                       width=14).pack(side="left", padx=(8, 24))

        tk.Label(row1, text="Model", bg=C["elevated"], fg=C["text_sec"],
                 font=("Segoe UI", 10)).pack(side="left")
        self._dropdown(row1, self.model_var,
                       ["large-v3", "medium", "small", "base", "tiny"],
                       width=14).pack(side="left", padx=(8, 0))

        row2 = tk.Frame(inner, bg=C["elevated"])
        row2.pack(fill="x", pady=(0, 6))

        tk.Label(row2, text="Output format", bg=C["elevated"], fg=C["text_sec"],
                 font=("Segoe UI", 10)).pack(side="left")
        self._dropdown(row2, self.output_mode_var,
                       ["Transcript (.txt)", "Rename source by transcript"],
                       width=28).pack(side="left", padx=(8, 0))

        row3 = tk.Frame(inner, bg=C["elevated"])
        row3.pack(fill="x")

        tk.Label(row3, text="Output path", bg=C["elevated"], fg=C["text_sec"],
                 font=("Segoe UI", 10)).pack(side="left")
        output_entry = tk.Entry(row3, textvariable=self.output_var, font=("Segoe UI", 10),
                                bg=C["entry_bg"], fg=C["entry_fg"], insertbackground=C["accent"],
                                relief="flat", highlightbackground=C["border"], highlightthickness=1)
        output_entry.pack(side="left", padx=(8, 6), fill="x", expand=True, ipady=4)
        browse_btn = tk.Button(row3, text="Browse", font=("Segoe UI", 9),
                               bg=C["surface"], fg=C["text_sec"],
                               activebackground=C["border"], activeforeground=C["text"],
                               borderwidth=0, relief="flat", cursor="hand2",
                               padx=12, pady=5, command=self._browse_output)
        browse_btn.pack(side="left")

    def _build_action_bar(self, parent):
        action = tk.Frame(parent, bg=C["bg"])
        action.pack(fill="x", pady=(0, 10))

        self.transcribe_btn = tk.Button(
            action, text="TRANSCRIBE", font=("Segoe UI Semibold", 11),
            bg=C["accent"], fg="#13131a", activebackground=C["accent_hover"],
            activeforeground="#13131a", borderwidth=0, cursor="hand2",
            padx=30, pady=10, relief="flat"
        )
        self.transcribe_btn.configure(command=self._toggle_transcription)
        self.transcribe_btn.pack(side="left")

        def _btn_enter(e):
            text = self.transcribe_btn.cget("text")
            if text == "TRANSCRIBE":
                self.transcribe_btn.configure(bg=C["accent_hover"])
            elif text == "CANCEL":
                self.transcribe_btn.configure(bg=C["red_hover"])

        def _btn_leave(e):
            text = self.transcribe_btn.cget("text")
            if text == "TRANSCRIBE":
                self.transcribe_btn.configure(bg=C["accent"])
            elif text == "CANCEL":
                self.transcribe_btn.configure(bg=C["red"])

        self.transcribe_btn.bind("<Enter>", _btn_enter)
        self.transcribe_btn.bind("<Leave>", _btn_leave)

        open_btn = tk.Button(action, text="Open output folder", font=("Segoe UI", 9),
                             bg=C["surface"], fg=C["text_sec"],
                             activebackground=C["border"], activeforeground=C["text"],
                             borderwidth=0, relief="flat", cursor="hand2",
                             padx=14, pady=8, command=self._open_output)
        open_btn.pack(side="right")

    def _build_progress(self, parent):
        prog_frame = tk.Frame(parent, bg=C["elevated"])
        prog_frame.pack(fill="both", expand=True)

        inner = tk.Frame(prog_frame, bg=C["elevated"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)

        self.progress_label = tk.Label(inner, text="Ready", bg=C["elevated"],
                                        fg=C["text_sec"], font=("Segoe UI", 9), anchor="w")
        self.progress_label.pack(fill="x")

        self.progress_canvas = tk.Canvas(inner, bg=C["surface"], highlightthickness=0, height=6)
        self.progress_canvas.pack(fill="x", pady=(6, 8))
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress())

        log_frame = tk.Frame(inner, bg=C["log_bg"], highlightbackground=C["border"],
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, bg=C["log_bg"], fg=C["log_fg"],
                                font=("Cascadia Code", 9), height=6, wrap="word",
                                state="disabled", borderwidth=4, relief="flat",
                                highlightthickness=0, insertbackground=C["accent"],
                                selectbackground=C["accent"], selectforeground=C["text"])
        log_scroll = tk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview,
                                  bg=C["surface"], troughcolor=C["log_bg"],
                                  activebackground=C["border"], width=14,
                                  highlightthickness=0, bd=0)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _draw_progress(self):
        c = self.progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 4:
            return
        c.create_rectangle(0, 0, w, h, fill=C["surface"], outline="")
        if self._progress_value > 0:
            fill_w = max(2, int(w * self._progress_value / 100))
            c.create_rectangle(0, 0, fill_w, h, fill=C["accent"], outline="")

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
            tag_frame.pack(side="left", padx=(8, 8), pady=3)
            tk.Label(tag_frame, text=tag, bg=color, fg=C["bg"],
                     font=("Consolas", 8, "bold")).pack(padx=4)

            tk.Label(row, text=name, bg=C["elevated"], fg=C["text"],
                     font=("Segoe UI", 10), anchor="w").pack(side="left", fill="x", expand=True)

            remove_btn = tk.Button(row, text="\u00d7", bg=C["elevated"], fg=C["text_dim"],
                                   font=("Segoe UI", 14), borderwidth=0, cursor="hand2",
                                   activebackground=C["elevated"], activeforeground=C["red"],
                                   padx=6, pady=2,
                                   command=lambda p=path: self._remove_file(p))
            remove_btn.pack(side="right", padx=(0, 10))

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

                    copy_renamed = self.output_mode_var.get() != "Transcript (.txt)"
                    saved_name = save_output(
                        filepath, full_text, output_dir, copy_renamed
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
        self._progress_value = value
        def _update():
            self._draw_progress()
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
