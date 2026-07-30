#!/usr/bin/env python3
"""What are the analyser's recognition failures made of?

Usage:  python3 tests/failure_typology.py [gan|shaanxi]

Coverage counts recognitions; on its own it cannot support the claim that the
grammatical core is closed, because a high coverage figure is equally
consistent with a large lexicon and an incomplete marker inventory. The claim
is about what the FAILURES are made of, so this script measures that.

For every unrecognised token we ask whether stripping a candidate affix leaves
a form the analyser recognises, and classify the failure, IN THIS ORDER:

  (A) morphotactic gap    -- reachable by morphology the model already
                             implements: the residue after stripping one of the
                             analyser's own surface exponents is recognised.
  (B) deferred phenomenon -- reachable by a documented phenomenon the model
                             deliberately does not implement: past habitual
                             -лэ (and -дилэ), erization -р, derivational -зы.
  (C) reduplication       -- the form is XX with X recognised.
  (D) lexical gap         -- none of the above; the stem itself is unknown.

(A)-(C) are UPPER BOUNDS: a string ending in -лэ need not contain the marker,
and a residue that happens to be a word need not be the actual stem. That is
the direction the argument needs -- it inflates everything except (D), so the
(D) share reported here is a lower bound on the true lexical share.

The (A) exponent inventory is not hand-written: it is parsed out of the lexc
sources, from every entry whose UPPER side is tag-only (a morphotactic
transition) and whose LOWER side is a non-empty affix string. So it tracks the
grammar automatically and cannot drift from it.

Figures are TOKEN-WEIGHTED over the same three registers as
tests/morphology_profile.py. No randomness is used anywhere.
"""
import sys, os, re, json, glob, subprocess
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

dia = sys.argv[1] if len(sys.argv) > 1 else "gan"
ana = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
if not os.path.exists(ana):
    sys.exit(f"Analyser not built: {ana}\nRun: make {dia}")

sys.path.insert(0, HERE)
from ablation import LEXC, strip_comment, unescape, split_colon  # shared lexc parsing

WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮүъь]+")
TAG  = re.compile(r"<[^>]+>")
SUP  = re.compile(r"<sup[^>]*>.*?</sup>", re.S)

WORKDIR  = os.environ.get("DNG_HELDOUT_DIR", "./heldout")
PROV_PDF = os.path.join(WORKDIR, "dungan_sayings.pdf")
OT_GLOB  = os.path.join(WORKDIR, "ot_epub/xhtml")

# Documented but deliberately unimplemented (Section "Modelled Morphology").
DEFERRED = ["дилэ", "лэ", "зы", "р"]


# --------------------------------------------------------------------------
# the analyser's own surface exponents, read out of the lexc sources
# --------------------------------------------------------------------------
def implemented_affixes():
    aff = set()
    in_lex = False
    for rel in LEXC:
        for raw in open(os.path.join(ROOT, rel), encoding="utf-8"):
            line = strip_comment(raw).strip()
            if not line:
                continue
            if line.startswith("LEXICON"):
                in_lex = True; continue
            if line.startswith("Multichar_Symbols"):
                in_lex = False; continue
            if not in_lex or not line.endswith(";"):
                continue
            parts = line[:-1].strip().rsplit(None, 1)
            if len(parts) != 2:
                continue
            pair = parts[0].strip()
            if not pair.startswith("%<"):
                continue                      # not a morphotactic transition
            up, lo = split_colon(pair)
            if lo is None:
                continue
            s = unescape(lo).strip()
            s = s.lstrip("+>").replace("+", "").replace(">", "")
            if s and WORD.fullmatch(s.lower()):
                aff.add(s.lower())
    return sorted(aff, key=len, reverse=True)


# --------------------------------------------------------------------------
# corpora (identical loaders to tests/morphology_profile.py)
# --------------------------------------------------------------------------
def toks_dev():
    wp = json.load(open(os.path.join(DATA, "dungan_wikipedia.json"), encoding="utf-8"))
    pa = json.load(open(os.path.join(DATA, "dungan_parallel.json"), encoding="utf-8"))
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


def recognised(forms):
    """Set of forms the analyser returns at least one non-'+?' analysis for."""
    if not forms:
        return set()
    r = subprocess.run(["hfst-lookup", "-q", ana],
                       input="\n".join(forms) + "\n", capture_output=True, text=True)
    ok = set()
    for ln in r.stdout.split("\n"):
        if not ln.strip():
            continue
        p = ln.split("\t")
        if len(p) >= 2 and not p[1].endswith("+?"):
            ok.add(p[0])
    return ok


MINSTEM = 2   # a residue shorter than this is not a plausible Dungan stem


