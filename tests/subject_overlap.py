#!/usr/bin/env python3
"""How much of the development corpus shares its subject matter with the
held-out texts?

Usage:  python3 tests/subject_overlap.py

The two held-out corpora (folk proverbs, Pentateuch) are publications of the
Institute for Bible Translation, the same publisher as the source dictionary.
"Held out" therefore means "not used during development", not "lexically or
stylistically independent". This script quantifies one measurable part of that
dependency: the share of the development corpus that is itself religious in
subject.

The classification is by article title, made by hand, and shipped in
tests/data/wikipedia_religious_subject.json together with the criterion and an
explicit list of the borderline groups excluded. It is deliberately
conservative -- biblical toponyms, ethnonyms, Roman officials and scriptural
coinage are all left out -- so the figure it reports is a LOWER bound on
subject overlap. Readers who would classify those groups as religious should
read the figure as larger, which strengthens rather than weakens the caveat it
supports.

No randomness is used anywhere.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
WORD = re.compile(r"[А-Яа-яЁёӘәҢңҖҗЎўҮү]+")   # same tokeniser as tests/coverage.py


def main():
    wp = json.load(open(os.path.join(DATA, "dungan_wikipedia.json"),
                        encoding="utf-8"))["cyrillic_articles"]
    spec = json.load(open(os.path.join(DATA, "wikipedia_religious_subject.json"),
                          encoding="utf-8"))
    titles = spec["titles"]

    missing = [t for t in titles if t not in wp]
    if missing:
        raise SystemExit("titles not found in the corpus dump: " + ", ".join(missing))

    par = json.load(open(os.path.join(DATA, "dungan_parallel.json"), encoding="utf-8"))
    par_txt = [r.get("dungan", "") for k in ("folk_tale", "poem_shyvaza",
                                             "glossed_sentences") for r in par[k]]

    wiki_tok = sum(len(WORD.findall(v)) for v in wp.values())
    par_tok = len(WORD.findall("\n".join(par_txt)))
    dev_tok = wiki_tok + par_tok
    rel_tok = sum(len(WORD.findall(wp[t])) for t in titles)

    print("=== SUBJECT OVERLAP WITH THE HELD-OUT TEXTS ===")
    print(f"development corpus            : {dev_tok} tokens "
          f"({wiki_tok} Wikipedia + {par_tok} parallel)")
    print(f"articles                      : {len(wp)}")
    print(f"religious in subject           : {len(titles)} articles, {rel_tok} tokens")
    print(f"share of the development corpus: {100*rel_tok/dev_tok:.1f}%  "
          f"(of the Wikipedia part alone: {100*rel_tok/wiki_tok:.1f}%)")
    print()
    print("This is a lower bound; see the '_criterion' field of "
          "tests/data/wikipedia_religious_subject.json for what is excluded.")


if __name__ == "__main__":
    main()
