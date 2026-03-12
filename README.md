# Whisper Transcriber

A GPU-accelerated audio/video transcription desktop app for Windows. Drag and drop files, get text transcripts. Runs 100% locally — no internet, no cloud, no subscriptions.

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (a high-performance reimplementation of OpenAI's Whisper using CTranslate2).

## Features

- **Drag & drop** audio and video files — or click to browse
- **GPU-accelerated** via NVIDIA CUDA (RTX series recommended)
- **Batch processing** — queue hundreds of files at once
- **Video support** — auto-extracts audio from mp4, mkv, avi, mov, webm, etc.
- **Audio support** — mp3, wav, m4a, ogg, flac, wma, aac
- **99+ languages** — Spanish, English, Portuguese, French, German, and more
- **Multiple models** — from `tiny` (fastest) to `large-v3` (most accurate)
- **Output format options** — save as `.txt` transcript, or copy source files renamed by their transcript content (useful for cataloging voice clips)
- **Timeout protection** — gracefully skips files that hang due to noise or corruption
- **VAD fallback** — retries with Voice Activity Detection disabled if the first pass returns empty
- **Session logging** — automatically saves a detailed session log to `log/` on every run

## Requirements

- Windows 10/11
- NVIDIA GPU with updated drivers (any modern GeForce/RTX)
- ~4 GB disk space (dependencies + model cache)

## Quick Start

### First-time setup

1. Double-click `setup/setup.vbs`
2. Approve the admin prompt
3. Wait for the setup to complete (~5-10 minutes depending on internet speed)

### Daily use

1. Double-click `launch.vbs`
2. Drop files onto the window
3. Click **TRANSCRIBE**
4. Click **Open output folder** to see results

## Project Structure

```
whisper-transcriber/
├── launch.vbs              # App launcher (double-click to run)
├── setup/
│   ├── setup.vbs           # Setup launcher (requests admin, runs setup.ps1)
│   └── setup.ps1           # Automated installer (uv, FFmpeg, Python, dependencies)
├── src/
│   ├── main.py             # Entry point (CUDA path setup, app launch)
│   ├── ui.py               # GUI (tkinter + tkinterdnd2)
│   ├── engine.py           # Transcription logic (faster-whisper, ffmpeg, file I/O)
│   └── constants.py        # Config (colors, extensions, paths)
├── output/                 # Default transcript output directory
├── log/                    # Session logs (auto-generated, one file per last session)
├── LICENSE                 # MIT License
└── .venv/                  # Python virtual environment (created by setup)
```

## Configuration

All settings are available in the app UI:

| Setting | Options | Default |
|---------|---------|---------|
| Language | Auto-detect, Spanish, English, +7 more | Spanish |
| Model | large-v3, medium, small, base, tiny | large-v3 |
| Output format | Transcript (.txt), Rename source by transcript | Transcript (.txt) |
| Output folder | Any local path | `./output/` |

## Dependencies

Managed automatically by the setup script:

| Dependency | Purpose | Installed via |
|------------|---------|---------------|
| [uv](https://docs.astral.sh/uv/) | Python version & package manager | astral.sh installer |
| [FFmpeg](https://ffmpeg.org/) | Audio/video decoding | winget or choco |
| Python 3.11 | Runtime | uv |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper inference engine | pip (in venv) |
| [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) | Drag & drop for tkinter | pip (in venv) |
| nvidia-cublas-cu12 | CUDA linear algebra | pip (in venv) |
| nvidia-cudnn-cu12 | CUDA deep neural networks | pip (in venv) |

## Model Information

Models are downloaded automatically on first use and cached at `~/.cache/huggingface/`.

| Model | Size | Speed | Accuracy | VRAM |
|-------|------|-------|----------|------|
| tiny | ~75 MB | Fastest | Basic | ~1 GB |
| base | ~145 MB | Very fast | Good | ~1 GB |
| small | ~480 MB | Fast | Very good | ~2 GB |
| medium | ~1.5 GB | Moderate | Great | ~5 GB |
| large-v3 | ~1.5 GB | Moderate | Best | ~4 GB |

> **Recommendation:** `large-v3` with an RTX GPU. On an RTX 4070 12GB, it processes audio at roughly 10-20x real-time speed.

## Portability

To set up on a new Windows PC, copy these files:
- `launch.vbs`
- `setup/setup.vbs`
- `setup/setup.ps1`
- `src/main.py`
- `src/ui.py`
- `src/engine.py`
- `src/constants.py`

Then run `setup/setup.vbs`. The setup script handles everything else.

## License

MIT License. See [LICENSE](LICENSE).

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), based on [OpenAI Whisper](https://github.com/openai/whisper) (MIT).
