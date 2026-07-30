#!/usr/bin/env python3
"""Are the corpus-mined lexicon additions what carries held-out coverage?

Usage:  python3 tests/holdout_ablation.py [gan]

The lexicon was grown partly against the development corpus: eleven sublexicons
named Corpus* (in stems/stems-wiktionary.lexc and stems/stems-salmi.lexc) hold
stems added precisely because they turned up as frequent unknowns there. If
held-out coverage rested on those additions, the held-out figures would be
telling us about the development corpus rather than about the language.

This script rebuilds the analyser with every Corpus* entry commented out --- a
real rebuild in a temporary tree, not a simulation --- and re-measures coverage
on the development corpus and on both held-out texts. The comparison separates
the contribution of the corpus-specific additions from that of the lexicon core
(dictionary, Wiktionary, Salmi, names, Swadesh, recovered adjectives).

Each emptied sublexicon keeps one sentinel entry, since hfst-lexc rejects an
empty LEXICON; the sentinel is a string of hard signs that cannot occur in
Dungan text and therefore cannot be recognised.

Requires: hfst tools on PATH, and the held-out texts fetched by
tests/heldout.py (default cache $DNG_HELDOUT_DIR or ./heldout).
No randomness is used anywhere.
"""
import os, re, sys, glob, shutil, tempfile, subprocess
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
dia = sys.argv[1] if len(sys.argv) > 1 else "gan"

WORKDIR  = os.environ.get("DNG_HELDOUT_DIR", "./heldout")
PROV_PDF = os.path.join(WORKDIR, "dungan_sayings.pdf")
OT_GLOB  = os.path.join(WORKDIR, "ot_epub", "xhtml")

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮү]+")
WORDH = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")   # held-out tokenisation
TAG  = re.compile(r"<[^>]+>")
SUP  = re.compile(r"<sup[^>]*>.*?</sup>", re.S)

SENTINEL = "ъъъъъъъъ:ъъъъъъъъ N-NN ;   ! ablation sentinel (unrecognisable by design)\n"
ABLATE_FILES = ("stems/stems-wiktionary.lexc", "stems/stems-salmi.lexc")


def build_ablated(dst):
    shutil.copytree(ROOT, dst, dirs_exist_ok=True)
    for h in glob.glob(os.path.join(dst, "*.hfst")):
        os.remove(h)
    n = 0
    for rel in ABLATE_FILES:
        p = os.path.join(dst, rel)
        out, cur = [], None
        for raw in open(p, encoding="utf-8"):
            s = raw.strip()
            if s.startswith("LEXICON"):
                cur = s.split()[1]
                out.append(raw)
                if cur.startswith("Corpus"):
                    out.append(SENTINEL)
                continue
            code = s.split("!")[0].strip()
            if cur and cur.startswith("Corpus") and code.endswith(";"):
                n += 1
                out.append("! ABLATED: " + raw)
                continue
            out.append(raw)
        open(p, "w", encoding="utf-8").write("".join(out))
    r = subprocess.run(["make", dia], cwd=dst, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ablated build failed:\n" + r.stderr[-2000:])
    return n


def dev_tokens():
    import json
    D = os.path.join(HERE, "data")
    wp = json.load(open(os.path.join(D, "dungan_wikipedia.json"), encoding="utf-8"))
    pa = json.load(open(os.path.join(D, "dungan_parallel.json"), encoding="utf-8"))
    txt = list(wp["cyrillic_articles"].values()) + [
        r.get("dungan", "") for k in ("folk_tale", "poem_shyvaza", "glossed_sentences")
        for r in pa[k]]
    return [t.lower() for t in WORD.findall("\n".join(txt))]


def prov_tokens():
    import fitz
    t = "".join(p.get_text() for p in fitz.open(PROV_PDF))
    return [x.lower() for x in WORDH.findall(t) if len(x) >= 2]


def pent_tokens():
    out = []
    for b in ("Gen", "Exod", "Lev", "Num", "Deut"):
        for f in sorted(glob.glob(os.path.join(OT_GLOB, f"DNG_{b}_*.xhtml"))):
            h = open(f, encoding="utf-8").read()
            out += [x.lower() for x in WORDH.findall(TAG.sub(" ", SUP.sub("", h)))
                    if len(x) >= 2]
    return out


def cov(ana, toks):
    f = Counter(toks); ts = sorted(f)
    r = subprocess.run(["hfst-lookup", "-q", ana], input="\n".join(ts) + "\n",
                       capture_output=True, text=True)
    k = {l.split("\t")[0] for l in r.stdout.split("\n")
         if "\t" in l and not l.split("\t")[1].endswith("+?")}
    n = sum(f.values()); c = sum(f[t] for t in ts if t in k)
    return c, n, 100.0 * c / n


def main():
    full = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
    if not os.path.exists(full):
        sys.exit(f"Analyser not built: {full}\nRun: make {dia}")

    corpora = [("development", dev_tokens)]
    for lbl, fn, need in (("proverbs (held out)", prov_tokens, PROV_PDF),
                          ("Pentateuch (held out)", pent_tokens, OT_GLOB)):
        if os.path.exists(need):
            corpora.append((lbl, fn))
        else:
            print(f"  (skipping {lbl}: {need} not present; run tests/heldout.py)")

    tmp = tempfile.mkdtemp(prefix="dng-ablate-")
    try:
        n = build_ablated(tmp)
        abl = os.path.join(tmp, f"dng-{dia}.automorf.hfst")
        print(f"=== HELD-OUT ABLATION [{dia}] ===")
        print(f"corpus-mined stems removed (all Corpus* sublexicons): {n}")
        print()
        print(f"{'corpus':<24}{'full':>16}{'core only':>16}{'delta':>9}")
        for lbl, fn in corpora:
            toks = fn()
            cf, nf, pf = cov(full, toks)
            ca, na, pa_ = cov(abl, toks)
            print(f"{lbl:<24}{pf:>15.1f}%{pa_:>15.1f}%{pa_-pf:>8.1f}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
