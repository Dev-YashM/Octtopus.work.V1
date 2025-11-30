import re
import os
from openai import OpenAI

# ---------------------- CONFIG ----------------------
MIC_FILE = "Mic_transcript.txt"
SPK_FILE = "Speaker_transcript.txt"
OUT_FILE = "Combined_transcript.txt"
SUMMARY_FILE = "Meeting_summary.txt"

client = OpenAI()   # Uses OPENAI_API_KEY from environment

# -------------------------------------------------------
# Convert timestamp → seconds
# -------------------------------------------------------
def to_seconds(ts):
    if ts.count(":") == 2:   # HH:MM:SS.mmm
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    if ts.count(":") == 1:   # MM:SS.mm
        m, s = ts.split(":")
        return int(m) * 60 + float(s)

    return 0.0


# -------------------------------------------------------
# Convert ANY timestamp → MM:SS.ms
# -------------------------------------------------------
def to_mmss(ts):
    sec = to_seconds(ts)
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


# -------------------------------------------------------
# Parse a transcript file
# -------------------------------------------------------
def parse_file(path, label):
    segments = []

    p1 = re.compile(
        r"\[(\d{2}:\d{2}:\d{2}\.\d+)\s*→\s*(\d{2}:\d{2}:\d{2}\.\d+)\]\s*(.*)"
    )

    p2 = re.compile(
        r"\[(\d{2}:\d{2}\.\d+)\s*→\s*(\d{2}:\d{2}\.\d+)\]\s*(.*)"
    )

    with open(path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()

            m = p1.search(line)
            if m:
                start, end, text = m.groups()
                segments.append({
                    "start": start,
                    "end": end,
                    "start_sec": to_seconds(start),
                    "end_sec": to_seconds(end),
                    "text": text,
                    "label": label
                })
                continue

            m = p2.search(line)
            if m:
                start, end, text = m.groups()
                segments.append({
                    "start": start,
                    "end": end,
                    "start_sec": to_seconds(start),
                    "end_sec": to_seconds(end),
                    "text": text,
                    "label": label
                })

    return segments


# -------------------------------------------------------
# Call ChatGPT to generate summary + title
# -------------------------------------------------------
def generate_summary(transcript_text):
    prompt = f"""
You are an AI meeting assistant.

Below is the full meeting transcript.

Your tasks:
1. Give a clear, professional meeting **title** (one line).
2. Give a concise **summary** (5–10 bullet points max).
3. Do NOT include the transcript back.

Transcript:
{transcript_text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",    # You can change this
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


# -------------------------------------------------------
# Merge transcripts + produce summary
# -------------------------------------------------------
def merge_transcripts():
    if not os.path.exists(MIC_FILE) or not os.path.exists(SPK_FILE):
        print("❌ Transcript files missing")
        return

    mic = parse_file(MIC_FILE, "MIC")
    spk = parse_file(SPK_FILE, "SPEAKER")

    combined = mic + spk

    combined.sort(key=lambda x: (x["start_sec"], x["end_sec"], x["label"]))

    # Write combined transcript
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for seg in combined:
            f.write(
                f"[{to_mmss(seg['start'])} → {to_mmss(seg['end'])}] "
                f"({seg['label']}) {seg['text']}\n"
            )

    # Delete original split files
    os.remove(MIC_FILE)
    os.remove(SPK_FILE)

    print("\n✅ Combined transcript written to:", OUT_FILE)

    # -----------------------------------------
    # Generate SUMMARY using ChatGPT
    # -----------------------------------------
    print("📡 Sending transcript to ChatGPT...")

    with open(OUT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    summary_text = generate_summary(text)

    # Save summary to file
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(summary_text)

    print("✅ Meeting summary saved to:", SUMMARY_FILE)


if __name__ == "__main__":
    merge_transcripts()
