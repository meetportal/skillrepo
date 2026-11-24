import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from media import clip_name, decode_audio

SAMPLE_RATE = 16000


def load_model(name, compute_type, threads):
    from faster_whisper import WhisperModel

    return WhisperModel(name, device="cpu", compute_type=compute_type, cpu_threads=threads)


def transcribe_array(model, audio, prompt, language, beam_size):
    segments, _ = model.transcribe(
        audio,
        language=language,
        beam_size=beam_size,
        word_timestamps=True,
        initial_prompt=prompt or None,
        condition_on_previous_text=False,
        vad_filter=False,
    )
    words, texts = [], []
    for segment in segments:
        texts.append(segment.text)
        for word in segment.words or []:
            words.append({"word": word.word.strip(), "start": round(word.start, 3), "end": round(word.end, 3), "prob": round(word.probability, 3)})
    return "".join(texts).strip(), words


def main():
    parser = argparse.ArgumentParser(description="Word-level transcription with faster-whisper (audio decoded by ffmpeg into numpy).")
    parser.add_argument("inputs", nargs="+", help="video or audio files")
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--language", default="en")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--prompt", default="", help="key terms and brand names, e.g. 'Acme. SPF, DKIM, DMARC.'")
    args = parser.parse_args()
    started = time.time()
    model = load_model(args.model, args.compute_type, args.threads)
    report = {"model": args.model, "initial_prompt": args.prompt, "sample_rate": SAMPLE_RATE, "clips": {}}
    for path in args.inputs:
        audio = decode_audio(path, sample_rate=SAMPLE_RATE, channels=1)
        text, words = transcribe_array(model, audio, args.prompt, args.language, args.beam_size)
        report["clips"][clip_name(path)] = {"file": str(Path(path).resolve()), "duration": round(len(audio) / SAMPLE_RATE, 3), "text": text, "words": words}
        print(f"{clip_name(path)}: {text}", flush=True)
    report["seconds"] = round(time.time() - started, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
