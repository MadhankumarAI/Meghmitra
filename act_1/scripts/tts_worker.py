"""TTS worker: renders queued voice notes with AI4Bharat Indic Parler-TTS (Apache-2.0), offline, GPU or CPU.

Runs in the ML venv next to the service and shares its SQLite file:
    .venv-ml\\Scripts\\python scripts\\tts_worker.py            # keep polling for jobs
    .venv-ml\\Scripts\\python scripts\\tts_worker.py --once     # drain the queue and exit
    .venv-ml\\Scripts\\python scripts\\tts_worker.py --say kn "ನಮಸ್ಕಾರ"   # one-off test -> var/media/voice/test.ogg

Output: OGG/Opus mono 48 kHz, which WhatsApp shows as a playable voice note (kept well under 512 KB).
Long scripts are synthesised sentence by sentence and joined with short pauses; Parler degrades past ~30 s.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = "ai4bharat/indic-parler-tts"
DB = Path(os.environ.get("DB_PATH", ROOT / "var" / "delivery.sqlite3"))
VOICE_DIR = ROOT / "var" / "media" / "voice"
SENTENCE = re.compile(r"(?<=[.!?।॥])\s+")
PAUSE_S = 0.35
BATCH = int(os.environ.get("TTS_BATCH", "3"))  # sentences per generate call; 3 fits a 4 GB GPU in fp32


def describe(speaker: str) -> str:
    return (f"{speaker} speaks at a slightly slow pace with a clear, calm and friendly voice. "
            "The recording is of very high quality, with the voice sounding clear and very close up, "
            "and there is no background noise.")


class Parler:
    def __init__(self) -> None:
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 2))
        self.torch = torch
        # GPU when present (a 4 GB GTX 1650 holds the model in fp32). Not fp16: its T5 text encoder overflows to
        # NaN in half precision and the note comes out silent.
        self.device = "cuda" if torch.cuda.is_available() and os.environ.get("TTS_DEVICE") != "cpu" else "cpu"
        if self.device == "cuda":
            # Stream the weights straight onto the GPU in fp16 (accelerate's device_map), so this 7.5 GB laptop
            # never holds a full copy in RAM, then upcast on the GPU (fp16 inference gives NaN, see above).
            self.model = ParlerTTSForConditionalGeneration.from_pretrained(
                MODEL, torch_dtype=torch.float16, device_map="cuda", low_cpu_mem_usage=True).float().eval()
        else:
            self.model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL).eval()
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.desc_tok = AutoTokenizer.from_pretrained(self.model.config.text_encoder._name_or_path)
        self.rate = self.model.config.sampling_rate

    def sentences(self, texts: list[str], speaker: str) -> list:
        """Synthesise several sentences in one batched generate call (the GPU works on them in parallel)."""
        import numpy as np
        d = self.desc_tok([describe(speaker)] * len(texts), return_tensors="pt", padding=True).to(self.device)
        p = self.tok(texts, return_tensors="pt", padding=True).to(self.device)
        self.torch.manual_seed(0)  # same text -> same voice
        with self.torch.no_grad():
            gen = self.model.generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                                      prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask,
                                      return_dict_in_generate=True)
        return [np.asarray(gen.sequences[i, :gen.audios_length[i]].float().cpu().numpy(), dtype="float32")
                for i in range(len(texts))]

    def render(self, text: str, speaker: str, out: Path) -> None:
        import numpy as np
        import soundfile as sf
        parts = [s.strip() for s in SENTENCE.split(text) if s.strip()]
        gap = np.zeros(int(self.rate * PAUSE_S), dtype="float32")
        chunks = []
        i, batch = 0, BATCH
        while i < len(parts):
            try:
                audios = self.sentences(parts[i:i + batch], speaker)
            except RuntimeError as e:  # torch reports GPU OOM as OutOfMemoryError or as "CUDA error: out of memory"
                if "out of memory" not in str(e) or batch == 1:
                    raise
                self.torch.cuda.empty_cache()
                batch = max(1, batch // 2)
                continue
            for part, audio in zip(parts[i:i + batch], audios):
                # Never ship a broken note: NaN or near-silence fails the job instead.
                if not np.isfinite(audio).all() or float(np.sqrt(np.mean(audio ** 2))) < 0.005:
                    raise RuntimeError(f"TTS produced silence/NaN for: {part[:60]}")
                chunks += [audio, gap]
            i += batch
        wav = np.concatenate(chunks) if chunks else gap
        peak = float(np.max(np.abs(wav))) or 1.0
        wav = (wav / peak * 0.9).astype("float32")
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "v.wav"
            sf.write(wav_path, wav, self.rate)
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-ac", "1", "-ar", "48000",
                            "-c:a", "libopus", "-b:a", "24k", "-application", "voip", str(out)], check=True)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    return c


def claim(c: sqlite3.Connection):
    c.execute("BEGIN IMMEDIATE")
    row = c.execute("SELECT key, language, text, engine FROM tts_jobs WHERE state='pending' "
                    "ORDER BY priority DESC, created_ts LIMIT 1").fetchone()
    if row:
        c.execute("UPDATE tts_jobs SET state='running', updated_ts=? WHERE key=?", (now(), row["key"]))
    c.execute("COMMIT")
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--say", nargs=2, metavar=("LANG_SPEAKER", "TEXT"))
    args = ap.parse_args()

    t0 = time.time()
    tts = Parler()
    print(f"model loaded on {tts.device} in {time.time() - t0:.0f}s", flush=True)

    if args.say:
        speaker, text = args.say
        out = VOICE_DIR / "test.ogg"
        t0 = time.time()
        tts.render(text, speaker, out)
        print(f"{out} in {time.time() - t0:.0f}s", flush=True)
        return

    c = connect()
    # Jobs left 'running' by a crashed worker go back to the queue.
    c.execute("UPDATE tts_jobs SET state='pending' WHERE state='running'")
    while True:
        job = claim(c)
        if job is None:
            if args.once:
                return
            time.sleep(2)
            continue
        speaker = (job["engine"] or ":").split(":", 1)[1] or "Mary"
        out = VOICE_DIR / f"{job['key']}.ogg"
        t0 = time.time()
        try:
            tts.render(job["text"], speaker, out)
            c.execute("UPDATE tts_jobs SET state='done', path=?, error=NULL, updated_ts=? WHERE key=?",
                      (str(out), now(), job["key"]))
            print(f"done {job['language']} {job['key']} {time.time() - t0:.0f}s {out.stat().st_size // 1024} KB",
                  flush=True)
        except Exception as e:
            if "CUDA error" in str(e):
                # A CUDA error leaves the GPU context unusable: requeue the job and exit so the worker is restarted
                # (scripts/run.ps1 does this) with a fresh context, instead of failing every job after this one.
                c.execute("UPDATE tts_jobs SET state='pending', updated_ts=? WHERE key=?", (now(), job["key"]))
                print(f"CUDA error on {job['key']}, restarting: {e}", file=sys.stderr, flush=True)
                sys.exit(3)
            c.execute("UPDATE tts_jobs SET state='failed', error=?, updated_ts=? WHERE key=?",
                      (str(e)[:500], now(), job["key"]))
            print(f"failed {job['key']}: {e}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
