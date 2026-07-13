#!/usr/bin/env python3
"""Held-out coverage evaluation on Dungan text NOT used in development.

Usage:  python3 tests/heldout.py [gan|shaanxi]

Motivation
----------
Lexicon expansion during development was driven by the SAME corpus on which
coverage is reported (tests/coverage.py), so that figure may be optimistically
biased (the model is partly fit to its own test set). This script measures
coverage on two Dungan texts that were never used in development, to estimate
genuine generalisation.

Held-out texts (Institute for Bible Translation, ibtrussia.org/Dungan/bible;
same translation tradition as the development corpus' Gospel material, but
distinct text). They are fetched at run time and used ONLY to count recognition
statistics; they are not redistributed with this project.
  1. Dungan folk proverbs   (folk/literary register)
  2. Dungan Pentateuch      (Gen–Deut, OT narrative register; glossary excluded)

Reported result (Opus build, this project): token coverage 85.2% (proverbs)
and 79.8% (Pentateuch) for both dialect analysers — both ABOVE the development
corpus (72.6/73.8%), i.e. coverage is not a corpus-fitting artefact. NB: the
registers differ in difficulty, so this validates coverage/generalisation, not
precision (whose circularity is discussed in the paper).

Requires network access and PyMuPDF (`pip install pymupdf`).
"""
import sys, os, re, subprocess, io, zipfile, urllib.request
from collections import Counter

PROV_PDF = "https://ibtrussia.org/sites/default/files/pdf/Dungan_sayings_web_0.pdf"
OT_EPUB  = "https://ibtrussia.org/sites/default/files/ebm/ebook/657c89o2g/dng_cyrillic_compilation.epub"
PENTATEUCH = ("Gen", "Exod", "Lev", "Num", "Deut")

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")
TAG  = re.compile(r"<[^>]+>")
SUP  = re.compile(r"<sup[^>]*>.*?</sup>", re.S)

dialect  = sys.argv[1] if len(sys.argv) > 1 else "shaanxi"
HERE = os.path.dirname(os.path.abspath(__file__))
analyser = os.path.join(os.path.dirname(HERE), f"dng-{dialect}.automorf.hfst")
if not os.path.exists(analyser):
    sys.exit(f"Analyser not built: {analyser}\nRun: make {dialect}")

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read()

def proverbs_tokens():
    import fitz
    doc = fitz.open(stream=fetch(PROV_PDF), filetype="pdf")
    text = "".join(p.get_text() for p in doc)
    return [t.lower() for t in WORD.findall(text) if len(t) >= 2]

def pentateuch_tokens():
    z = zipfile.ZipFile(io.BytesIO(fetch(OT_EPUB)))
    out = []
    for name in z.namelist():
        base = os.path.basename(name)
        if not base.startswith("DNG_") or not base.endswith(".xhtml"):
            continue
        if "glossary" in name or not any(f"DNG_{b}_" in base for b in PENTATEUCH):
            continue
        html = z.read(name).decode("utf-8", "ignore")
        text = TAG.sub(" ", SUP.sub("", html))
        out += [t.lower() for t in WORD.findall(text) if len(t) >= 2]
    return out

def coverage(tokens):
    freq = Counter(tokens); types = sorted(freq)
    r = subprocess.run(["hfst-lookup", "-q", analyser],
                       input="\n".join(types) + "\n", capture_output=True, text=True)
    known = {l.split("\t")[0] for l in r.stdout.split("\n")
             if l.strip() and len(l.split("\t")) >= 2 and not l.split("\t")[1].endswith("+?")}
    tok = sum(freq.values()); ctok = sum(freq[t] for t in types if t in known)
    return ctok, tok, 100 * ctok / tok, sum(1 for t in types if t in known), len(types)

print(f"[{dialect}] held-out coverage (texts never used in development):\n")
for label, getter in (("folk proverbs", proverbs_tokens), ("Pentateuch (Gen-Deut)", pentateuch_tokens)):
    try:
        ctok, tok, pct, ctyp, ntyp = coverage(getter())
        print(f"  {label:24s}  token {ctok}/{tok} = {pct:.1f}%   type {ctyp}/{ntyp} = {100*ctyp/ntyp:.1f}%")
    except Exception as e:
        print(f"  {label:24s}  SKIPPED ({type(e).__name__}: {e})")
print("\n(Compare with development-corpus coverage from `make coverage`: 72.6/73.8%.)")
