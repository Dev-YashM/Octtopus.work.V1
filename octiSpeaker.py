# #!/usr/bin/env python3
# """
# Continuous system-audio recorder → full Whisper transcription at end.

# Requirements:
#     pip install soundcard numpy torch openai-whisper
# """

# import soundcard as sc
# import numpy as np
# import whisper
# import torch
# import time
# import sys
# import threading

# # ------------------ WHISPER ------------------ #

# print("Loading Whisper model...")
# device = "cuda" if torch.cuda.is_available() else "cpu"
# print("Using:", device)

# model = whisper.load_model("small", device=device)

# # ------------------ AUDIO CAPTURE SETTINGS ------------------ #

# CAPTURE_SR = 48000     # system audio sampling rate
# TARGET_SR = 16000      # Whisper required sampling rate
# BLOCK_SEC = 0.2        # 200ms blocks
# blocksize = int(CAPTURE_SR * BLOCK_SEC)

# full_audio = []        # store entire session

# def resample_to_16k(audio, sr_src=48000, sr_tgt=16000):
#     if sr_src == sr_tgt:
#         return audio
#     duration = len(audio) / sr_src
#     target_len = int(duration * sr_tgt)
#     return np.interp(
#         np.linspace(0, len(audio), target_len, endpoint=False),
#         np.arange(len(audio)),
#         audio
#     ).astype(np.float32)

# # ------------------ AUDIO CAPTURE THREAD ------------------ #

# def audio_capture_worker():
#     global full_audio

#     default_speaker = sc.default_speaker()
#     print("\n🎧 Default speaker:", default_speaker)

#     loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
#     print("🎧 Loopback source:", loopback)

#     with loopback.recorder(samplerate=CAPTURE_SR, channels=2) as rec:
#         print("\n🟢 Recording system audio... Press CTRL + C to stop.\n")
#         while True:
#             block = rec.record(blocksize)
#             # mono downmix
#             if block.ndim > 1:
#                 block = block.mean(axis=1)
#             full_audio.append(block.copy())

# # ------------------ START RECORDING ------------------ #

# thread = threading.Thread(target=audio_capture_worker, daemon=True)
# thread.start()

# try:
#     while True:
#         time.sleep(1)
# except KeyboardInterrupt:
#     print("\n\n✋ Stopped recording.\nProcessing audio...")

# # ------------------ PROCESSING ------------------ #

# if len(full_audio) == 0:
#     print("No audio captured.")
#     sys.exit()

# full_audio = np.concatenate(full_audio).astype(np.float32)
# print("Total samples:", len(full_audio))

# # Resample to 16 kHz for Whisper
# audio_16k = resample_to_16k(full_audio)

# print("Running Whisper transcription...")
# result = model.transcribe(audio_16k, fp16=False)

# # ------------------ SAVE TO FILE ------------------ #

# output_path = "transcript.txt"

# def format_timestamp(t):
#     mm = int(t // 60)
#     ss = t % 60
#     return f"{mm:02d}:{ss:05.2f}"

# with open(output_path, "w", encoding="utf-8") as f:
#     for seg in result["segments"]:
#         start = format_timestamp(seg["start"])
#         end = format_timestamp(seg["end"])
#         text = seg["text"].strip()
#         f.write(f"[{start} → {end}] {text}\n")

# print(f"\n✅ Saved transcript to: {output_path}")
# print("Done.")



#!/usr/bin/env python3
"""
Continuous system-audio recorder → full Whisper transcription at end.
"""

import soundcard as sc
import numpy as np
import whisper
import torch
import time
import sys
import threading
import warnings

# ------------- REMOVE ALL SOUNDCARD WARNINGS ------------- #
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

# ------------------ WHISPER ------------------ #

print("Loading Whisper model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print("Using:", device)

model = whisper.load_model("small", device=device)

# ------------------ AUDIO SETTINGS ------------------ #

CAPTURE_SR = 48000
TARGET_SR = 16000
BLOCK_SEC = 0.2
blocksize = int(CAPTURE_SR * BLOCK_SEC)

full_audio = []

def resample_to_16k(audio, sr_src=48000, sr_tgt=16000):
    if sr_src == sr_tgt:
        return audio.astype(np.float32)
    duration = len(audio) / sr_src
    target_len = int(duration * sr_tgt)
    return np.interp(
        np.linspace(0, len(audio), target_len, endpoint=False),
        np.arange(len(audio)),
        audio
    ).astype(np.float32)

# ------------------ AUDIO CAPTURE THREAD ------------------ #

def audio_capture_worker():
    global full_audio

    default_speaker = sc.default_speaker()
    print("\n🎧 Default speaker:", default_speaker)

    loopback = sc.get_microphone(id=str(default_speaker.name), include_loopback=True)
    print("🎧 Loopback source:", loopback)
    print("\n🟢 Recording system audio... Press CTRL + C to stop.\n")

    with loopback.recorder(samplerate=CAPTURE_SR, channels=2) as rec:
        while True:
            block = rec.record(blocksize)

            if not isinstance(block, np.ndarray):
                continue

            if block.ndim > 1:
                block = block.mean(axis=1)

            try:
                full_audio.append(block.astype(np.float32))
            except Exception:
                pass  # safe fail, prevents crashes

# ------------------ START RECORDING ------------------ #

thread = threading.Thread(target=audio_capture_worker, daemon=True)
thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\n✋ Stopped recording.\nProcessing audio...")

# ------------------ PROCESSING ------------------ #

if len(full_audio) == 0:
    print("No audio captured.")
    sys.exit()

full_audio = np.concatenate(full_audio).astype(np.float32)
print("Total samples:", len(full_audio))

audio_16k = resample_to_16k(full_audio)

print("Running Whisper transcription...")
result = model.transcribe(audio_16k, fp16=False)

# ------------------ SAVE TO FILE ------------------ #

output_path = "Speaker_transcript.txt"

def ts(t):
    mm = int(t // 60)
    ss = t % 60
    return f"{mm:02d}:{ss:05.2f}"

with open(output_path, "w", encoding="utf-8") as f:
    for seg in result["segments"]:
        start = ts(seg["start"])
        end = ts(seg["end"])
        f.write(f"[{start} → {end}] {seg['text'].strip()}\n")

print(f"\n✅ Saved transcript to: {output_path}")
print("Done.")
