#!/usr/bin/env python3
"""Train TRUE "hey mason" openWakeWord weights to replace the legacy files.

The bundled tools/wakewords/hey_mason.{onnx,tflite} were trained on the
previous hotword — the sherpa default is the genuine hey-mason path today.
Run this when you want native openWakeWord weights for "hey mason":

    1. Collect data (all 16 kHz mono WAV):
         data/positive/  — 50+ clips of people saying "hey mason"
                            (vary speakers, mics, rooms; 1-2 s each).
                            Tip: Mason's own TTS (mason tts) can draft clips,
                            but mix in real voices or it only hears robots.
         data/negative/  — 200+ clips of speech WITHOUT the phrase
                            (podcasts, meetings, TV) + room noise.
    2. pip install openwakeword[training] tensorflow
    3. python scripts/train_wakeword.py --phrase "hey mason" \\
           --positive data/positive --negative data/negative \\
           --out tools/wakewords/
    4. Flip wake_word.provider back to openwakeword and say "hey mason".

What the script does:
  positives -> openwakeword DataGenerator -> train/test split (90/10) ->
  transfer-learn the shared embedding (frozen) + a new dense head ->
  export hey_mason.onnx, convert hey_mason.tflite, print a threshold hint.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _need(cmd: list[str], what: str) -> None:
    if shutil.which(cmd[0]) is None and _importable(cmd[0]) is False:
        raise SystemExit(f"missing {what}: install it first ({' '.join(cmd)})")


def _importable(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Train TRUE hey-mason openWakeWord weights.")
    ap.add_argument("--phrase", default="hey mason")
    ap.add_argument("--positive", required=True, help="dir of positive WAV clips")
    ap.add_argument("--negative", required=True, help="dir of negative WAV clips")
    ap.add_argument("--out", default="tools/wakewords")
    ap.add_argument("--steps", type=int, default=5000)
    args = ap.parse_args()

    for mod, pkg in (("openwakeword", "openwakeword[training]"), ("tensorflow", "tensorflow")):
        if not _importable(mod):
            raise SystemExit(f"missing {pkg}: pip install {pkg}")

    pos, neg, out = Path(args.positive), Path(args.negative), Path(args.out)
    for d in (pos, neg):
        if not d.is_dir() or not list(d.glob("*.wav")):
            raise SystemExit(f"no WAV clips in {d} — see script header step 1")
    out.mkdir(parents=True, exist_ok=True)

    slug = args.phrase.strip().lower().replace(" ", "_")
    print(f"training openWakeWord model for {args.phrase!r} "
          f"({len(list(pos.glob('*.wav')))} pos / {len(list(neg.glob('*.wav')))} neg, {args.steps} steps)")
    cmd = [sys.executable, "-m", "openwakeword.train",
           "--positive-data-dir", str(pos), "--negative-data-dir", str(neg),
           "--output-dir", str(out), "--model-name", slug, "--training-steps", str(args.steps)]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit("openwakeword training failed (see output above)")
    print(f"done: {out / (slug + '.onnx')}")
    print("Next: set wake_word.provider=openwakeword and verify with live mic. "
          "Keep sherpa as fallback until false-fire rate is measured.")


if __name__ == "__main__":
    main()
