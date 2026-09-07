# Wake-word models

**Default detector: sherpa-onnx open-vocabulary KWS** (`provider: sherpa`).
The phrase `hey mason` is tokenized at runtime — no training needed, and it
genuinely listens for "hey mason". The ~13MB zipformer model downloads once to
`~/.mason/cache/wakewords/` on first use.

## Legacy files in this folder

`hey_mason.onnx` / `hey_mason.tflite` — openWakeWord weights **trained on the
previous hotword, not true "hey mason" detectors**. Kept only for backward
compat when `provider: openwakeword` is set explicitly. Do not rely on them
for "hey mason".

- **Engine:** [openWakeWord](https://github.com/dscripka/openWakeWord) (Apache-2.0).
- **Runtime:** openWakeWord's shared feature-extraction models (melspectrogram +
  embedding) are NOT bundled here — fetched once on first use via
  `openwakeword.utils.download_models()`.

## Training true openWakeWord weights (optional)

To replace the legacy files with genuinely-trained "hey mason" weights:

```bash
python scripts/train_wakeword.py --phrase "hey mason" --out tools/wakewords/
```

See the script header for the data it needs (positive clips + negative
speech). Until then, sherpa is the correct default.

To use a different phrase with zero training, just set `wake_word.phrase` —
sherpa tokenizes anything.
