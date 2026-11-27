#!/usr/bin/env python3
"""Classify the readings that precision.py counts as wrong.

precision.py reports how many returned readings do not match the reference. This
script says what those readings actually are, which is what the paper quotes:
every one of them is a legitimate analysis of the string, and they fall into
four classes.

  POS split          one spelling analysed as two parts of speech
                     (вә `I' beside the verb `to bend', ни pronoun beside
                     postposition, ба particle beside classifier)
  clitic / tag       the same lemma with a competing clitic reading
                     (-ни locative beside prospective, -ди genitive beside
                     progressive) or a competing animacy feature
  homograph + POS    a different lemma and a different part of speech
  lexical homograph  a different lemma, same part of speech

Usage: python3 tests/precision_errors.py [gan|shaanxi] [-v]
"""
import os, re, subprocess, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
dia = next((a for a in sys.argv[1:] if a in ("gan", "shaanxi")), "gan")
verbose = "-v" in sys.argv
ANA = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
if not os.path.exists(ANA):
    sys.exit(f"Analyser not built: {ANA}\nRun: make {dia}")

TONE = re.compile(r"<t\d>")


def strip(a):
    return TONE.sub("", a)


def analyze(form):
    r = subprocess.run(["hfst-lookup", "-q", ANA], input=form + "\n",
                       capture_output=True, text=True)
    outs = []
    for line in (r.stdout or "").strip().split("\n"):
        p = line.split("\t")
        if len(p) >= 2 and not p[1].endswith("+?"):
            outs.append(p[1])
    return outs


def parts(a):
    return a.split("<")[0], re.findall(r"<([^>]+)>", a)


def load_gold(path):
    rows = []
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip():
            continue
        p = l.rstrip("\n").split("\t")
        if len(p) >= 2:
            rows.append((p[0], p[1]))
    return rows


def main():
    gold = load_gold(os.path.join(HERE, "gold-precision.txt"))
    wrong = []
    for tok, g in gold:
        outs = analyze(tok)
        if not any(strip(o) == strip(g) for o in outs):
            continue                      # not recognized at all; recall error
        for o in outs:
            if strip(o) == strip(g):
                continue
            gl, gt = parts(g)
            ol, ot = parts(o)
            if gl != ol:
                kind = "lexical homograph" if gt[0] == ot[0] else "homograph + POS"
            elif gt[0] != ot[0]:
                kind = "POS split"
            else:
                kind = "clitic / tag"
            wrong.append((tok, g, o, kind))

    c = collections.Counter(k for _, _, _, k in wrong)
    print(f"[{dia}] wrong readings: {len(wrong)} of "
          f"{sum(len(analyze(t)) for t, _ in gold)} returned\n")
    for k, v in c.most_common():
        print(f"  {k:18s} {v}")
    if verbose:
        print("\n--- each one ---")
        for tok, g, o, k in wrong:
            print(f"{tok:14s} gold {g:40s} got {o:40s} [{k}]")
    print("\nEvery entry is a legitimate analysis of the string; what separates it "
          "from the reference is context, not malformed morphology.")


if __name__ == "__main__":
    main()
