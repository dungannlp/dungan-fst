#!/usr/bin/env python3
"""Word-list ablation: how much of the analyser's coverage is due to the
modelled morphology, and how much to the lexicon alone?

Usage:  python3 tests/ablation.py [gan|shaanxi]

For an isolating language a bare word list is already a strong baseline, so a
coverage figure on its own does not show that modelling morphotactics bought
anything. This script builds that baseline explicitly. It parses the SURFACE
(lower) side of every stem entry of the dialect's lexc source set -- the same
files the Makefile feeds to hfst-lexc -- and matches development-corpus tokens
against that set as plain strings, with no continuation classes, no clitics and
no two-level rules. The difference between that figure and the transducer's
token coverage is the contribution of the modelled morphology.

The baseline is deliberately generous to itself: it is a set of full surface
stems, so any token that IS a stem counts as recognised, exactly as under the
transducer. What it cannot do is recognise a stem plus an affix.

Parsing rules (stated because the stem count is reported in the paper):
  * comments (everything from an unescaped '!') and blank lines are dropped;
  * lines are entries only inside a LEXICON block, and only if they end in ';';
  * an entry 'upper:lower CONT ;' contributes 'lower'; 'form CONT ;' with no
    colon contributes 'form';
  * entries whose upper side is tag-only (starts with the multichar '%<') are
    skipped -- they are morphotactic transitions, not stems;
  * entries whose surface side is empty or contains a morpheme boundary
    ('%>' / '%+') are skipped -- those are affixes, not stems;
  * '%' escapes are removed and the result is lowercased, matching the
    lowercasing the corpus tokenisers apply.

No randomness is used anywhere.
"""
import sys, os, re, json, subprocess
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data")

dia = sys.argv[1] if len(sys.argv) > 1 else "gan"
ana = os.path.join(ROOT, f"dng-{dia}.automorf.hfst")
if not os.path.exists(ana):
    sys.exit(f"Analyser not built: {ana}\nRun: make {dia}")

# The lexc source set, mirroring the Makefile's GAN_LEXC / SHAANXI_LEXC.
COMMON_SET = ["dng-fst.dng.lexc",
              "stems/stems-common.lexc",
              "stems/stems-wiktionary.lexc",
              "stems/stems-salmi.lexc",
              "stems/stems-salmi-dict.lexc",
              "stems/stems-yanshansin.lexc",
              "stems/stems-names.lexc",
              "stems/stems-core-swadesh.lexc",
              "stems/stems-adj-recovered.lexc"]
LEXC = COMMON_SET + [f"stems/stems-{dia}.lexc"]

# Same tokeniser as tests/coverage.py, so the transducer figure printed here is
# identical to the one the coverage gate reports.
WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮү]+")


def strip_comment(line):
    """Drop an lexc comment, respecting '%!' escaping."""
    out = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == "%" and i + 1 < len(line):
            out.append(line[i:i + 2]); i += 2; continue
        if c == "!":
            break
        out.append(c); i += 1
    return "".join(out)


def unescape(s):
    return re.sub(r"%(.)", r"\1", s)


def split_colon(entry):
    """Split 'upper:lower' on the first UNESCAPED colon."""
    i = 0
    while i < len(entry):
        if entry[i] == "%":
            i += 2; continue
        if entry[i] == ":":
            return entry[:i], entry[i + 1:]
        i += 1
    return entry, None


def surface_stems():
    stems = set()
    in_lexicon = False
    for rel in LEXC:
        path = os.path.join(ROOT, rel)
        for raw in open(path, encoding="utf-8"):
            line = strip_comment(raw).strip()
            if not line:
                continue
            if line.startswith("LEXICON"):
                in_lexicon = True
                continue
            if line.startswith("Multichar_Symbols") or line.startswith("!"):
                in_lexicon = False
                continue
            if not in_lexicon or not line.endswith(";"):
                continue
            body = line[:-1].strip()
            # entry := PAIR CONTINUATION ; -- continuation is the last field
            parts = body.rsplit(None, 1)
            if len(parts) != 2:
                continue
            pair = parts[0].strip()
            if not pair or pair.startswith("%<"):
                continue            # tag-only morphotactic transition
            up, lo = split_colon(pair)
            surf = lo if lo is not None else up
            surf = surf.strip()
            if not surf or "%>" in surf or "%+" in surf:
                continue            # affix, not a stem
            surf = unescape(surf).lower()
            if surf and WORD.fullmatch(surf):
                stems.add(surf)
    return stems


def dev_tokens():
    wp = json.load(open(os.path.join(DATA, "dungan_wikipedia.json"), encoding="utf-8"))
    pa = json.load(open(os.path.join(DATA, "dungan_parallel.json"), encoding="utf-8"))
    txt = list(wp["cyrillic_articles"].values()) + [
        r.get("dungan", "") for k in ("folk_tale", "poem_shyvaza", "glossed_sentences")
        for r in pa[k]]
    return [t.lower() for t in WORD.findall("\n".join(txt))]


def fst_known(types):
    r = subprocess.run(["hfst-lookup", "-q", ana],
                       input="\n".join(types) + "\n", capture_output=True, text=True)
    known = set()
    for ln in r.stdout.split("\n"):
        if not ln.strip():
            continue
        p = ln.split("\t")
        if len(p) >= 2 and not p[1].endswith("+?"):
            known.add(p[0])
    return known


def main():
    stems = surface_stems()
    toks = dev_tokens()
    freq = Counter(toks)
    types = sorted(freq)
    ntok = sum(freq.values())

    known = fst_known(types)
    fst_tok = sum(freq[t] for t in types if t in known)
    base_tok = sum(freq[t] for t in types if t in stems)
    fst_typ = sum(1 for t in types if t in known)
    base_typ = sum(1 for t in types if t in stems)

    print(f"=== WORD-LIST ABLATION [{dia}] ===")
    print(f"surface stem forms parsed from the lexc source set : {len(stems)}")
    print(f"development corpus                                 : "
          f"{ntok} tokens / {len(types)} types")
    print()
    print(f"  stem-list baseline (no morphotactics, no clitics):"
          f"  {base_tok}/{ntok} = {100*base_tok/ntok:.1f}% tokens"
          f"   ({base_typ}/{len(types)} = {100*base_typ/len(types):.1f}% types)")
    print(f"  full transducer                                  :"
          f"  {fst_tok}/{ntok} = {100*fst_tok/ntok:.1f}% tokens"
          f"   ({fst_typ}/{len(types)} = {100*fst_typ/len(types):.1f}% types)")
    print(f"  contribution of the modelled morphology          :"
          f"  {100*(fst_tok-base_tok)/ntok:+.1f} points tokens"
          f"   ({100*(fst_typ-base_typ)/len(types):+.1f} points types)")
    print()
    only_fst = [t for t in types if t in known and t not in stems]
    only_fst.sort(key=lambda t: -freq[t])
    print("  most frequent types the transducer gains over the stem list:")
    print("   ", ", ".join(f"{t} ({freq[t]})" for t in only_fst[:15]))


if __name__ == "__main__":
    main()
