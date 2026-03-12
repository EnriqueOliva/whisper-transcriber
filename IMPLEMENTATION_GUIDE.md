# Whisper Transcriber — Complete Implementation Guide

This document contains everything needed to recreate the Whisper Transcriber app from scratch on a Windows machine. It is written for an LLM or developer who needs to reproduce the entire project without any prior context.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Target System Requirements](#2-target-system-requirements)
3. [Architecture Decisions and Why](#3-architecture-decisions-and-why)
4. [File Structure](#4-file-structure)
5. [Step-by-Step Build Instructions](#5-step-by-step-build-instructions)
6. [File-by-File Implementation](#6-file-by-file-implementation)
7. [Critical Technical Details](#7-critical-technical-details)
8. [Known Issues and Solutions](#8-known-issues-and-solutions)
9. [Testing Procedures](#9-testing-procedures)
10. [Appendix: Complete Source Code](#10-appendix-complete-source-code)

---

## 1. Overview

**What this app does:** A Windows desktop GUI application that transcribes audio and video files to text using OpenAI's Whisper speech recognition model, running entirely locally on the user's GPU.

**Core workflow:**
1. User drags/drops audio or video files onto the app window
2. Video files have their audio extracted via FFmpeg
3. Audio is fed to faster-whisper (a CTranslate2-based Whisper implementation)
4. Transcribed text is saved as `.txt` files in an output folder
5. Optional: instead of `.txt`, the app can copy the original source file renamed with the transcript as its filename

**Key technology choices:**
- **faster-whisper** instead of openai-whisper — 2-4x faster, uses ~60% less VRAM, same model accuracy
- **uv** instead of global Python — manages Python versions per-project, no system pollution
- **tkinter + tkinterdnd2** for GUI — ships with Python, no extra framework needed, tkinterdnd2 adds native drag-and-drop
- **VBScript launchers** instead of .bat/.exe — launches silently with no console window, can self-elevate to admin for setup

---

## 2. Target System Requirements

- **OS:** Windows 10 or 11
- **GPU:** Any NVIDIA GPU with updated drivers (tested on RTX 4070 12GB)
- **RAM:** 8+ GB system RAM
- **Disk:** ~4 GB free (1.2 GB for .venv, 1.5 GB for model cache, rest for FFmpeg and tools)
- **Internet:** Required only during setup and first model download

### Pre-existing software that may or may not be present

The setup script checks for and installs if missing:
- `uv` (Python version/package manager)
- `FFmpeg` (audio/video processing)

The setup script requires one of these to install FFmpeg:
- `winget` (ships with Windows 11, usually present on Windows 10)
- `chocolatey` (fallback)

---

## 3. Architecture Decisions and Why

### Why faster-whisper over openai-whisper

openai-whisper requires PyTorch (~2.5 GB) and uses more VRAM. faster-whisper uses CTranslate2 which:
- Bundles its own CUDA runtime (no PyTorch needed)
- Runs the same Whisper models 2-4x faster
- Uses ~4 GB VRAM for large-v3 vs ~10 GB with openai-whisper
- Supports the same 99+ languages and all model sizes

The only thing faster-whisper doesn't support is OpenAI's `turbo` model variant, but `large-v3` on faster-whisper is both faster and more accurate than `turbo` on openai-whisper.

### Why uv over global Python

- No system-wide Python installation needed
- Each project gets its own isolated Python version and virtual environment
- Works like nvm for Node.js — installs Python to `~/.local/share/uv/python/`
- The user may have multiple projects needing different Python versions in the future

### Why tkinter over Electron/PyQt/etc.

- Ships with Python — zero extra dependencies for the GUI framework itself
- Small footprint — the entire GUI is one file (~480 lines)
- tkinterdnd2 adds native Windows drag-and-drop support
- Sufficient for this use case (form controls, list, progress bar, text log)

### Why VBScript for launchers

- `.bat` files flash a console window even when launching a GUI app — unacceptable for daily use
- `.vbs` files run silently via `wscript.exe` — no console window at all
- VBScript can self-elevate to admin via `Shell.Application.ShellExecute "runas"` — needed for setup
- The `.vbs` files are tiny (~10 lines each) and just set environment variables then launch Python

### Why NVIDIA pip packages instead of CUDA Toolkit

The `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` pip packages bundle the required CUDA runtime DLLs directly inside the virtual environment. This means:
- No system-wide CUDA Toolkit installation needed
- No manual cuDNN download and path configuration
- Everything stays contained in the `.venv` folder
- The only system requirement is NVIDIA GPU drivers (which Windows installs automatically)

**Critical caveat:** The DLLs installed by these pip packages are NOT automatically found by CTranslate2. You must add their directories to the system PATH before importing faster-whisper. This is done in two places:
1. `main.py` — adds the paths via `os.environ["PATH"]` before any imports
2. `launch.vbs` — adds the paths via `shell.Environment("Process")("PATH")` before launching Python

Both are necessary. The VBS PATH setup ensures the DLLs are found by the process. The Python PATH setup is a belt-and-suspenders approach.

---

## 4. File Structure

```
whisper-transcriber/
├── launch.vbs              # Silent app launcher
├── README.md               # Project documentation
├── IMPLEMENTATION_GUIDE.md # This file
├── setup/
│   ├── setup.vbs           # Admin-elevating setup launcher
│   └── setup.ps1           # Automated installer script
├── src/
│   ├── main.py             # Entry point: CUDA path setup → launch UI
│   ├── ui.py               # TranscriberApp class: full GUI
│   ├── engine.py           # Transcription engine: whisper, ffmpeg, file ops
│   └── constants.py        # All constants: colors, extensions, paths, config
├── output/                 # Default output directory (auto-created)
└── .venv/                  # Python 3.11 virtual environment (created by setup)
```

### How paths resolve

All Python files compute paths relative to their own location:
- `constants.py` computes `PROJECT_ROOT` as two levels up from itself (`src/constants.py` → `src/` → project root)
- `main.py` computes `VENV_DIR` the same way
- `launch.vbs` uses `fso.GetParentFolderName(WScript.ScriptFullName)` to find its own directory (the project root)
- `setup.ps1` uses `Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)` — two levels up from `setup/setup.ps1` to reach the project root

This means the entire folder can be placed anywhere on the filesystem and everything still works.

---

## 5. Step-by-Step Build Instructions

These are the exact commands to run in order, assuming a fresh Windows 11 machine with an NVIDIA GPU.

### Step 1: Install uv

```powershell
# In PowerShell (admin not required)
irm https://astral.sh/uv/install.ps1 | iex
```

This installs `uv` to `~/.local/bin/`. Restart the terminal after installation.

### Step 2: Install FFmpeg

```powershell
# In PowerShell (admin may be required)
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
```

Restart the terminal after installation so FFmpeg is in PATH.

### Step 3: Create the project directory

```powershell
mkdir whisper-transcriber
mkdir whisper-transcriber/src
mkdir whisper-transcriber/setup
mkdir whisper-transcriber/output
cd whisper-transcriber
```

### Step 4: Install Python 3.11 and create virtual environment

```powershell
uv python install 3.11
uv venv --python 3.11
```

This creates a `.venv/` folder in the current directory with Python 3.11.

### Step 5: Install Python dependencies

```powershell
uv pip install faster-whisper tkinterdnd2 nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Package purposes:
- `faster-whisper` — Whisper inference engine (pulls in ctranslate2, av, tokenizers, huggingface-hub)
- `tkinterdnd2` — drag-and-drop support for tkinter
- `nvidia-cublas-cu12` — CUDA Basic Linear Algebra Subroutines (~528 MB)
- `nvidia-cudnn-cu12` — CUDA Deep Neural Network library (~614 MB)

### Step 6: Create all source files

Create each file as specified in [Section 6](#6-file-by-file-implementation) or copy them from the [Appendix](#10-appendix-complete-source-code).

### Step 7: Verify the installation

```powershell
# Test CUDA detection
.venv/Scripts/python.exe -c "import ctranslate2; print('CUDA devices:', ctranslate2.get_cuda_device_count())"

# Test app launch (set PATH for CUDA DLLs first)
$env:PATH = ".venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;$env:PATH"
.venv/Scripts/python.exe src/main.py
```

The app window should appear. Close it manually.

### Step 8: First transcription (downloads model)

The first time you transcribe a file, faster-whisper downloads the selected model from Hugging Face. For `large-v3`, this is ~1.5 GB. The model is cached at `~/.cache/huggingface/hub/models--Systran--faster-whisper-large-v3/`. After this one-time download, the app works fully offline.

---

## 6. File-by-File Implementation

### 6.1 `src/constants.py`

**Purpose:** Centralized configuration. All magic numbers, color values, file extensions, and paths live here.

**Key details:**
- `PROJECT_ROOT` is computed dynamically from the file's own location — never hardcoded
- `C` is the color palette dictionary used by the entire UI — warm dark theme with amber accents
- `SUPPORTED_EXTENSIONS` includes both audio and video formats
- `VIDEO_EXTENSIONS` is the subset that requires FFmpeg audio extraction
- `LANG_MAP` converts display names ("Spanish") to ISO codes ("es") for faster-whisper
- `INVALID_FILENAME_CHARS` regex matches all characters illegal in Windows filenames
- `MAX_FILENAME_LEN` is 120 (Windows max is 255, but 120 leaves room for path + counter suffix)

### 6.2 `src/engine.py`

**Purpose:** All transcription and file processing logic, decoupled from the UI.

**Functions:**

#### `sanitize_filename(text) → str`
Strips illegal Windows filename characters, trims dots/spaces, truncates at `MAX_FILENAME_LEN` on a word boundary. Returns "untitled" if the result is empty.

#### `unique_path(directory, base_name, ext) → str`
Returns a non-colliding file path. If `base_name.ext` exists, tries `base_name (2).ext`, `base_name (3).ext`, etc.

#### `extract_audio(filepath, output_dir) → str`
Extracts audio from a video file using FFmpeg. Outputs a 16kHz mono WAV (the format Whisper expects). Uses `subprocess.CREATE_NO_WINDOW` to prevent a console flash on Windows. Returns the path to the temporary WAV file. Raises `RuntimeError` on FFmpeg failure.

**FFmpeg command:** `ffmpeg -y -i <input> -vn -acodec pcm_s16le -ar 16000 -ac 1 <output.wav>`
- `-y` — overwrite without asking
- `-vn` — no video
- `-acodec pcm_s16le` — 16-bit PCM (uncompressed)
- `-ar 16000` — 16kHz sample rate
- `-ac 1` — mono

#### `transcribe_audio(model, audio_path, lang_code, on_progress, is_cancelled) → (text_parts, info, status)`

The core transcription function. Uses a two-pass strategy:

**Pass 1:** Transcribe with VAD (Voice Activity Detection) enabled.
- `vad_filter=True` with `min_silence_duration_ms=500`
- VAD skips silent portions, making transcription faster and cleaner
- Timeout: `max(30 seconds, audio_duration * 5)` — prevents hanging on corrupt/noisy files

**Pass 2 (fallback):** If Pass 1 returns empty text, retry WITHOUT VAD.
- `vad_filter=False, condition_on_previous_text=False`
- `condition_on_previous_text=False` prevents hallucination loops on noisy audio
- Shorter timeout: `max(15 seconds, audio_duration * 3)`
- This catches short clips where VAD incorrectly classifies all audio as non-speech

**Return value:** Tuple of `(text_parts: list[str], info: TranscriptionInfo, status: str)`
- `status` is one of: `"ok"`, `"timed_out"`, `"retry_timed_out"`
- The caller decides what to do based on status

**Callbacks:**
- `on_progress(segment_end, duration)` — called after each segment, used for progress bar
- `is_cancelled()` — callable returning bool, checked between segments

#### `save_output(filepath, full_text, output_dir, copy_renamed) → str`

Two modes:
- **Normal mode** (`copy_renamed=False`): Writes a `.txt` file with the transcript, named after the source file
- **Rename mode** (`copy_renamed=True`): Copies the original source file to the output folder with the transcript as its filename, preserving the original extension. Uses `shutil.copy2` (preserves metadata).

Returns the basename of the saved file (for logging).

### 6.3 `src/ui.py`

**Purpose:** The complete GUI application — window, widgets, styles, event handlers, and the transcription orchestrator.

**Class: `TranscriberApp`**

#### Initialization
- Creates a `tkinterdnd2.Tk()` root window (not regular `tk.Tk()` — needed for drag-and-drop)
- Window size: 740x720, minimum 640x620
- Uses the `clam` ttk theme (best theme for custom styling on Windows)
- Initializes state variables: `files` list, `model` (lazy-loaded), `is_transcribing`, `cancel_requested`

#### UI Structure (top to bottom)
1. **Menu bar** — Settings > Special features > "Copy source file renamed by transcript content"
2. **Title** — "Whisper Transcriber" with subtitle
3. **Drop zone** — Click or drag-and-drop area. Highlights amber on hover.
4. **File list** — Scrollable canvas with VID/AUD tags, filename, and remove (x) button per file
5. **Settings card** — Language dropdown, Model dropdown, Output path with Browse button
6. **Action bar** — TRANSCRIBE button (amber, turns red when cancellable) + Open output folder button
7. **Progress area** — Status label, progress bar, scrollable log text

#### Drag-and-Drop Implementation
tkinterdnd2 wraps the Tk DnD extension. Drop events deliver file paths in a specific format:
- Single file: `C:/path/to/file.mp3`
- File with spaces: `{C:/path/to/my file.mp3}`
- Multiple files: space-separated, each potentially braced

The `_on_drop` method parses this with a regex: `r'\{([^}]+)\}|(\S+)'`

#### Transcription Orchestrator (`_transcribe_worker`)
Runs in a daemon thread to keep the UI responsive. Flow:

1. Load/cache the WhisperModel (lazy — only loads when model name changes)
2. Resolve language code from the dropdown selection
3. For each file:
   a. If video extension → call `extract_audio()` for FFmpeg extraction
   b. Call `transcribe_audio()` with progress and cancel callbacks
   c. Handle status: skip on timeout, break on cancel
   d. If no speech detected → skip
   e. Call `save_output()` in normal or rename mode
   f. Clean up temp audio file if created
   g. Log result with elapsed time
4. Update progress to 100% and show completion message
5. In `finally` block: reset button state regardless of success/failure

#### Thread Safety
All UI updates from the worker thread go through `self.root.after(0, callback)` which schedules the callback on tkinter's main thread. Direct widget manipulation from a non-main thread would crash tkinter.

#### Button State Machine
- Idle: "TRANSCRIBE" (amber)
- Transcribing: "CANCEL" (red)
- Cancel requested: "CANCELLING..." (gray, disabled)
- After completion: resets to "TRANSCRIBE" (amber)

### 6.4 `src/main.py`

**Purpose:** Entry point. Handles two critical setup tasks before the app launches:

1. **Suppresses Hugging Face symlink warning** — `HF_HUB_DISABLE_SYMLINKS_WARNING=1`. Without this, every model load prints a warning about Windows Developer Mode not being enabled. Cosmetic but annoying.

2. **Adds NVIDIA DLL directories to PATH** — The `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` pip packages install their DLLs to `.venv/Lib/site-packages/nvidia/{cublas,cudnn}/bin/`. CTranslate2 loads these DLLs at runtime via the system PATH. Without this step, transcription fails with `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`.

**Why this is in main.py and not constants.py:** The PATH modification must happen before `from faster_whisper import WhisperModel` is executed anywhere. Since `ui.py` imports from `faster_whisper` at module level, and `main.py` imports `ui.py`, the PATH setup must be complete before the `from ui import TranscriberApp` line in `main.py`.

### 6.5 `launch.vbs`

**Purpose:** Silent launcher for daily use. Double-click to open the app with no console window.

**How it works:**
1. Gets its own directory path
2. Sets the current directory to the project root
3. Prepends the NVIDIA DLL paths to the process-level PATH environment variable
4. Runs `.venv\Scripts\pythonw.exe src\main.py` with window style `0` (hidden — no console)

**Why `pythonw.exe` instead of `python.exe`:** `pythonw.exe` is the "windowless" Python interpreter. It doesn't create a console window. Combined with the VBScript's hidden window style, the only visible window is the tkinter GUI.

**Why PATH is set in both VBS and Python:** Belt and suspenders. The VBS sets it at the process level (before Python starts), and `main.py` sets it at the Python level (in case the VBS PATH didn't propagate correctly). Both are needed for reliable CUDA DLL loading.

### 6.6 `setup/setup.vbs`

**Purpose:** Requests admin elevation and launches the PowerShell setup script.

**How admin elevation works:**
1. First run: the script checks for a `/elevated:1` argument — not present on first run
2. Calls `Shell.Application.ShellExecute` with the `"runas"` verb, passing itself with the `/elevated:1` flag
3. Windows shows the UAC (User Account Control) prompt
4. If approved, the script runs again — this time with `/elevated:1` present, so it proceeds
5. Launches PowerShell with `-ExecutionPolicy Bypass` to run `setup.ps1`

**Why admin is needed:** Installing uv and FFmpeg via winget/choco requires admin rights for system-wide installation.

### 6.7 `setup/setup.ps1`

**Purpose:** Automated installer that sets up all dependencies.

**Flow (5 steps):**

1. **Check/install uv** — Checks if `uv` command exists. If not, downloads and runs the official installer from `astral.sh`. Adds `~/.local/bin` to PATH for the current session.

2. **Check/install FFmpeg** — Checks if `ffmpeg` command exists. If not, tries `winget install --id Gyan.FFmpeg`, falls back to `choco install ffmpeg`.

3. **Install Python 3.11** — Runs `uv python install 3.11`. uv downloads CPython to its managed cache. This is NOT a global system installation.

4. **Create virtual environment** — Runs `uv venv --python 3.11` in the project root. If `.venv` already exists, deletes and recreates it. The venv contains a Python interpreter and an isolated package directory.

5. **Install Python packages** — Runs `uv pip install faster-whisper tkinterdnd2 nvidia-cublas-cu12 nvidia-cudnn-cu12` inside the venv. Total download: ~1.2 GB (CUDA libraries are the bulk).

**Path resolution:** `$projectRoot` is computed as two levels up from the script's own location (`setup/setup.ps1` → `setup/` → project root). This is where the `.venv` gets created.

**Error handling:** Each step is wrapped in try/catch. On failure, shows the error in red and exits with code 1. The `Read-Host` at the end keeps the window open so the user can read the output.

---

## 7. Critical Technical Details

### CUDA DLL Loading (the #1 gotcha)

The `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` packages install DLLs to:
```
.venv/Lib/site-packages/nvidia/cublas/bin/cublas64_12.dll
.venv/Lib/site-packages/nvidia/cublas/bin/cublasLt64_12.dll
.venv/Lib/site-packages/nvidia/cudnn/bin/cudnn64_9.dll
(and several more cudnn DLLs)
```

CTranslate2 loads these at runtime using the standard Windows DLL search path. They are NOT in the default PATH. You must add these directories to PATH **before** CTranslate2 tries to use them.

The model loads fine without the DLLs (it's just loading weights into memory). The crash happens when you actually try to **transcribe** — that's when CTranslate2 calls into cuBLAS/cuDNN.

Symptoms of missing DLLs: `RuntimeError: Library cublas64_12.dll is not found or cannot be loaded`

### VAD (Voice Activity Detection) on Short Clips

faster-whisper's VAD filter (powered by Silero VAD) analyzes audio to detect speech segments and only transcribes those. This works great for long recordings but can misclassify short clips (< 5 seconds) as non-speech, especially if:
- The audio has background noise
- The speech doesn't start at the very beginning
- The audio is low quality

Solution implemented: Try with VAD first, then retry without if empty. The retry also uses `condition_on_previous_text=False` to prevent the model from entering a hallucination loop where it generates repetitive text on noisy audio.

### Timeout Protection

Whisper can sometimes hang indefinitely on problematic audio — corrupt files, extreme noise, or unusual encoding. The `transcribe_audio` function implements per-file timeouts:
- First pass: `max(30s, duration * 5)` — generous but bounded
- Retry pass: `max(15s, duration * 3)` — shorter since we already tried once

The timeout checks happen between segments (not mid-segment), so a single very long segment could still block. In practice, segments are typically 1-10 seconds long.

### Windows-Specific Code

Three places in the codebase are Windows-only:
1. `subprocess.CREATE_NO_WINDOW` in `engine.py` — prevents FFmpeg from flashing a console window. This flag doesn't exist on macOS/Linux.
2. `os.startfile(output_dir)` in `ui.py` — opens a folder in Windows Explorer. macOS equivalent is `subprocess.run(["open", path])`, Linux is `subprocess.run(["xdg-open", path])`.
3. NVIDIA DLL path setup in `main.py` — the `.dll` paths are Windows-specific. Linux uses `.so` files with different loading mechanisms.

### Model Caching

faster-whisper downloads models from Hugging Face Hub to `~/.cache/huggingface/hub/`. The exact path for large-v3 is:
```
C:\Users\<username>\.cache\huggingface\hub\models--Systran--faster-whisper-large-v3\
```

This cache is shared across all Python environments and projects. If the user sets up a second instance of this app, it will reuse the cached model.

### Thread Model

The app uses two threads:
1. **Main thread** — tkinter event loop (all UI rendering and interaction)
2. **Worker thread** — transcription (spawned per batch, daemon=True so it dies when the app closes)

All communication from worker → UI goes through `root.after(0, callback)`. The `cancel_requested` flag is the only communication from UI → worker, and it's a simple boolean read (thread-safe in Python due to the GIL).

---

## 8. Known Issues and Solutions

### Issue: Empty .txt files for short audio clips
**Cause:** VAD filters out the entire audio as non-speech.
**Solution:** Already implemented — automatic retry without VAD.

### Issue: App hangs on noisy audio files
**Cause:** Whisper enters a decode loop producing garbage text.
**Solution:** Already implemented — timeout kills the loop and skips the file.

### Issue: Hugging Face symlink warning on every model load
**Cause:** Windows Developer Mode not enabled — HF Hub can't use symlinks for caching.
**Solution:** `os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"` in main.py. The caching still works, just uses copies instead of symlinks (slightly more disk space).

### Issue: "Library cublas64_12.dll is not found"
**Cause:** NVIDIA DLL directories not in PATH.
**Solution:** Ensure both `launch.vbs` and `main.py` add the paths (see Section 7).

### Issue: The .venv folder can't be moved/copied to another machine
**Cause:** Virtual environments contain hardcoded absolute paths in their configuration files.
**Solution:** Always create a fresh venv on each machine using the setup script.

---

## 9. Testing Procedures

### Test 1: CUDA Detection
```powershell
.venv/Scripts/python.exe -c "import ctranslate2; print('CUDA:', ctranslate2.get_cuda_device_count())"
```
Expected: `CUDA: 1` (or more)

### Test 2: CUDA DLL Loading
```powershell
$env:PATH = ".venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;$env:PATH"
.venv/Scripts/python.exe -c "
from faster_whisper import WhisperModel
m = WhisperModel('tiny', device='cuda', compute_type='float16')
print('Model loaded on GPU')
"
```
Expected: `Model loaded on GPU` (first run downloads ~75 MB tiny model)

### Test 3: End-to-End Transcription
Generate a test audio file with FFmpeg's built-in TTS, then transcribe it:
```powershell
ffmpeg -y -f lavfi -i "flite=text='Hello world test':voice=kal16" -ar 16000 -ac 1 test.wav
$env:PATH = ".venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;$env:PATH"
.venv/Scripts/python.exe -c "
from faster_whisper import WhisperModel
m = WhisperModel('tiny', device='cuda', compute_type='float16')
segs, info = m.transcribe('test.wav', vad_filter=False)
print([s.text.strip() for s in segs])
"
```
Expected: A list containing text similar to the input (tiny model is imprecise, but should produce something).

### Test 4: GUI Launch
```powershell
$env:PATH = ".venv\Lib\site-packages\nvidia\cublas\bin;.venv\Lib\site-packages\nvidia\cudnn\bin;$env:PATH"
.venv/Scripts/python.exe src/main.py
```
Expected: App window appears with all UI elements. Close manually.

### Test 5: Silent Launch via VBScript
Double-click `launch.vbs`. Expected: Only the app window appears, no console window.

---

## 10. Appendix: Complete Source Code

All source files are reproduced below in full. To recreate the project, create the directory structure from Section 4 and write each file with the content shown.

### `src/constants.py`

```python
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".wma", ".aac",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".ts", ".flv",
}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".wmv", ".ts", ".flv"}

MAX_FILENAME_LEN = 120
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

LANG_MAP = {
    "Spanish": "es", "English": "en", "Portuguese": "pt", "French": "fr",
    "German": "de", "Italian": "it", "Japanese": "ja", "Chinese": "zh", "Korean": "ko",
}

C = {
    "bg":           "#13131a",
    "elevated":     "#1b1b26",
    "surface":      "#232330",
    "border":       "#2c2c3a",
    "border_hover": "#d4943a",
    "text":         "#e8e2da",
    "text_sec":     "#9490a0",
    "text_dim":     "#5c586a",
    "accent":       "#d4943a",
    "accent_hover": "#e8b050",
    "accent_press": "#b07828",
    "green":        "#7ec4a0",
    "amber":        "#c4a06c",
    "red":          "#c07070",
    "red_hover":    "#e08080",
    "log_bg":       "#111118",
    "log_fg":       "#8a8694",
    "entry_bg":     "#18181f",
    "entry_fg":     "#d0ccc4",
}
```

### `src/engine.py`

```python
import os
import subprocess
import time
import shutil

from constants import VIDEO_EXTENSIONS, INVALID_FILENAME_CHARS, MAX_FILENAME_LEN


def sanitize_filename(text):
    name = INVALID_FILENAME_CHARS.sub("", text)
    name = name.strip(". ")
    if len(name) > MAX_FILENAME_LEN:
        name = name[:MAX_FILENAME_LEN].rsplit(" ", 1)[0].strip(". ")
    return name or "untitled"


def unique_path(directory, base_name, ext):
    candidate = os.path.join(directory, base_name + ext)
    if not os.path.exists(candidate):
        return candidate
    counter = 2
    while True:
        candidate = os.path.join(directory, f"{base_name} ({counter}){ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def extract_audio(filepath, output_dir):
    name = os.path.basename(filepath)
    temp_audio = os.path.join(output_dir, f"_temp_{os.path.splitext(name)[0]}.wav")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", filepath, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", temp_audio],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
    )
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg error: {result.stderr[:200]}")
    return temp_audio


def transcribe_audio(model, audio_path, lang_code, on_progress=None, is_cancelled=None):
    start_time = time.time()

    segments, info = model.transcribe(
        audio_path, language=lang_code, beam_size=5,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
    )

    duration = info.duration
    max_time = max(30, duration * 5)
    text_parts = []
    timed_out = False

    for segment in segments:
        if is_cancelled and is_cancelled():
            break
        if time.time() - start_time > max_time:
            timed_out = True
            break
        text_parts.append(segment.text.strip())
        if on_progress and duration > 0:
            on_progress(segment.end, duration)

    if timed_out:
        return text_parts, info, "timed_out"

    if not text_parts and not (is_cancelled and is_cancelled()):
        retry_start = time.time()
        retry_max = max(15, duration * 3)
        segments, info = model.transcribe(
            audio_path, language=lang_code, beam_size=5,
            vad_filter=False, condition_on_previous_text=False
        )
        for segment in segments:
            if is_cancelled and is_cancelled():
                break
            if time.time() - retry_start > retry_max:
                return text_parts, info, "retry_timed_out"
            text_parts.append(segment.text.strip())
            if on_progress and duration > 0:
                on_progress(segment.end, duration)

    return text_parts, info, "ok"


def save_output(filepath, full_text, output_dir, copy_renamed):
    name = os.path.basename(filepath)
    if copy_renamed and full_text.strip():
        source_ext = os.path.splitext(filepath)[1]
        renamed_base = sanitize_filename(full_text.replace("\n", " "))
        renamed_path = unique_path(output_dir, renamed_base, source_ext)
        shutil.copy2(filepath, renamed_path)
        return os.path.basename(renamed_path)
    else:
        source_base = os.path.splitext(name)[0]
        out_path = os.path.join(output_dir, source_base + ".txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        return os.path.basename(out_path)
```

### `src/ui.py`

```python
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

    # ... (all remaining UI builder methods, event handlers, and _transcribe_worker)
    # See the full ui.py source file for the complete implementation.

    def run(self):
        self.root.mainloop()
```

> **Note:** The full `ui.py` is ~479 lines. The complete file is in the `src/` directory. The appendix above shows the structure; refer to the actual file for the complete implementation of all UI builder methods and event handlers.

### `src/main.py`

```python
import os
import sys

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SRC_DIR)
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")

_nvidia_dirs = [
    os.path.join(VENV_DIR, "Lib", "site-packages", "nvidia", "cublas", "bin"),
    os.path.join(VENV_DIR, "Lib", "site-packages", "nvidia", "cudnn", "bin"),
]
for _d in _nvidia_dirs:
    if os.path.isdir(_d) and _d not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

from ui import TranscriberApp


if __name__ == "__main__":
    app = TranscriberApp()
    app.run()
```

### `launch.vbs`

```vbscript
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = baseDir

env = "PATH"
nvidiaPath = baseDir & "\.venv\Lib\site-packages\nvidia\cublas\bin;" & baseDir & "\.venv\Lib\site-packages\nvidia\cudnn\bin;"
shell.Environment("Process")(env) = nvidiaPath & shell.Environment("Process")(env)

shell.Run """" & baseDir & "\.venv\Scripts\pythonw.exe"" """ & baseDir & "\src\main.py""", 0, False
```

### `setup/setup.vbs`

```vbscript
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("Shell.Application")
Set wshShell = CreateObject("WScript.Shell")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
psScript = baseDir & "\setup.ps1"

If Not fso.FileExists(psScript) Then
    MsgBox "setup.ps1 not found in:" & vbCrLf & baseDir, vbCritical, "Whisper Transcriber Setup"
    WScript.Quit
End If

If Not WScript.Arguments.Named.Exists("elevated") Then
    shell.ShellExecute "wscript.exe", """" & WScript.ScriptFullName & """ /elevated:1", baseDir, "runas", 1
    WScript.Quit
End If

wshShell.CurrentDirectory = baseDir
wshShell.Run "powershell.exe -ExecutionPolicy Bypass -NoExit -File """ & psScript & """", 1, False
```

### `setup/setup.ps1`

```powershell
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Step($step, $msg) {
    Write-Host ""
    Write-Host "  [$step] $msg" -ForegroundColor Cyan
    Write-Host "  $('-' * 50)" -ForegroundColor DarkGray
}

function Write-Ok($msg) {
    Write-Host "       $msg" -ForegroundColor Green
}

function Write-Skip($msg) {
    Write-Host "       $msg" -ForegroundColor Yellow
}

function Write-Err($msg) {
    Write-Host "       $msg" -ForegroundColor Red
}

Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkCyan
Write-Host "       Whisper Transcriber - Setup" -ForegroundColor White
Write-Host "  =============================================" -ForegroundColor DarkCyan
Write-Host "  Project: $projectRoot" -ForegroundColor DarkGray
Write-Host ""

# Step 1: uv
Write-Step "1/5" "Checking uv (Python manager)..."
$uvPath = Get-Command uv -ErrorAction SilentlyContinue
if ($uvPath) {
    $uvVer = & uv --version 2>&1
    Write-Skip "Already installed: $uvVer"
} else {
    Write-Host "       Installing uv..." -ForegroundColor White
    try {
        irm https://astral.sh/uv/install.ps1 | iex
        $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
        $uvVer = & uv --version 2>&1
        Write-Ok "Installed: $uvVer"
    } catch {
        Write-Err "Failed to install uv: $_"
        Write-Err "Please install manually: https://docs.astral.sh/uv/getting-started/installation/"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Step 2: FFmpeg
Write-Step "2/5" "Checking FFmpeg (audio/video processing)..."
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ffmpegPath) {
    Write-Skip "Already installed: ffmpeg found at $($ffmpegPath.Source)"
} else {
    Write-Host "       Installing FFmpeg via winget..." -ForegroundColor White
    $wingetPath = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetPath) {
        try {
            & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
            Write-Ok "FFmpeg installed."
        } catch {
            Write-Err "winget install failed. Trying choco..."
            $chocoPath = Get-Command choco -ErrorAction SilentlyContinue
            if ($chocoPath) {
                & choco install ffmpeg -y
                Write-Ok "FFmpeg installed via choco."
            } else {
                Write-Err "Could not install FFmpeg automatically."
                Write-Err "Please install manually: https://www.gyan.dev/ffmpeg/builds/"
                Read-Host "Press Enter to exit"
                exit 1
            }
        }
    } else {
        Write-Err "winget not found."
        $chocoPath = Get-Command choco -ErrorAction SilentlyContinue
        if ($chocoPath) {
            & choco install ffmpeg -y
            Write-Ok "FFmpeg installed via choco."
        } else {
            Write-Err "Neither winget nor choco found. Please install FFmpeg manually."
            Read-Host "Press Enter to exit"
            exit 1
        }
    }
}

# Step 3: Python 3.11
Write-Step "3/5" "Installing Python 3.11 via uv..."
try {
    & uv python install 3.11 2>&1 | ForEach-Object { Write-Host "       $_" -ForegroundColor Gray }
    Write-Ok "Python 3.11 ready."
} catch {
    Write-Err "Failed: $_"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 4: Virtual environment
Write-Step "4/5" "Creating virtual environment..."
Set-Location $projectRoot
if (Test-Path ".venv") {
    Write-Skip "Virtual environment already exists. Recreating..."
    Remove-Item -Recurse -Force ".venv"
}
try {
    & uv venv --python 3.11 2>&1 | ForEach-Object { Write-Host "       $_" -ForegroundColor Gray }
    Write-Ok "Virtual environment created."
} catch {
    Write-Err "Failed: $_"
    Read-Host "Press Enter to exit"
    exit 1
}

# Step 5: Dependencies
Write-Step "5/5" "Installing dependencies (this may take a few minutes)..."
Write-Host "       faster-whisper, CUDA libraries, UI toolkit..." -ForegroundColor Gray
try {
    & uv pip install faster-whisper tkinterdnd2 nvidia-cublas-cu12 nvidia-cudnn-cu12 2>&1 | ForEach-Object {
        $line = $_.ToString()
        if ($line -match "Downloading|Installed|Resolved") {
            Write-Host "       $line" -ForegroundColor Gray
        }
    }
    Write-Ok "All dependencies installed."
} catch {
    Write-Err "Failed: $_"
    Read-Host "Press Enter to exit"
    exit 1
}

# Done
Write-Host ""
Write-Host "  =============================================" -ForegroundColor DarkCyan
Write-Host "       Setup complete!" -ForegroundColor Green
Write-Host "  =============================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  To launch the app, double-click:" -ForegroundColor White
Write-Host "       $projectRoot\launch.vbs" -ForegroundColor Yellow
Write-Host ""
Write-Host "  The first transcription will download the AI" -ForegroundColor Gray
Write-Host "  model (~1.5 GB). After that it's cached." -ForegroundColor Gray
Write-Host ""
Read-Host "  Press Enter to close"
```
