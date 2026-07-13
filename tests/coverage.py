#!/usr/bin/env python3
"""Recognition coverage of the dng-fst analyser against the collected corpus.

Usage:  python3 tests/coverage.py [gan|shaanxi]

Reports type/token recognition coverage for the chosen dialect's analyser,
broken down BY SUB-CORPUS, plus a total and the most frequent unknown tokens
(the lexicon-expansion worklist).

Sub-corpora (all real published Dungan in the Cyrillic standard):
  parallel.folk_tale, parallel.poem_shyvaza -- literary text. Dungan literary
        prose/verse follows the GANSU-BASED literary standard (Iasyr Shyvaza
        poem + a folk tale).
  parallel.glossed   -- the 40 glossed example sentences from the Russian
        Wikipedia article; these lean Shaanxi.
  wikipedia          -- 126 Dungan Wikipedia (Wikimedia Incubator Wp/dng)
        articles; Shaanxi spelling conventions predominate.

DIALECT NOTE: the written literary standard is Gansu-based, but the bulk
Wikipedia corpus leans Shaanxi in spelling. Measuring the Gansu analyser on the
Shaanxi-leaning bulk therefore yields a CROSS-DIALECT LOWER BOUND; the literary
sub-corpora are the more Gansu-representative (if smaller) sample. Both
analysers are now measured on the FULL corpus, so neither dialect's figure is
restricted to the 384 parallel-sentence tokens any longer. A dedicated
Gansu-only bulk corpus is not openly available (the one large Dungan corpus is
PRC-hosted and login-walled; excluded here).
"""
import sys, os, re, json, subprocess
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

dialect = sys.argv[1] if len(sys.argv) > 1 else "shaanxi"
analyser = os.path.join(PROJ, f"dng-{dialect}.automorf.hfst")
if not os.path.exists(analyser):
    sys.exit(f"Analyser not built: {analyser}\nRun: make {dialect}")

def load_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


sub = {}
par = load_json("dungan_parallel.json")
sub["parallel.folk_tale"]    = [r.get("dungan", "") for r in par["folk_tale"]]
sub["parallel.poem_shyvaza"] = [r.get("dungan", "") for r in par["poem_shyvaza"]]
sub["parallel.glossed"]      = [r.get("dungan", "") for r in par["glossed_sentences"]]
try:
    wp = load_json("dungan_wikipedia.json")
    sub["wikipedia"] = list(wp["cyrillic_articles"].values())
except Exception as e:
    print("warn: wikipedia corpus not loaded:", e)

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮү]+")
def toks(texts):
    return [t.lower() for t in WORD.findall("\n".join(texts))]


all_types = sorted({t for texts in sub.values() for t in toks(texts)})
res = subprocess.run(["hfst-lookup", "-q", analyser],
                     input="\n".join(all_types) + "\n",
                     capture_output=True, text=True)
known = set()
for line in res.stdout.split("\n"):
    if not line.strip():
        continue
    p = line.split("\t")
    if len(p) >= 2 and not p[1].endswith("+?"):
        known.add(p[0])

def cov(texts):
    f = Counter(toks(texts))
    ntok = sum(f.values())
    nctok = sum(f[t] for t in f if t in known)
    ntyp = len(f)
    nctyp = sum(1 for t in f if t in known)
    return ntok, nctok, ntyp, nctyp, f


print(f"[{dialect}] recognition coverage by sub-corpus "
      f"(real published Dungan, Cyrillic standard):\n")
print(f"  {'sub-corpus':22s} {'tokens':>7} {'tok-cov':>9}  {'types':>6} {'typ-cov':>9}")
allf = Counter()
for name, texts in sub.items():
    ntok, nctok, ntyp, nctyp, f = cov(texts)
    allf += f
    print(f"  {name:22s} {ntok:7d} {100*nctok/ntok:8.1f}% {ntyp:6d} {100*nctyp/ntyp:8.1f}%")

ntok = sum(allf.values()); nctok = sum(allf[t] for t in allf if t in known)
ntyp = len(allf); nctyp = sum(1 for t in allf if t in known)
print(f"  {'-'*58}")
print(f"  {'TOTAL':22s} {ntok:7d} {100*nctok/ntok:8.1f}% {ntyp:6d} {100*nctyp/ntyp:8.1f}%")

litf = Counter()
for name in ("parallel.folk_tale", "parallel.poem_shyvaza"):
    litf += cov(sub[name])[4]
lt = sum(litf.values()); lc = sum(litf[t] for t in litf if t in known)
print(f"  {'(literary subset)':22s} {lt:7d} {100*lc/lt:8.1f}%"
      f"   <- Gansu-based literary standard")

unknown = [(t, c) for t, c in allf.items() if t not in known]
print(f"\n[{dialect}] top unknown tokens (lexicon-expansion worklist):")
for t, c in sorted(unknown, key=lambda x: -x[1])[:20]:
    print(f"    {c:4d}  {t}")
