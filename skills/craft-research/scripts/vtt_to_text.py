import argparse
import html
import re
import sys
from pathlib import Path

TIMING = re.compile(r"^(\d+:)?\d{2}:\d{2}\.\d{3}\s+-->\s+(\d+:)?\d{2}:\d{2}\.\d{3}")
TAG = re.compile(r"<[^>]+>")


def seconds(stamp):
    parts = [float(p) for p in stamp.split(":")]
    return sum(value * 60 ** index for index, value in enumerate(reversed(parts)))


def cues(text):
    block_start, lines = None, []
    for raw in text.splitlines() + [""]:
        line = raw.strip()
        if TIMING.match(line):
            block_start, lines = seconds(line.split("-->")[0].strip()), []
        elif not raw.rstrip("\r"):
            if block_start is not None and lines:
                yield block_start, lines
            block_start, lines = None, []
        elif block_start is not None and line:
            lines.append(html.unescape(TAG.sub("", line)).strip())


def dedupe(text):
    emitted, last = [], ""
    for start, lines in cues(text):
        for line in lines:
            if not line or line == last:
                continue
            if last and line.startswith(last):
                line = line[len(last):].strip()
                if not line:
                    continue
            emitted.append((start, line))
            last = line
    return emitted


def main():
    parser = argparse.ArgumentParser(
        description="Turn a YouTube .vtt (auto or manual subtitles) into readable text: tags stripped, rolling duplicate lines removed, "
                    "one paragraph per N seconds with an [mm:ss] stamp for citing.")
    parser.add_argument("vtt", help="subtitle file written by yt-dlp --write-auto-subs / --write-subs")
    parser.add_argument("--every", type=float, default=15.0, help="seconds per paragraph (default 15)")
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args()

    lines = dedupe(Path(args.vtt).read_text(encoding="utf-8", errors="replace"))
    paragraphs, current, current_start = [], [], None
    for start, line in lines:
        if current_start is None:
            current_start = start
        if start - current_start >= args.every and current:
            paragraphs.append((current_start, " ".join(current)))
            current, current_start = [], start
        current.append(line)
    if current:
        paragraphs.append((current_start, " ".join(current)))
    output = "\n".join(f"[{int(s // 60):02d}:{int(s % 60):02d}] {t}" for s, t in paragraphs) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
