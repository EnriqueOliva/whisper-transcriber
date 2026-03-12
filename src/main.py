import os
import sys
import ctypes

ctypes.windll.shcore.SetProcessDpiAwareness(1)

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

_config_path = os.path.join(PROJECT_ROOT, "config.txt")
UI_VARIANT = None
if os.path.isfile(_config_path):
    _raw = open(_config_path, encoding="utf-8").read().strip()
    if _raw and _raw != "default":
        UI_VARIANT = _raw

if __name__ == "__main__":
    if UI_VARIANT:
        import importlib
        mod = importlib.import_module(f"uis.ui_{UI_VARIANT}")
    else:
        import ui as mod
    app = mod.TranscriberApp()
    app.run()
