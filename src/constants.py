import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")
DEFAULT_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
LOG_DIR = os.path.join(PROJECT_ROOT, "log")

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
    "border_hover": "#79c0ff",
    "text":         "#e8e2da",
    "text_sec":     "#9490a0",
    "text_dim":     "#5c586a",
    "accent":       "#79c0ff",
    "accent_hover": "#9dd0ff",
    "accent_press": "#5a9fd4",
    "green":        "#7ec4a0",
    "amber":        "#c4a06c",
    "red":          "#c07070",
    "red_hover":    "#e08080",
    "log_bg":       "#111118",
    "log_fg":       "#8a8694",
    "entry_bg":     "#18181f",
    "entry_fg":     "#d0ccc4",
}
