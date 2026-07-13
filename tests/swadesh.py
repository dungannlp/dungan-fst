#!/usr/bin/env python3
"""Core-vocabulary sanity check against the ASJP Swadesh list (CC-BY,
Janšansin & Šinlo 2008 Russian-Dungan dictionary, via asjp.clld.org).

An analyser of a language should recognise its most basic words. This checks
that a recognised Cyrillic form exists for each core concept. It's a coverage
floor on fundamental vocabulary, independent of the corpus-based coverage gate.
"""
import subprocess, sys



CONCEPTS = {
  "I":["вә","ңә"],"you":["ни"],"we":["вәму","заму"],"one":["йи"],"two":["лён","эр"],
  "person":["жын","җын"],"fish":["йүй","йү"],"dog":["гу"],"tree":["шу"],
  "leaf":["езы"],"skin":["пизы","пи"],"blood":["щё"],"horn":["го"],
  "eye":["йәнҗин","нянчин"],"nose":["бизы"],"tooth":["я","ня"],"tongue":["йү"],
  "knee":["щигэзы","щегэзы"],"hand":["шу","шоу"],"liver":["ганзы"],
  "drink":["хә","хо"],"see":["кан","чиэн"],"hear":["тин"],"die":["сы"],
  "come":["лэ"],"sun":["тэён"],"water":["фи","шуй"],"fire":["хуә","хуо"],
  "path":["лу","до"],"mountain":["сан","шан"],"night":["йә","е"],
  "full":["ман","мон"],"new":["щин"],"name":["минзы","мин"],
}

def analyze(form, dialect="shaanxi"):
    r=subprocess.run(["hfst-lookup","-q",f"dng-{dialect}.automorf.hfst"],
                     input=form+"\n",capture_output=True,text=True)
    return [p.split("\t")[1] for p in r.stdout.strip().split("\n")
            if len(p.split("\t"))>=2 and not p.split("\t")[1].endswith("+?")]

def main():
    covered=[c for c,fs in CONCEPTS.items() if any(analyze(f) for f in fs)]
    missing=[c for c in CONCEPTS if c not in covered]
    n=len(CONCEPTS); c=len(covered)
    print(f"Core Swadesh vocabulary: {c}/{n} = {100*c/n:.0f}% of concepts recognised")
    if missing: print(f"  missing: {', '.join(missing)}")
    floor=0.85
    if c/n < floor:
        print(f"FAIL: {100*c/n:.0f}% below {100*floor:.0f}% floor"); sys.exit(1)
    print(f"PASS: above {100*floor:.0f}% floor")

if __name__=="__main__": main()
