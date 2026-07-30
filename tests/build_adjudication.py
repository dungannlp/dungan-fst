#!/usr/bin/env python3
"""Build a native-speaker precision-adjudication worksheet.

Why
---
Automated precision (tests/precision.py) is circular: the gold readings derive
from the same Yanshansin dictionary that built the analyzer's stems, so the test
catches implementation bugs but cannot catch errors shared by both sides (a wrong
dictionary entry, or a linguistic decision taken uniformly in lexicon and gold).
Breaking that loop requires a judgment from an independent party — a Dungan
speaker or Dunganologist.

This script produces the instrument for that judgment: a stratified sample of
real word-forms with the analyser's readings and a short context, plus blank
columns for the adjudicator. It deliberately over-samples INFLECTED and
MULTI-READING forms, where correctness is genuinely in question, over bare
dictionary stems (trivially correct, uninformative).

Source text is the Dungan Wikipedia corpus (CC BY-SA), so the worksheet is
freely redistributable. The same procedure can be pointed at held-out text for
double independence (text + judgment); see tests/heldout.py for held-out
sources.

Usage:  python3 tests/build_adjudication.py [gan|shaanxi]
Output: tests/adjudication/precision_worksheet.csv
"""
import sys, os, re, json, csv, subprocess, random
from collections import Counter, defaultdict

random.seed(20260627)
dialect = sys.argv[1] if len(sys.argv) > 1 else "gan"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
analyser = os.path.join(ROOT, f"dng-{dialect}.automorf.hfst")
if not os.path.exists(analyser):
    sys.exit(f"Analyser not built: {analyser}\nRun: make {dialect}")

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")
data = json.load(open(os.path.join(HERE, "data/dungan_wikipedia.json"), encoding="utf-8"))
articles = list(data["cyrillic_articles"].values())
blob = "\n".join(articles)
tokens = [t for t in WORD.findall(blob) if len(t) >= 2]
freq = Counter(t.lower() for t in tokens)

# analyse all distinct forms
forms = sorted(freq)
r = subprocess.run(["hfst-lookup", "-q", analyser],
                   input="\n".join(forms) + "\n", capture_output=True, text=True)
readings = defaultdict(list)
for line in r.stdout.split("\n"):
    if not line.strip():
        continue
    parts = line.split("\t")
    if len(parts) >= 2 and not parts[1].endswith("+?"):
        readings[parts[0]].append(parts[1])

def lemma_of(reading):
    return reading.split("<")[0].split("+")[0]

# Context: the first standalone occurrence in the RAW article text, with
# punctuation and original case preserved (the annotator needs the real
# sentence, not a token soup), and never crossing an article boundary ---
# the naive token-window approach glued the end of one article to the start
# of the next for forms first attested near a boundary.
LETTER = "А-Яа-яЁёӘәҢңҖҗЎўҮүъь"
def context(form):
    pat = re.compile(r"(?<![" + LETTER + r"])" + re.escape(form) + r"(?![" + LETTER + r"])",
                     re.IGNORECASE)
    for art in articles:
        m = pat.search(art)
        if m is None:
            continue
        a, b = max(0, m.start() - 60), min(len(art), m.end() + 60)
        snip = art[a:b]
        if a > 0:                       # snap the left edge to a word boundary
            cut = snip.find(" ")
            if 0 <= cut < 20:
                snip = snip[cut + 1:]
            snip = "…" + snip
        if b < len(art):                # snap the right edge to a word boundary
            cut = snip.rfind(" ")
            if cut > len(snip) - 20:
                snip = snip[:cut]
            snip = snip + "…"
        return " ".join(snip.split())   # collapse newlines and runs of spaces
    # fallback (should not trigger: every sampled form was tokenised from
    # these very articles): token window within the concatenated text
    lower_seq = [t.lower() for t in tokens]
    if form in lower_seq:
        i = lower_seq.index(form)
        return " ".join(tokens[max(0, i - 5):i + 6])
    return ""

# stratify
inflected, multi, bare = [], [], []
for f, rds in readings.items():
    if not rds:
        continue
    is_infl = any(lemma_of(x).lower() != f for x in rds)
    if len(rds) >= 2:
        multi.append(f)
    if is_infl:
        inflected.append(f)
    if not is_infl and len(rds) == 1:
        bare.append(f)

def sample(pool, n):
    pool = [p for p in pool if freq[p] >= 1]
    random.shuffle(pool)
    return pool[:n]

picked, seen = [], set()
for bucket, n in ((inflected, 50), (multi, 30), (bare, 20)):
    added = 0
    for f in sample(bucket, len(bucket)):
        if added >= n:
            break
        if f not in seen:
            seen.add(f); picked.append(f); added += 1
picked = picked[:100]
random.shuffle(picked)

outdir = os.path.join(HERE, "adjudication")
os.makedirs(outdir, exist_ok=True)
path = os.path.join(outdir, "precision_worksheet.csv")

# Build and self-check the rows before writing anything.
rows = []
for i, f in enumerate(picked, 1):
    ctx = context(f)
    rds = list(dict.fromkeys(readings[f]))   # guard against duplicate paths
    assert f in ctx.lower(), f"context lost the form: {f!r}"
    rows.append([i, f, ctx, "  |  ".join(rds), "", ""])
assert len(rows) == 100 and len({r[1] for r in rows}) == 100, "need 100 unique forms"

# utf-8-sig: plain UTF-8 plus a BOM, so spreadsheet software (the likeliest
# tool of a human annotator) decodes the Cyrillic correctly on open.
with open(path, "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["no.", "word form", "context",
                "analyzer readings (all)",
                "correct reading present? (yes/no)",
                "if 'no': correct reading / comment"])
    w.writerows(rows)
print(f"wrote {path}  ({len(rows)} forms; "
      f"inflected/multi/bare pools = {len(inflected)}/{len(multi)}/{len(bare)})")