import os
import subprocess
import time

from constants import VIDEO_EXTENSIONS


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


def save_transcript(filepath, full_text, output_dir):
    source_base = os.path.splitext(os.path.basename(filepath))[0]
    out_path = os.path.join(output_dir, source_base + ".txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    return os.path.basename(out_path)
