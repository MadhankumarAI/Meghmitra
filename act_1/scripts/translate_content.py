"""Pre-translate content/locales/en.yaml into every other locale file with AI4Bharat IndicTrans2.

Runs offline, ahead of time, in the ML venv:
    .venv-ml\\Scripts\\python scripts\\translate_content.py            # all locales
    .venv-ml\\Scripts\\python scripts\\translate_content.py kn hi      # some
    .venv-ml\\Scripts\\python scripts\\translate_content.py --force kn # re-translate machine entries too

Each output entry is {source, text, status}:
  machine   raw model output, placeholders verified. Usable, but must be reviewed by a native speaker.
  checked   read against the English source and corrected by a model review (placeholders and WhatsApp
            limits verified). Better than `machine`, but still NOT a native speaker's sign-off.
  reviewed  signed off by a native speaker (set by hand). Never overwritten by this script.
  stale     was reviewed, but the English source has since changed. Text kept; needs a new review.
  glossary  hand-entered term from the locale's `glossary:` block (crop names). Not machine translated;
            still needs a native speaker's sign-off.
  needs_fix model output lost a {placeholder} or is too long for WhatsApp; `text` is left empty so the
            service falls back to English, and the model output is kept in `mt` for the reviewer.
To add a language: create content/locales/<code>.yaml with a `meta:` block (see kn.yaml) and run this.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "content" / "locales"
MODEL = "ai4bharat/indictrans2-en-indic-dist-200M"
PLACEHOLDER = re.compile(r"\{(\w+)\}")
KEEP_LATIN = ("STOP", "START", "KVK", "IMD", "CMRI")
# WhatsApp limits: reply button titles 20, list row titles 24, list button 20 characters.
LIMITS = {
    "strings.btn_yes": 20, "strings.btn_no": 20, "strings.btn_outlook": 20, "strings.btn_change_crop": 20,
    "strings.btn_officer": 20, "strings.btn_menu": 20, "strings.lang_list_button": 20,
    "strings.crop_list_button": 20, "strings.btn_add_crop": 20, "strings.other_crop": 24, "strings.pick_block_button": 20, "strings.crop_done": 24,
    "strings.share_again": 24, "strings.menu_footer": 60,
}


def flatten(tree: dict, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in tree.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                out[f"{key}.{i}"] = str(item)
        else:
            out[key] = str(v)
    return out


def protect(text: str) -> str:
    """{name} -> #name and STOP -> #STOP: IndicProcessor swaps #tokens for <ID> tags and restores them."""
    text = PLACEHOLDER.sub(lambda m: f"#{m.group(1)}", text)
    for w in KEEP_LATIN:
        text = re.sub(rf"\b{w}\b", f"#{w}", text)
    return text


def unprotect(text: str, names: set[str]) -> str:
    for w in KEEP_LATIN:
        text = text.replace(f"#{w}", w)
    for n in sorted(names, key=len, reverse=True):
        text = re.sub(rf"#\s*{n}\b", "{" + n + "}", text)
    return text


def tidy(text: str, source: str) -> str:
    """Labels without final punctuation in English lose the full stop / danda the model adds."""
    if not re.search(r"[.?!:]$", source.strip()):
        text = re.sub(r"[\s.।]+$", "", text)
    return text


