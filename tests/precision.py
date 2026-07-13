#!/usr/bin/env python3
"""Precision / correctness evaluation for the Dungan FST.

Unlike coverage.py (which only asks "is the token recognized?"), this asks
"is the CORRECT analysis produced, and how much spurious ambiguity comes with
it?" Gold analyses are annotated from the hanzi in the parallel corpus, which
disambiguates each morpheme.

PROVENANCE / CAVEAT: this gold set was assembled during the project with AI
assistance, NOT by a native speaker or an independent Dungan expert. The hanzi
truth labels and the analyser's stem lexicon both derive largely from the same
Yanshansin dictionary, and the same agent that built the analyser decided the
"correct" reading. So (unlike coverage, measured on external text) this metric
reflects the model's INTERNAL CONSISTENCY, not independently verified
correctness. Independent native-speaker adjudication is future work.

Metrics:
  recall            : fraction of tokens whose correct analysis is in the output
                      (tone-insensitive: a gold reading without <tN> matches an
                      output reading that differs only by a tone tag)
  exact             : fraction matching including tone
  mean_ambiguity    : average number of analyses returned per recognized token
  over_generation   : average number of WRONG extra analyses per token
"""
import re, subprocess, sys

def analyze(form, dialect):
    r = subprocess.run(["hfst-lookup","-q",f"dng-{dialect}.automorf.hfst"],
                       input=form+"\n", capture_output=True, text=True)
    outs=[]
    for line in r.stdout.strip().split("\n"):
        p=line.split("\t")
        if len(p)>=2 and not p[1].endswith("+?"):
            outs.append(p[1])
    return outs

def strip_tone(a): return re.sub(r'<t\d>','',a)

def load_gold(path):
    rows=[]
    for l in open(path,encoding="utf-8"):
        if l.startswith("#") or not l.strip(): continue
        p=l.rstrip("\n").split("\t")
        if len(p)>=2: rows.append((p[0],p[1]))
    return rows

def main():
    dialect = sys.argv[1] if len(sys.argv)>1 else "gan"
    gold = load_gold("tests/gold-precision.txt")
    n=len(gold)
    recall=exact=recognized=0
    total_analyses=0; over=0
    misses=[]
    for tok,gold_a in gold:
        outs=analyze(tok,dialect)
        if outs: recognized+=1
        total_analyses+=len(outs)

        if gold_a in outs: exact+=1

        if any(strip_tone(o)==strip_tone(gold_a) for o in outs):
            recall+=1

            over += sum(1 for o in outs if strip_tone(o)!=strip_tone(gold_a))
        else:
            misses.append((tok,gold_a,outs))
    print(f"[{dialect}] precision evaluation on {n} hand-annotated tokens")
    print(f"  recall (correct reading present): {recall}/{n} = {100*recall/n:.1f}%")
    print(f"  exact (incl. tone)              : {exact}/{n} = {100*exact/n:.1f}%")
    print(f"  recognized (any analysis)       : {recognized}/{n} = {100*recognized/n:.1f}%")
    print(f"  mean analyses per recognized tok: {total_analyses/recognized:.2f}" if recognized else "  (none recognized)")
    print(f"  mean wrong extra readings/tok   : {over/n:.2f}")
    if misses:
        print(f"\n  misses ({len(misses)}):")
        for tok,g,outs in misses:
            print(f"    {tok:12s} want {g}")
            print(f"    {'':12s} got  {outs if outs else '(unrecognized)'}")

    floor=0.90
    if recall/n < floor:
        print(f"\nFAIL: recall {100*recall/n:.1f}% below floor {100*floor:.0f}%")
        sys.exit(1)
    print(f"\nPASS: recall above {100*floor:.0f}% floor")

if __name__=="__main__":
    main()
