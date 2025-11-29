import re
import os


MIC_FILE = "Mic_transcript.txt"
SPK_FILE = "Speaker_transcript.txt"
OUT_FILE = "Combined_transcript.txt"


# -------------------------------------------------------
# Convert timestamp of BOTH formats → seconds
# -------------------------------------------------------
def to_seconds(ts):
    """
    Accepts:
        00:00:00.000
        00:00.00
        00:06.00
    Converts to seconds (float)
    """
    # Format 1 → HH:MM:SS.mmm   (MIC)
    if ts.count(":") == 2:
        h, m, s = ts.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    # Format 2 → MM:SS.ms   (SPEAKER)
    if ts.count(":") == 1:
        m, s = ts.split(":")
        return int(m) * 60 + float(s)

    return 0.0


# -------------------------------------------------------
# Convert ANY timestamp → MM:SS.ms (final output format)
# -------------------------------------------------------
def to_mmss(ts):
    sec = to_seconds(ts)
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"   # mm:ss.xx


# -------------------------------------------------------
# Parse a transcript file and extract segments
# -------------------------------------------------------
def parse_file(path, label):
    segments = []

    # MIC format: [00:00:00.000 → 00:00:18.000]
    p1 = re.compile(
        r"\[(\d{2}:\d{2}:\d{2}\.\d+)\s*→\s*(\d{2}:\d{2}:\d{2}\.\d+)\]\s*(.*)"
    )

    # SPEAKER format: [00:00.00 → 00:06.00]
    p2 = re.compile(
        r"\[(\d{2}:\d{2}\.\d+)\s*→\s*(\d{2}:\d{2}\.\d+)\]\s*(.*)"
    )

    with open(path, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()

            # MIC-style timestamps
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

            # SPEAKER-style timestamps
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
# Merge + sort + save
# -------------------------------------------------------
def merge_transcripts():
    if not os.path.exists(MIC_FILE) or not os.path.exists(SPK_FILE):
        print("❌ Transcript files missing")
        return

    mic = parse_file(MIC_FILE, "MIC")
    spk = parse_file(SPK_FILE, "SPEAKER")

    combined = mic + spk

    # ---------------------------------------------
    # OPTION B: Sort by start time, then end time
    # ---------------------------------------------
    combined.sort(key=lambda x: (x["start_sec"], x["end_sec"], x["label"]))

    # Write output
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        for seg in combined:
            f.write(
                f"[{to_mmss(seg['start'])} → {to_mmss(seg['end'])}] "
                f"({seg['label']}) {seg['text']}\n"
            )

    # Delete originals
    os.remove(MIC_FILE)
    os.remove(SPK_FILE)

    print("\n✅ Combined transcript written to:", OUT_FILE)


if __name__ == "__main__":
    merge_transcripts()
