#!/usr/bin/env python3
"""Quantitative morphological profile of Dungan in running text, measured with
the FST analyser across three registers. Produces the corpus-based numbers that
prose grammars lack: category frequency, productivity (distinct lemmas per
category), inflectional load, and the structure of morphological ambiguity.

Usage: python3 tests/morphology_profile.py [gan|shaanxi]
"""
import sys, os, re, json, glob, subprocess
from collections import Counter, defaultdict
WORD=re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+"); TAG=re.compile(r"<[^>]+>"); SUP=re.compile(r"<sup[^>]*>.*?</sup>",re.S)
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
dia=sys.argv[1] if len(sys.argv)>1 else "gan"; ana=os.path.join(ROOT,f"dng-{dia}.automorf.hfst")
POS={"n","np","vblex","adj","adv","num","prn","post","part","cnjcoo","cnjsub","cls","cop","ij"}
LEXFEAT={"nn","an","t1","t2","t3"}
WORKDIR=os.environ.get("DNG_HELDOUT_DIR","/home/claude/work")
PROV_PDF=os.path.join(WORKDIR,"dungan_sayings.pdf"); OT_GLOB=os.path.join(WORKDIR,"ot_epub/xhtml")
def toks_dev():
    d=os.path.join(HERE,"data"); wp=json.load(open(os.path.join(d,"dungan_wikipedia.json"),encoding="utf-8")); pa=json.load(open(os.path.join(d,"dungan_parallel.json"),encoding="utf-8"))
    txt=list(wp["cyrillic_articles"].values())+[r.get("dungan","") for k in("folk_tale","poem_shyvaza","glossed_sentences") for r in pa[k]]
    return [t.lower() for t in WORD.findall("\n".join(txt)) if len(t)>=2]
def toks_prov():
    import fitz; t="".join(p.get_text() for p in fitz.open(PROV_PDF)); return [x.lower() for x in WORD.findall(t) if len(x)>=2]
def toks_pent():
    out=[]
    for b in ("Gen","Exod","Lev","Num","Deut"):
        for f in glob.glob(os.path.join(OT_GLOB, f"DNG_{b}_*.xhtml")):
            out+= [x.lower() for x in WORD.findall(TAG.sub(" ",SUP.sub("",open(f,encoding="utf-8").read()))) if len(x)>=2]
    return out
def analyse(forms):
    r=subprocess.run(["hfst-lookup","-q",ana],input="\n".join(forms)+"\n",capture_output=True,text=True)
    A=defaultdict(list)
    for ln in r.stdout.split("\n"):
        if not ln.strip(): continue
        p=ln.split("\t")
        if len(p)>=2 and not p[1].endswith("+?"): A[p[0]].append(p[1])
    return A
def profile(tokens,label):
    freq=Counter(tokens); forms=sorted(freq); A=analyse(forms)
    recog_tok=sum(freq[f] for f in forms if A[f])
    catf=Counter(); catlem=defaultdict(set); infl_tok=0; nreadings=Counter(); di_split=Counter(); ni_split=Counter()
    for f in forms:
        if not A[f]: continue
        w=freq[f]; nreadings[min(len(A[f]),4)]+=w
        first=A[f][0]; lemma=first.split("<")[0]
        tags_first={t.strip("<>") for t in TAG.findall(first)}
        if tags_first & (set().union(*[{t.strip('<>') for t in TAG.findall(a)} for a in A[f]]) - POS - LEXFEAT):
            infl_tok+=w

        for t in tags_first:
            if t in POS or t in LEXFEAT: continue
            catf[t]+=w; catlem[t].add(lemma)

        if f.endswith("ди"):
            rd={tuple(sorted({x.strip('<>') for x in TAG.findall(a)} - POS - LEXFEAT)) for a in A[f]}
            for tagset in rd:
                if "gen" in tagset: di_split["→gen"]+=w; break
            else: di_split["→other"]+=w
        if f.endswith("ни"):
            rd=[{x.strip('<>') for x in TAG.findall(a)} for a in A[f]]
            if any("loc" in s for s in rd): ni_split["→loc(+other)"]+=w
            else: ni_split["→other"]+=w
    return dict(label=label, tok=sum(freq.values()), recog=recog_tok, infl=infl_tok,
               catf=catf, catlem={k:len(v) for k,v in catlem.items()}, nreadings=nreadings,
               di=di_split, ni=ni_split)

regs=[("dev (encyclopedic)",toks_dev)]
if os.path.exists(PROV_PDF): regs.append(("proverbs (folk)",toks_prov))
else: print(f"[skip] proverbs: {PROV_PDF} not found — run tests/heldout.py or set DNG_HELDOUT_DIR")
if os.path.isdir(OT_GLOB): regs.append(("Pentateuch (OT narr.)",toks_pent))
else: print(f"[skip] Pentateuch: {OT_GLOB} not found — run tests/heldout.py or set DNG_HELDOUT_DIR")
results=[profile(g(),l) for l,g in regs]
print(f"\n=== MORPHOLOGICAL PROFILE [{dia}] ===")
print(f"{'register':24s} {'tokens':>8s} {'recog%':>7s} {'inflected% of recog':>20s}")
for r in results:
    print(f"{r['label']:24s} {r['tok']:>8d} {100*r['recog']/r['tok']:>6.1f}% {100*r['infl']/max(1,r['recog']):>18.1f}%")
print("\n--- category frequency (% of recognized tokens bearing the tag) | productivity (distinct lemmas) ---")
cats=["pst","prog","fut","pl","gen","loc","comp","sup","sg","px","pers"]
hdr="category".ljust(8)+"".join(f"{r['label'].split()[0]:>14s}" for r in results)
print(hdr)
for c in cats:
    row=c.ljust(8)
    for r in results:
        pct=100*r['catf'].get(c,0)/max(1,r['recog']); lem=r['catlem'].get(c,0)
        row+=f"{pct:>7.1f}%/{lem:<5d}"
    print(row)
print("\n--- ambiguity: #analyses per recognized token (token-weighted, dev) ---")
r=results[0]; tot=sum(r['nreadings'].values())
for k in sorted(r['nreadings']): print(f"   {k}{'+' if k==4 else ' '} analyses: {100*r['nreadings'][k]/tot:5.1f}%")
print("\n--- suffix ambiguity (dev) ---")
print(f"   -ди forms: →has-genitive-reading {r['di'].get('→gen',0)} tok vs →other-only {r['di'].get('→other',0)} tok")
print(f"   -ни forms: →has-locative-reading {r['ni'].get('→loc(+other)',0)} tok vs →other-only {r['ni'].get('→other',0)} tok")
