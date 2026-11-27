#!/usr/bin/env python3
"""Quantitative morphological profile of Dungan in running text, measured with
the FST analyser across three registers. Produces the corpus-based numbers that
prose grammars lack: category frequency, productivity (distinct lemmas per
category), inflectional load, cross-register rank stability (Spearman rho with
an exact one-sided permutation p-value), and the structure of morphological
ambiguity.

Usage: python3 tests/morphology_profile.py [gan|shaanxi]

Definitions used here (they are reported in the paper, so they are stated
explicitly rather than left to the reader of the code):

  OVERT   the ten tags that correspond to an overt exponent in the surface
          string: <pl> <gen> <loc> <px> <pst> <prog> <fut> <exp> <comp> <sup>.
          Only these count as "inflection" in the headline load figure.
  ZERO    the five tags the analyser emits with no exponent at all:
          <sg> and the pronominal <pers> <p1> <p2> <p3>. Counting these would
          measure the tagset, not the language; the script reports what they
          would add, so the reader can see the size of the definitional choice.
  LEXFEAT lexical, not inflectional: animacy <an>/<nn> and tone <t1>-<t3>.
          <neg> <incl> <dem> <itg> are likewise lexical (closed-class
          subcategories), and are excluded on the same grounds.

  first-reading   category counted from the FIRST line hfst-lookup returns.
                  All analyses carry weight zero, so this reflects transducer
                  path order, not disambiguation. Reported as the lower bound.
  any-reading     category counted if ANY returned analysis carries it.
                  Reported as the upper bound.

Everything printed by this script is reproducible: no randomness is used
anywhere (the permutation test enumerates all n! permutations exactly for
n <= 10, which is the case for the ten categories of the paper's table).
"""
import sys, os, re, json, glob, subprocess, math
from collections import Counter, defaultdict

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")
TAG = re.compile(r"<[^>]+>")
SUP = re.compile(r"<sup[^>]*>.*?</sup>", re.S)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
dia = sys.argv[1] if len(sys.argv) > 1 else "gan"
ana = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
if not os.path.exists(ana):
    sys.exit(f"Analyser not built: {ana}\nRun: make {dia}")

POS = {"n", "np", "vblex", "adj", "adv", "num", "prn", "post", "part",
       "cnjcoo", "cnjsub", "cls", "cop", "ij"}
LEXFEAT = {"nn", "an", "t1", "t2", "t3", "neg", "incl", "dem", "itg"}
ZERO = {"sg", "pers", "p1", "p2", "p3"}
OVERT = ["gen", "pst", "prog", "fut", "loc", "pl", "px", "exp", "sup", "comp"]
OVERTSET = set(OVERT)

WORKDIR = os.environ.get("DNG_HELDOUT_DIR", "./heldout")
PROV_PDF = os.path.join(WORKDIR, "dungan_sayings.pdf")
OT_GLOB = os.path.join(WORKDIR, "ot_epub/xhtml")


# --------------------------------------------------------------------------
# corpora
# --------------------------------------------------------------------------
def toks_dev():
    d = os.path.join(HERE, "data")
    wp = json.load(open(os.path.join(d, "dungan_wikipedia.json"), encoding="utf-8"))
    pa = json.load(open(os.path.join(d, "dungan_parallel.json"), encoding="utf-8"))
    txt = list(wp["cyrillic_articles"].values()) + [
        r.get("dungan", "") for k in ("folk_tale", "poem_shyvaza", "glossed_sentences")
        for r in pa[k]]
    return [t.lower() for t in WORD.findall("\n".join(txt)) if len(t) >= 2]


def toks_prov():
    import fitz
    t = "".join(p.get_text() for p in fitz.open(PROV_PDF))
    return [x.lower() for x in WORD.findall(t) if len(x) >= 2]


def toks_pent():
    out = []
    for b in ("Gen", "Exod", "Lev", "Num", "Deut"):
        for f in sorted(glob.glob(os.path.join(OT_GLOB, f"DNG_{b}_*.xhtml"))):
            html = open(f, encoding="utf-8").read()
            out += [x.lower() for x in WORD.findall(TAG.sub(" ", SUP.sub("", html)))
                    if len(x) >= 2]
    return out


def analyse(forms):
    r = subprocess.run(["hfst-lookup", "-q", ana],
                       input="\n".join(forms) + "\n", capture_output=True, text=True)
    A = defaultdict(list)
    for ln in r.stdout.split("\n"):
        if not ln.strip():
            continue
        p = ln.split("\t")
        if len(p) >= 2 and not p[1].endswith("+?"):
            A[p[0]].append(p[1])
    return A


