"""Reusable POS classifier for Yanshansin glosses.
Key fix: Russian noun phrases put the adjective FIRST ('многоэтажный дом'),
so a naive first-word check misfires. We classify by the gloss's HEAD noun:
if any word in the gloss is a bare noun (not -ть/-ый ending) + the phrase
isn't a pure adjective/verb, treat as noun.
"""
import re

def classify(gloss):
    g = gloss.strip().lower()
    words = re.findall(r'[а-яёә\-]+', g)
    if not words:
        return "n"
    # Single-word glosses: trust the ending
    if len(words) == 1:
        w = words[0]
        if w.endswith(("ость","есть","асть")): return "n"   # abstract-noun suffix, not infinitive
        if w.endswith(("ть","ться","ти")): return "vblex"
        if w.endswith(("ый","ий","ой","ая","ое","ые","ого")): return "adj"
        if w in ("внизу","утром","вместе","также","тоже","почему","зачем",
                 "можно","возможно","нарочно","специально","наверно"): return "adv"
        return "n"
    # Multi-word: if the FIRST word is a verb infinitive, it's a verb
    if words[0].endswith(("ость","есть","асть")): return "n"
    if words[0].endswith(("ть","ться","ти")): return "vblex"
    # If ALL words are adjective-form, it's an adjective
    if all(w.endswith(("ый","ий","ой","ая","ое","ые","ого","енький")) for w in words):
        return "adj"
    # If there's a noun head (a non-adj, non-verb word), it's a noun phrase.
    # Russian: adjective precedes noun, so a trailing non-adjective word = head noun.
    for w in words:
        if not w.endswith(("ый","ий","ой","ая","ое","ые","ого")) \
           and not w.endswith(("ть","ться","ти")):
            return "n"
    return "n"

if __name__ == "__main__":
    tests = [("високосный год","n"),("литературный язык","n"),
             ("многоэтажный дом","n"),("вкусный","adj"),("танцевать плясать","vblex"),
             ("голая степь","n"),("маленький","adj"),("тёща","n")]
    for g,exp in tests:
        got=classify(g)
        print(f"  {'OK ' if got==exp else 'XX '} {g!r} -> {got} (want {exp})")