class Translator:
    def __init__(self) -> None:
        import torch
        from IndicTransToolkit.processor import IndicProcessor
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 2))
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=True).eval()
        self.IP = IndicProcessor

    def __call__(self, sentences: list[str], tgt: str, batch: int = 8, n_best: int = 5) -> list[list[str]]:
        """For each sentence, the model's n best translations, best first."""
        out: list[list[str]] = []
        for i in range(0, len(sentences), batch):
            chunk = sentences[i:i + batch]
            # The processor queues one placeholder map per preprocessed sentence (FIFO), so each sentence's
            # n hypotheses get their own processor holding n copies of that sentence's map.
            pre = self.IP(inference=True).preprocess_batch(chunk, src_lang="eng_Latn", tgt_lang=tgt)
            enc = self.tok(pre, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True)
            with self.torch.no_grad():
                gen = self.model.generate(**enc, use_cache=True, min_length=0, max_length=256, num_beams=n_best,
                                          num_return_sequences=n_best)
            dec = self.tok.batch_decode(gen, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            post = []
            for j in range(len(chunk)):
                ip = self.IP(inference=True)
                ip.preprocess_batch([chunk[j]] * n_best, src_lang="eng_Latn", tgt_lang=tgt)
                post.append(ip.postprocess_batch(dec[j * n_best:(j + 1) * n_best], lang=tgt))
            out += post
            print(f"  {tgt}: {min(i + batch, len(sentences))}/{len(sentences)}", flush=True)
        return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="*")
    ap.add_argument("--force", action="store_true", help="re-translate entries with status machine/needs_fix")
    args = ap.parse_args()

    en = yaml.safe_load((LOCALES / "en.yaml").read_text(encoding="utf-8"))
    source = {}
    for section in ("strings", "templates", "crops"):
        source.update(flatten(en[section], section + "."))

    def check(key: str, mt: str) -> tuple[str, list[str]]:
        names = set(PLACEHOLDER.findall(source[key]))
        cand = tidy(unprotect(mt.strip(), names), source[key])
        probs = []
        if set(PLACEHOLDER.findall(cand)) != names or "#" in cand:
            probs.append("placeholder")
        if key in LIMITS and len(cand) > LIMITS[key]:
            probs.append(f"longer than {LIMITS[key]}")
        return cand, probs
    hints = en.get("mt_hints") or {}

    targets = sorted(p for p in LOCALES.glob("*.yaml") if p.stem != "en" and (not args.langs or p.stem in args.langs))
    if not targets:
        sys.exit("no target locale files")
    translator = Translator()

    for path in targets:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        tgt = doc["meta"]["indictrans"]
        entries: dict = doc.get("entries") or {}
        glossary = flatten(doc.get("glossary") or {})
        todo: list[str] = []
        for key, src in source.items():
            if key in glossary:
                if (entries.get(key) or {}).get("status") not in ("reviewed", "checked"):
                    entries[key] = {"source": src, "text": glossary[key], "status": "glossary"}
                continue
            e = entries.get(key)
            if e and e.get("status") in ("reviewed", "checked", "stale"):
                if e.get("source") != src:
                    e["status"] = "stale"
                continue
            if e and e.get("source") == src and e.get("status") == "machine" and not args.force:
                continue
            todo.append(key)
        for key in list(entries):
            if key not in source:
                del entries[key]
        print(f"{path.stem}: {len(todo)} to translate", flush=True)

        if todo:
            inputs = [protect(hints.get(k, source[k])) for k in todo]
            results = translator(inputs, tgt, n_best=1)
            # Only strings whose best translation fails a check are decoded again for 5 alternatives.
            retry = [i for i, k in enumerate(todo) if check(k, results[i][0])[1]]
            if retry:
                print(f"{path.stem}: {len(retry)} retried with 5-best", flush=True)
                for i, hyps in zip(retry, translator([inputs[i] for i in retry], tgt, batch=4, n_best=5)):
                    results[i] = results[i] + hyps
            for key, hyps in zip(todo, results):
                # First hypothesis that keeps every placeholder and fits the WhatsApp limit wins.
                text, problems = "", ["no hypothesis"]
                for mt in hyps:
                    cand, probs = check(key, mt)
                    if not probs:
                        text, problems = cand, []
                        break
                    if problems == ["no hypothesis"]:
                        text, problems = cand, probs
                if problems:
                    entries[key] = {"source": source[key], "text": "", "status": "needs_fix", "mt": text,
                                    "problem": ", ".join(problems)}
                else:
                    entries[key] = {"source": source[key], "text": text, "status": "machine"}

        doc["entries"] = {k: entries[k] for k in source if k in entries}
        header = (f"# {doc['meta'].get('english_name', path.stem)} strings. Generated by scripts/translate_content.py "
                  f"with {MODEL}.\n# Review each entry, fix `text`, and set `status: reviewed`. "
                  "See the script docstring for statuses.\n")
        path.write_text(header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=1000),
                        encoding="utf-8")
        counts: dict[str, int] = {}
        for e in doc["entries"].values():
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        print(f"{path.stem}: {counts}", flush=True)


if __name__ == "__main__":
    main()
