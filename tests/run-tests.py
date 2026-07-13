#!/usr/bin/env python3
"""Gold-standard test runner for dng-fst.

Runs tests/gold-analyses.txt and tests/gold-generation.txt against the built
analysers/generators for both dialects. Exits non-zero if any test fails, so
it can gate CI.

Usage:  python3 tests/run-tests.py
Requires: dng-{gan,shaanxi}.{automorf,autogen}.hfst already built (make all).
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)

def lookup(fst, forms):
    """Return {input: set(of outputs)} from hfst-lookup."""
    res = subprocess.run(["hfst-lookup", "-q", os.path.join(PROJ, fst)],
                         input="\n".join(forms) + "\n",
                         capture_output=True, text=True)
    out = {}
    for line in res.stdout.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            inp, res_str = parts[0], parts[1]
            if res_str.endswith("+?"):
                continue
            out.setdefault(inp, set()).add(res_str)
    return out

def load_cases(fname):
    cases = []
    with open(os.path.join(HERE, fname), encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                print(f"  ! malformed line in {fname}: {line!r}")
                continue
            cases.append(tuple(parts))
    return cases

DIALECT_FST = {
    "gan":     {"morf": "dng-gan.automorf.hfst",     "gen": "dng-gan.autogen.hfst"},
    "shaanxi": {"morf": "dng-shaanxi.automorf.hfst", "gen": "dng-shaanxi.autogen.hfst"},
}

def expand_dialects(d):
    return ["gan", "shaanxi"] if d == "both" else [d]

def run_block(title, cases, direction):
    """direction: 'morf' (analyse) or 'gen' (generate)."""

    passed = failed = 0
    failures = []

    by_dialect = {}
    for inp, exp, dia in cases:
        for d in expand_dialects(dia):
            by_dialect.setdefault(d, set()).add(inp)
    results = {}
    for d, forms in by_dialect.items():
        results[d] = lookup(DIALECT_FST[d][direction], sorted(forms))

    for inp, exp, dia in cases:
        for d in expand_dialects(dia):
            got = results[d].get(inp, set())
            if exp in got:
                passed += 1
            else:
                failed += 1
                failures.append((d, inp, exp, sorted(got)))
    print(f"\n=== {title} ===")
    print(f"  passed: {passed}   failed: {failed}")
    for d, inp, exp, got in failures:
        gots = ", ".join(got) if got else "(no analysis)"
        print(f"  FAIL [{d}] {inp!r}")
        print(f"        expected: {exp}")
        print(f"        got     : {gots}")
    return failed

def main():
    total_failed = 0
    ana = load_cases("gold-analyses.txt")
    gen = load_cases("gold-generation.txt")
    total_failed += run_block("ANALYSIS (surface -> analysis)", ana, "morf")
    total_failed += run_block("GENERATION (analysis -> surface)", gen, "gen")

    print("\n" + "=" * 50)
    if total_failed == 0:
        print(f"ALL TESTS PASSED ({len(ana)} analysis + {len(gen)} generation)")
        sys.exit(0)
    else:
        print(f"FAILED: {total_failed} test(s)")
        sys.exit(1)

if __name__ == "__main__":
    main()
