#!/usr/bin/env python3
"""Coverage-floor gate for CI.

Computes naive token coverage for each dialect and fails (exit 1) if it drops
below a per-dialect floor. This catches regressions where a lexicon/rule edit
silently reduces what the analyser recognises.

Usage:  python3 tests/check-coverage.py
Floors are deliberately set a few points BELOW current measured coverage so
normal work doesn't trip them, but a real regression will.
"""
import os, sys, re, json, subprocess
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
_BUNDLED = os.path.join(HERE, "data")
DATA = _BUNDLED if os.path.isdir(_BUNDLED) else os.path.join(PROJ, "..", "dungan")






FLOOR = {"gan": 68.0, "shaanxi": 68.0}

def load_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)

def corpus_tokens(dialect):





    texts = []
    par = load_json("dungan_parallel.json")
    for r in par["folk_tale"]:         texts.append(r.get("dungan", ""))
    for r in par["poem_shyvaza"]:      texts.append(r.get("dungan", ""))
    for r in par["glossed_sentences"]: texts.append(r.get("dungan", ""))
    wp = load_json("dungan_wikipedia.json")
    for v in wp["cyrillic_articles"].values():
        texts.append(v)
    blob = "\n".join(texts)
    return Counter(re.findall(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+", blob))

def coverage(dialect):
    fst = os.path.join(PROJ, f"dng-{dialect}.automorf.hfst")
    freq = corpus_tokens(dialect)
    uniq = sorted(freq)
    res = subprocess.run(["hfst-lookup", "-q", fst],
                         input="\n".join(uniq) + "\n",
                         capture_output=True, text=True)
    covered = set()
    for line in res.stdout.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[1].endswith("+?"):
            covered.add(parts[0])
    ni = sum(freq.values())
    nci = sum(freq[t] for t in covered)
    return 100.0 * nci / ni if ni else 0.0

def main():
    failed = False
    for dialect, floor in FLOOR.items():
        cov = coverage(dialect)
        status = "OK" if cov >= floor else "FAIL"
        if cov < floor:
            failed = True
        print(f"[{dialect}] token coverage {cov:.1f}%  (floor {floor:.1f}%)  {status}")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