def tags_of(a):
    return {t.strip("<>") for t in TAG.findall(a)}


# --------------------------------------------------------------------------
# profile
# --------------------------------------------------------------------------
def profile(tokens, label):
    freq = Counter(tokens)
    forms = sorted(freq)
    A = analyse(forms)
    recog_tok = sum(freq[f] for f in forms if A[f])

    catf = Counter()  # first-reading, overt categories
    catlem = defaultdict(set)
    infl_first = infl_any = infl_unrestricted = 0
    nread = Counter()
    nread_toneblind = Counter()
    nread_lemma = Counter()
    di = Counter()
    ni = Counter()

    for f in forms:
        if not A[f]:
            continue
        w = freq[f]
        first = A[f][0]
        tf = tags_of(first)
        allt = set().union(*[tags_of(a) for a in A[f]])

        if tf & OVERTSET:
            infl_first += w
        if allt & OVERTSET:
            infl_any += w
        # "unrestricted" = any non-POS, non-lexical tag, i.e. ZERO counted too
        if tf & (OVERTSET | ZERO):
            infl_unrestricted += w

        for t in tf & OVERTSET:
            catf[t] += w
            catlem[t].add(first.split("<")[0])

        # ambiguity, three granularities
        nread[min(len(A[f]), 3)] += w
        nread_toneblind[min(len({re.sub(r"<t[123]>", "", a) for a in A[f]}), 3)] += w
        nread_lemma[min(len({a.split("<")[0] for a in A[f]}), 3)] += w

        # clitic ambiguity probes: suffixed forms only (free-standing ди/ни excluded)
        if f.endswith("ди") and len(f) > 2:
            has_gen = any("gen" in tags_of(a) for a in A[f])
            has_prog = any("prog" in tags_of(a) for a in A[f])
            if has_gen and has_prog:
                di["both"] += w
            elif has_gen:
                di["gen"] += w
            elif has_prog:
                di["prog"] += w
            else:
                di["neither"] += w
        if f.endswith("ни") and len(f) > 2:
            has_loc = any("loc" in tags_of(a) for a in A[f])
            has_fut = any("fut" in tags_of(a) for a in A[f])
            if has_loc and has_fut:
                ni["both"] += w
            elif has_loc:
                ni["loc"] += w
            elif has_fut:
                ni["fut"] += w
            else:
                ni["neither"] += w

    return dict(label=label, tok=sum(freq.values()), types=len(forms), recog=recog_tok,
                infl_first=infl_first, infl_any=infl_any,
                infl_unrestricted=infl_unrestricted,
                catf=catf, catlem={k: len(v) for k, v in catlem.items()},
                nread=nread, nread_toneblind=nread_toneblind, nread_lemma=nread_lemma,
                di=di, ni=ni)


