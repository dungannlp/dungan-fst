#!/usr/bin/env python3
"""Sensitivity of the morphological profile to the counting rule and to corpus size.

Answers the two reviewer questions the profile alone cannot:

  * does the cross-register *ranking* survive if categories are counted under
    every returned reading instead of the first one?
  * is *productivity* (distinct carrier lemmas) an artefact of corpus size?

For each register it reports, per category: share of recognized tokens under the
FIRST-reading and the ANY-reading rule, distinct carrier lemmas, and lemmas per
10,000 tokens.  It then reports cross-register rank agreement under both rules
(Spearman rho with a permutation p, Kendall tau-b, top-2 / bottom-2 overlap and
the largest rank displacement of a single category), and token-level bootstrap
95% intervals for the load.

Usage: python3 tests/sensitivity.py [gan|shaanxi] [--reps N]

Requires the analyser (`make gan`) and, for the folkloric and narrative
registers, the held-out texts (`make fetch-heldout`).  Deterministic: the
permutation p-value uses a fixed seed, the bootstrap a fixed generator.
"""
import sys, os, re, json, glob, math, random, subprocess
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
dia = next((a for a in sys.argv[1:] if a in ("gan", "shaanxi")), "gan")
reps = 2000
if "--reps" in sys.argv:
    reps = int(sys.argv[sys.argv.index("--reps") + 1])

ANA = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
if not os.path.exists(ANA):
    sys.exit(f"Analyser not built: {ANA}\nRun: make {dia}")

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")
TAG = re.compile(r"<[^>]+>")
SUP = re.compile(r"<sup[^>]*>.*?</sup>", re.S)
OVERT = ["gen", "pst", "prog", "fut", "loc", "pl", "px", "exp", "sup", "comp"]

WORKDIR = os.environ.get("DNG_HELDOUT_DIR", "./heldout")
PROV_PDF = os.path.join(WORKDIR, "dungan_sayings.pdf")
OT_GLOB = os.path.join(WORKDIR, "ot_epub", "xhtml")


def toks_dev():
    d = os.path.join(HERE, "data")
    wp = json.load(open(os.path.join(d, "dungan_wikipedia.json"), encoding="utf-8"))
    pa = json.load(open(os.path.join(d, "dungan_parallel.json"), encoding="utf-8"))
    txt = list(wp["cyrillic_articles"].values()) + [
        r.get("dungan", "") for k in ("folk_tale", "poem_shyvaza", "glossed_sentences")
        for r in pa[k]]
    return [t.lower() for t in WORD.findall("\n".join(txt)) if len(t) >= 2]


def toks_prov():
    if not os.path.exists(PROV_PDF):
        return None
    import fitz
    t = "".join(p.get_text() for p in fitz.open(PROV_PDF))
    return [x.lower() for x in WORD.findall(t) if len(x) >= 2]


def toks_pent():
    if not os.path.isdir(OT_GLOB):
        return None
    out = []
    for b in ("Gen", "Exod", "Lev", "Num", "Deut"):
        for f in sorted(glob.glob(os.path.join(OT_GLOB, f"DNG_{b}_*.xhtml"))):
            html = open(f, encoding="utf-8").read()
            out += [x.lower() for x in WORD.findall(TAG.sub(" ", SUP.sub("", html))) if len(x) >= 2]
    return out


def analyse(forms):
    r = subprocess.run(["hfst-lookup", "-q", ANA], input="\n".join(forms) + "\n",
                       capture_output=True, text=True)
    A = defaultdict(list)
    for ln in (r.stdout or "").split("\n"):
        p = ln.split("\t")
        if len(p) >= 2 and not p[1].endswith("+?"):
            A[p[0]].append(p[1])
    return A


def tags_of(a):
    return {t.strip("<>") for t in TAG.findall(a)}


def stats(tokens):
    freq = Counter(tokens)
    forms = sorted(freq)
    A = analyse(forms)
    rec = {f: A[f] for f in forms if A[f]}
    recog = sum(freq[f] for f in rec)
    row = {"tokens": len(tokens), "recognized": recog, "cat": {}}
    for cat in OVERT:
        first = anyc = 0
        lem_f = set()
        for f, ans in rec.items():
            ts = [tags_of(a) for a in ans]
            if cat in ts[0]:
                first += freq[f]
                lem_f.add(ans[0].split("<")[0])
            if any(cat in t for t in ts):
                anyc += freq[f]
        row["cat"][cat] = {"first": first, "any": anyc,
                           "lemmas": len(lem_f),
                           "per10k": 10000.0 * len(lem_f) / len(tokens)}
    lf = la = 0
    flags_f, flags_a = [], []
    for f, ans in rec.items():
        ts = [tags_of(a) for a in ans]
        one_f = any(c in ts[0] for c in OVERT)
        one_a = any(c in t for t in ts for c in OVERT)
        lf += freq[f] * one_f
        la += freq[f] * one_a
        flags_f += [one_f] * freq[f]
        flags_a += [one_a] * freq[f]
    row["load_first"], row["load_any"] = lf, la
    row["flags"] = {"first": flags_f, "any": flags_a}
    return row


def ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def tau_b(x, y):
    n = len(x)
    conc = disc = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = x[i] - x[j], y[i] - y[j]
            if dx == 0 and dy == 0:
                tx += 1; ty += 1
            elif dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif dx * dy > 0:
                conc += 1
            else:
                disc += 1
    n0 = n * (n - 1) / 2
    den = math.sqrt((n0 - tx) * (n0 - ty))
    return (conc - disc) / den if den else float("nan")


def avg_ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman_exact(x, y):
    """rho with ties, and the exact one-sided permutation p over all n! relabellings.

    Same test as tests/morphology_profile.py, so the two scripts agree to the
    last digit: because rank vectors are fixed multisets under permutation, rho
    is a monotone function of the dot product and the p-value is a subset-DP
    count over 2^n masks rather than an enumeration of 10!.
    """
    rx, ry = avg_ranks(x), avg_ranks(y)
    rho = pearson(rx, ry)
    n = len(rx)
    if n > 12:
        return rho, None
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
            for sm, c in cur.items():
                tgt[sm + add] = tgt.get(sm + add, 0) + c
        dp[mask] = None
    full = dp[(1 << n) - 1]
    ge = sum(c for sm, c in full.items() if sm >= target)
    tot = sum(full.values())
    return rho, ge / tot


def boot_ci(flags, reps):
    """percentile bootstrap over token occurrences (numpy if available)."""
    try:
        import numpy as np
        rng = np.random.default_rng(11)
        a = np.array(flags, dtype=float)
        n = len(a)
        vals = np.empty(reps)
        for i in range(reps):
            vals[i] = a[rng.integers(0, n, n)].mean()
        vals.sort()
        return float(vals[int(0.025 * reps)]), float(vals[int(0.975 * reps)]), reps
    except ImportError:
        rnd = random.Random(11)
        n, reps = len(flags), min(reps, 400)
        vals = []
        for _ in range(reps):
            c = 0
            for _ in range(n):
                if flags[rnd.randrange(n)]:
                    c += 1
            vals.append(c / n)
        vals.sort()
        return vals[int(0.025 * reps)], vals[int(0.975 * reps)], reps


def main():
    regs = {}
    for label, loader in (("encyclopaedic", toks_dev), ("folkloric", toks_prov),
                          ("narrative", toks_pent)):
        t = loader()
        if t is None:
            print(f"  [skip] {label}: held-out texts not fetched "
                  f"(set DNG_HELDOUT_DIR or run make fetch-heldout)")
            continue
        print(f"  {label}: {len(t)} tokens")
        regs[label] = stats(t)
    if not regs:
        sys.exit("nothing to measure")

    labs = list(regs)
    print("\ncategory            " + "".join(f"{l[:12]:>26s}" for l in labs))
    print("                     " + "".join(f"{'first / any  (lem/10k)':>26s}" for l in labs))
    for cat in OVERT:
        line = f"{cat:<20s}"
        for l in labs:
            d = regs[l]["cat"][cat]
            r = regs[l]["recognized"]
            line += f"{100*d['first']/r:8.2f} /{100*d['any']/r:6.2f} ({d['lemmas']:4d}/{d['per10k']:5.1f})"
        print(line)

    print("\n--- load and ambiguity ---")
    for l in labs:
        s = regs[l]
        r = s["recognized"]
        print(f"{l:14s} load first {100*s['load_first']/r:5.1f}%  "
              f"any {100*s['load_any']/r:5.1f}%")

    print("\n--- cross-register rank agreement ---")
    print(f"{'pair':26s} {'rule':5s} {'rho':>6s} {'p':>8s} {'tau':>6s} "
          f"{'top2':>5s} {'bot2':>5s} {'maxmove':>7s}")
    for rule in ("first", "any"):
        for i in range(len(labs)):
            for j in range(i + 1, len(labs)):
                x = [regs[labs[i]]["cat"][c][rule] for c in OVERT]
                y = [regs[labs[j]]["cat"][c][rule] for c in OVERT]
                rho, p = spearman_exact(x, y)
                rx, ry = ranks(x), ranks(y)
                top = sum(1 for a, b in zip(rx, ry) if a <= 2 and b <= 2)
                bot = sum(1 for a, b in zip(rx, ry) if a > len(OVERT) - 2 and b > len(OVERT) - 2)
                mv = max(abs(a - b) for a, b in zip(rx, ry))
                print(f"{labs[i][:12]}-{labs[j][:12]:12s} {rule:5s} {rho:6.3f} {p:8.4f} "
                      f"{tau_b(x, y):6.3f} {top:5d} {bot:5d} {mv:7.1f}")

    if reps:
        print("\n--- bootstrap 95% intervals ---")
        for l in labs:
            for rule in ("first", "any"):
                lo, hi, used = boot_ci(regs[l]["flags"][rule], reps)
                load = regs[l]["load_" + rule] / regs[l]["recognized"]
                print(f"{l:14s} {rule:5s} load {100*load:5.1f}%  "
                      f"CI [{100*lo:5.1f}, {100*hi:5.1f}]  ({used} resamples)")


if __name__ == "__main__":
    main()
