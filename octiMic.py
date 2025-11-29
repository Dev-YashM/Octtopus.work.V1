#!/usr/bin/env python3
"""
MIC Whisper recorder + full transcription (sounddevice, auto device pick).

Behavior:
- Auto-selects a working MIC (OnePlus Nord Buds 3 Pro / Realtek Mic / default).
- Records continuously from your mic at 16 kHz.
- You speak normally.
- When you press Ctrl+C:
    - Stops recording
    - Runs Whisper ONCE on the full audio
    - Saves a .txt file with timestamps for each segment.

This avoids VAD chunking issues and lets Whisper handle segmentation itself.
"""

import sounddevice as sd
import numpy as np
import whisper
import torch
import time
from datetime import datetime

# ---------------- MODEL SETTINGS ---------------- #

# Good balance: better than "tiny", faster than "small"
# You can change to: "tiny", "base", "base.en", "small.en" etc.
MODEL_NAME = "tiny"

# If you want to hard-force a device ID from sd.query_devices(), put it here.
# Otherwise leave as None to auto-detect.
FORCE_DEVICE_ID = None

print("Loading Whisper model for MIC...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")
model = whisper.load_model(MODEL_NAME, download_root=".", device=device)

# ---------------- AUDIO SETTINGS ---------------- #

CAPTURE_SR = 16000        # record directly at 16 kHz (Whisper's native)
BLOCK_SEC = 0.5           # 0.5 second blocks
blocksize = int(CAPTURE_SR * BLOCK_SEC)

# ---------------- DEVICE SELECTION (same logic as your working script) ---------------- #

PREFERRED_KEYWORDS = [
    "OnePlus Nord Buds 3 Pro",
    "Microphone Array (Realtek HD Audio Mic input",
    "Microphone Array (Realtek(R) Au",
]

def list_input_devices():
    print("\n🎙 Available INPUT devices (for mic):\n")
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_input_channels'] > 0:
            print(f"{i}: {dev['name']}  | max_in={dev['max_input_channels']}")
    print()

def pick_working_input_device():
    devices = sd.query_devices()

    # If user wants to force one specific device ID
    if FORCE_DEVICE_ID is not None:
        idx = FORCE_DEVICE_ID
        try:
            sd.check_input_settings(device=idx, samplerate=CAPTURE_SR, channels=1)
            print(f"\nℹ Using FORCED input device ID = {idx}: {devices[idx]['name']}")
            return idx
        except Exception as e:
            print(f"❌ Forced device {idx} failed: {e}")

    # Build candidate list by keyword match
    candidates = []
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] <= 0:
            continue
        name = dev['name']
        if any(key in name for key in PREFERRED_KEYWORDS):
            candidates.append((i, name))

    print("\n🔍 Trying preferred mic devices (OnePlus / Realtek mics):")
    for idx, name in candidates:
        try:
            sd.check_input_settings(device=idx, samplerate=CAPTURE_SR, channels=1)
            print(f"✅ Using device {idx}: {name}")
            return idx
        except Exception as e:
            print(f"❌ Device {idx} ({name}) not usable: {e}")

    # If none of the preferred work, try default
    default_idx = sd.default.device[0]
    try:
        sd.check_input_settings(device=default_idx, samplerate=CAPTURE_SR, channels=1)
        print(f"\n⚠ Falling back to DEFAULT input device {default_idx}: {devices[default_idx]['name']}")
        return default_idx
    except Exception as e:
        print(f"❌ Default input device {default_idx} failed too: {e}")

    # As last resort, just scan all input-capable devices and pick first that works
    print("\n⚠ Scanning all input devices to find any that works...")
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] <= 0:
            continue
        try:
            sd.check_input_settings(device=i, samplerate=CAPTURE_SR, channels=1)
            print(f"✅ Using fallback device {i}: {dev['name']}")
            return i
        except Exception:
            continue

    raise RuntimeError("No working microphone device found")

# ---------------- UTILS ---------------- #

def format_ts(seconds: float) -> str:
    """Convert seconds -> HH:MM:SS.mmm format."""
    if seconds is None:
        return "??:??:??.???"
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds)
    h = s // 3600
    s = s % 3600
    m = s // 60
    s = s % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    list_input_devices()
    input_id = pick_working_input_device()
    dev_info = sd.query_devices(input_id)
    print(f"\n🎤 Capturing MIC from: {dev_info['name']} (ID {input_id})\n")

    audio_chunks = []

    print("🎧 Recording from MIC...")
    print("   Speak normally. When you're done, press Ctrl+C to stop and transcribe.\n")

    try:
        with sd.InputStream(
            samplerate=CAPTURE_SR,
            channels=1,
            dtype='float32',
            device=input_id,
        ) as stream:
            while True:
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    print("⚠ MIC buffer overflow (some samples dropped)")
                block = data.reshape(-1)
                audio_chunks.append(block.copy())
    except KeyboardInterrupt:
        print("\n✋ Recording stopped by user. Preparing audio for transcription...\n")

    if not audio_chunks:
        print("No audio was captured, nothing to transcribe.")
        raise SystemExit

    # Concatenate all chunks into one long 1D float32 array
    full_audio = np.concatenate(audio_chunks).astype(np.float32)

    # Normalize
    max_val = np.max(np.abs(full_audio)) if len(full_audio) > 0 else 0
    if max_val > 0:
        full_audio = full_audio / max_val

    print(f"⏱ Total recorded duration: {len(full_audio) / CAPTURE_SR:.2f} seconds")
    print("🧠 Running Whisper transcription... (this may take a bit)\n")

    result = model.transcribe(
        full_audio,
        fp16=(device == "cuda"),
        language="en",
        verbose=False,
        task="transcribe",
        temperature=0.0,
        beam_size=5,
        condition_on_previous_text=False,
    )

    segments = result.get("segments", [])
    full_text = result.get("text", "").strip()

    # ---------------- SAVE TO FILE WITH TIMESTAMPS ---------------- #

    filename = "Mic_transcript.txt"   # <--- FIXED FILENAME

    with open(filename, "w", encoding="utf-8") as f:
        f.write("Full transcript:\n")
        f.write(full_text + "\n\n")
        f.write("Per-segment timestamps:\n\n")
        for seg in segments:
            start = format_ts(seg.get("start"))
            end = format_ts(seg.get("end"))
            text = seg.get("text", "").strip()
            line = f"[{start} → {end}] {text}"
            f.write(line + "\n")

    print("✅ Transcription complete.")
    print(f"📄 Saved transcript with timestamps to: {filename}\n")