# --------------------------------------------------------------------------
# Spearman rho + EXACT one-sided permutation p-value
# --------------------------------------------------------------------------
def avg_ranks(xs):
    """Average (mid-)ranks, descending: largest value gets rank 1."""
    order = sorted(range(len(xs)), key=lambda i: -xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = r
        i = j + 1
    return ranks


def pearson(a, b):
    n = len(a)
    ma = sum(a) / n;
    mb = sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return num / (da * db) if da and db else float("nan")


def spearman_exact(x, y):
    """Spearman rho with ties (Pearson on mid-ranks) and the EXACT one-sided
    permutation p-value P(rho_perm >= rho_obs) over all n! relabellings of one
    rank vector.

    Because both rank vectors are fixed multisets under permutation, their means
    and standard deviations are invariant, so rho is a strictly increasing
    function of the dot product sum_i rx[i]*ry[perm(i)]. Counting permutations
    with rho >= rho_obs therefore reduces to counting permutations whose dot
    product is at least the observed one, which a subset DP does exactly in
    milliseconds instead of enumerating 10! assignments one by one.
    """
    rx, ry = avg_ranks(x), avg_ranks(y)
    rho = pearson(rx, ry)
    n = len(rx)
    if n > 12:
        return rho, None, None
    # mid-ranks are multiples of 0.5; double them so all dot products are ints
    ix = [int(round(2 * v)) for v in rx]
    iy = [int(round(2 * v)) for v in ry]
    target = sum(a * b for a, b in zip(ix, iy))
    dp = {0: {0: 1}}
    for mask in range(1 << n):
        cur = dp.get(mask)
        if not cur:
            continue
        k = bin(mask).count("1")
        if k == n:
            continue
        a = ix[k]
        for j in range(n):
            if mask & (1 << j):
                continue
            nm = mask | (1 << j)
            add = a * iy[j]
            tgt = dp.setdefault(nm, {})
            for s, c in cur.items():
                tgt[s + add] = tgt.get(s + add, 0) + c
        dp[mask] = None
    full = dp[(1 << n) - 1]
    tot = sum(full.values())
    ge = sum(c for s, c in full.items() if s >= target)
    return rho, ge / tot, tot


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
regs = [("encyclopaedic", toks_dev)]
if os.path.exists(PROV_PDF):
    regs.append(("folkloric", toks_prov))
else:
    print(f"[skip] proverbs: {PROV_PDF} not found — run tests/heldout.py or set DNG_HELDOUT_DIR")
if os.path.isdir(OT_GLOB):
    regs.append(("narrative", toks_pent))
else:
    print(f"[skip] Pentateuch: {OT_GLOB} not found — run tests/heldout.py or set DNG_HELDOUT_DIR")

results = [profile(g(), l) for l, g in regs]

print(f"\n=== MORPHOLOGICAL PROFILE [{dia}] ===")
print(f"{'register':16s} {'tokens':>8s} {'types':>7s} {'recog%':>8s} "
      f"{'overt-first':>12s} {'overt-any':>10s} {'unrestricted':>13s} {'zero adds':>10s}")
for r in results:
    f1 = 100 * r['infl_first'] / max(1, r['recog'])
    fa = 100 * r['infl_any'] / max(1, r['recog'])
    fu = 100 * r['infl_unrestricted'] / max(1, r['recog'])
    print(f"{r['label']:16s} {r['tok']:>8d} {r['types']:>7d} "
          f"{100 * r['recog'] / r['tok']:>7.1f}% {f1:>11.1f}% {fa:>9.1f}% "
          f"{fu:>12.1f}% {fu - f1:>9.1f}")

print("\n--- category: % of recognised tokens (first reading) / distinct lemmas ---")
print("category".ljust(10) + "".join(f"{r['label'][:9]:>16s}" for r in results))
for c in OVERT:
    row = c.ljust(10)
    for r in results:
        pct = 100 * r['catf'].get(c, 0) / max(1, r['recog'])
        row += f"{pct:>9.2f}%/{r['catlem'].get(c, 0):<5d}"
    print(row)

print("\n--- cross-register rank stability (Spearman rho over the 10 overt categories) ---")
print("    exact one-sided permutation p over all 10! = 3,628,800 relabellings")
for i in range(len(results)):
    for j in range(i + 1, len(results)):
        a = [results[i]['catf'].get(c, 0) / max(1, results[i]['recog']) for c in OVERT]
        b = [results[j]['catf'].get(c, 0) / max(1, results[j]['recog']) for c in OVERT]
        rho, p, tot = spearman_exact(a, b)
        ps = f"p = {p:.4f} (exact, {tot:,} perms)" if p is not None else "p n/a"
        print(f"    {results[i]['label']:14s} vs {results[j]['label']:14s} "
              f"rho = {rho:.3f}   {ps}")

print("\n--- ambiguity: analyses per recognised token (token-weighted) ---")
for r in results:
    tot = sum(r['nread'].values())


    def pct(d, k): return 100 * d.get(k, 0) / max(1, sum(d.values()))


    print(f"  {r['label']:14s} 1: {pct(r['nread'], 1):5.1f}%  2: {pct(r['nread'], 2):5.1f}%  "
          f"3+: {pct(r['nread'], 3):5.1f}%   "
          f"| tone-blind 1: {pct(r['nread_toneblind'], 1):5.1f}%  "
          f"| lemma-only 1: {pct(r['nread_lemma'], 1):5.1f}%")

print("\n--- clitic ambiguity (suffixed forms only; free-standing ди/ни excluded) ---")
for r in results:
    dt = sum(r['di'].values())
    nt = sum(r['ni'].values())
    print(f"  {r['label']:14s} -ди {dt:5d} tok: both {100 * r['di'].get('both', 0) / max(1, dt):5.1f}%  "
          f"gen-only {100 * r['di'].get('gen', 0) / max(1, dt):5.1f}%  "
          f"prog-only {100 * r['di'].get('prog', 0) / max(1, dt):5.1f}%  "
          f"neither {100 * r['di'].get('neither', 0) / max(1, dt):5.1f}%")
    print(f"  {'':14s} -ни {nt:5d} tok: both {100 * r['ni'].get('both', 0) / max(1, nt):5.1f}%  "
          f"loc-only {100 * r['ni'].get('loc', 0) / max(1, nt):5.1f}%  "
          f"fut-only {100 * r['ni'].get('fut', 0) / max(1, nt):5.1f}%  "
          f"neither {100 * r['ni'].get('neither', 0) / max(1, nt):5.1f}%")