def classify(register_tokens, label, affixes, out):
    freq = Counter(register_tokens)
    types = sorted(freq)
    known = recognised(types)
    unk = [t for t in types if t not in known]
    unk_tok = sum(freq[t] for t in unk)

    # one batched lookup over every candidate residue
    cand = set()
    for t in unk:
        for a in affixes + DEFERRED:
            if t.endswith(a) and len(t) - len(a) >= MINSTEM:
                cand.add(t[: len(t) - len(a)])
        if len(t) % 2 == 0 and len(t) >= 2 * MINSTEM and t[: len(t) // 2] == t[len(t) // 2:]:
            cand.add(t[: len(t) // 2])
    cand_ok = recognised(sorted(cand))

    cls = Counter()
    members = defaultdict(list)
    for t in unk:
        w = freq[t]
        hit = None
        for a in affixes:                                   # (A)
            if t.endswith(a) and len(t) - len(a) >= MINSTEM and t[: len(t) - len(a)] in cand_ok:
                hit = ("A", a); break
        if hit is None:
            for a in DEFERRED:                              # (B)
                if t.endswith(a) and len(t) - len(a) >= MINSTEM and t[: len(t) - len(a)] in cand_ok:
                    hit = ("B", a); break
        if hit is None:                                     # (C)
            h = len(t) // 2
            if len(t) % 2 == 0 and len(t) >= 2 * MINSTEM and t[:h] == t[h:] and t[:h] in cand_ok:
                hit = ("C", "XX")
        if hit is None:
            hit = ("D", "")                                 # (D)
        cls[hit[0]] += w
        members[hit[0]].append((w, t, hit[1]))

    out[label] = (unk_tok, cls, members, freq, known)
    return unk_tok, cls, members


def main():
    affixes = implemented_affixes()
    print(f"=== FAILURE TYPOLOGY [{dia}] ===")
    print(f"implemented surface exponents used for (A) ({len(affixes)}): "
          + " ".join(affixes))
    print(f"deferred exponents used for (B): " + " ".join(DEFERRED))
    print()

    regs = [("encyclopaedic", toks_dev)]
    for lbl, fn, need in (("folkloric", toks_prov, PROV_PDF),
                          ("narrative", toks_pent, OT_GLOB)):
        if os.path.exists(need):
            regs.append((lbl, fn))
        else:
            print(f"  (skipping {lbl}: {need} not present; run tests/heldout.py)")

    out = {}
    rows = []
    for lbl, fn in regs:
        toks = fn()
        unk_tok, cls, members = classify(toks, lbl, affixes, out)
        rows.append((lbl, len(toks), unk_tok, cls))

    print(f"{'register':<16}{'tokens':>9}{'unrecog':>9}{'(A) morphot':>13}"
          f"{'(B) deferred':>14}{'(C) redup':>11}{'(D) lexical':>13}")
    for lbl, n, u, c in rows:
        pc = lambda k: (100.0 * c[k] / u) if u else 0.0
        print(f"{lbl:<16}{n:>9}{u:>9}{pc('A'):>12.1f}%{pc('B'):>13.1f}%"
              f"{pc('C'):>10.1f}%{pc('D'):>12.1f}%")

    print("\n--- (A) work-list: most frequent failures the grammar could already reach ---")
    for lbl, n, u, c in rows:
        ms = sorted(out[lbl][2]["A"], reverse=True)[:12]
        print(f"  {lbl:<14}" + ", ".join(f"{t} (-{a}, {w})" for w, t, a in ms))

    print("\n--- (B)/(C) work-list ---")
    for lbl, n, u, c in rows:
        for k in ("B", "C"):
            ms = sorted(out[lbl][2][k], reverse=True)[:8]
            if ms:
                print(f"  {lbl:<14}({k}) " + ", ".join(f"{t} ({w})" for w, t, a in ms))

    print("\n--- (D) work-list: most frequent purely lexical gaps ---")
    for lbl, n, u, c in rows:
        ms = sorted(out[lbl][2]["D"], reverse=True)[:12]
        print(f"  {lbl:<14}" + ", ".join(f"{t} ({w})" for w, t, a in ms))

    # The specific sub-case the paper singles out: aspect clitics on adjectives.
    print("\n--- (A) residues that are adjectives (predicative aspect clitics) ---")
    for lbl, n, u, c in rows:
        ms = out[lbl][2]["A"]
        res = sorted({t[: len(t) - len(a)] for w, t, a in ms if a in ("ли", "ни")})
        if not res:
            print(f"  {lbl:<14}(none)"); continue
        r = subprocess.run(["hfst-lookup", "-q", ana],
                           input="\n".join(res) + "\n", capture_output=True, text=True)
        adj = {ln.split("\t")[0] for ln in r.stdout.split("\n")
               if "\t" in ln and "<adj>" in ln.split("\t")[1]}
        sel = [(w, t, a) for w, t, a in ms
               if a in ("ли", "ни") and t[: len(t) - len(a)] in adj]
        tot = sum(w for w, _, _ in sel)
        top = ", ".join(t for w, t, a in sorted(sel, reverse=True)[:8])
        print(f"  {lbl:<14}{tot} tokens / {len(sel)} types: {top}")


if __name__ == "__main__":
    main()
