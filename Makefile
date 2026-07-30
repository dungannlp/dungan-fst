# ============================================================================
# Builds TWO dialect analysers from a shared core:
#   dng-gan      Gansu standard (3-tone)   : copula сы, 1sg вә
#   dng-shaanxi  Shaanxi variety (4-tone)  : copula шы, 1sg ңә
#
# Each build = root morphotactics + common stems + ONE dialect stem file,
# composed with that dialect's two-level rules.
#
# Targets:
#   make            build both dialects (analyser + generator, optimised)
#   make gan        build Gansu only
#   make shaanxi    build Shaanxi only
#   make test       gold-standard analysis + generation tests
#   make coverage   print coverage report for both dialects
#   make check      coverage-floor gate
#   make precision  correctness gate (hand-annotated gold, hanzi = truth)
#   make swadesh    core-vocabulary gate (ASJP Swadesh list)
#   make check-all  all of the above (gates CI)
#
# Reported experiments (not gates; these print the figures used in the paper):
#   make ablation         word-list ablation (contribution of the stem lexicon)
#   make profile          morphological profile across the three registers
#   make typology         typology of recognition failures (A/B/C/D)
#   make subject-overlap  religious-subject share of the development corpus
#   make heldout          coverage on the held-out texts (needs make fetch-heldout)
#   make holdout-ablation rebuild without the corpus-mined stems and re-measure
#   make fetch-heldout    alias for `make heldout`, whose first run downloads
#                         the held-out texts into $$DNG_HELDOUT_DIR
#   make adjudication     regenerate the native-speaker precision worksheet
#   make experiments      every experiment above that needs no download
#
#   make clean      remove build artefacts
# ============================================================================

LEXC      := hfst-lexc
TWOLC     := hfst-twolc
COMPOSE   := hfst-compose-intersect
INVERT    := hfst-invert
FST2FST   := hfst-fst2fst

ROOT      := dng-fst.dng.lexc
COMMON    := stems/stems-common.lexc
CAPS      := caps.hfst  # sentence-initial capital folding

# Per-dialect source sets
WIK           := stems/stems-wiktionary.lexc
SALMI         := stems/stems-salmi.lexc
SALMIDICT     := stems/stems-salmi-dict.lexc
YAN           := stems/stems-yanshansin.lexc
NAMES         := stems/stems-names.lexc
CORE          := stems/stems-core-swadesh.lexc
ADJREC        := stems/stems-adj-recovered.lexc
GAN_LEXC      := $(ROOT) $(COMMON) $(WIK) $(SALMI) $(SALMIDICT) $(YAN) $(NAMES) $(CORE) $(ADJREC) stems/stems-gan.lexc
GAN_TWOL      := dng-fst.dng.twol

SHAANXI_LEXC  := $(ROOT) $(COMMON) $(WIK) $(SALMI) $(SALMIDICT) $(YAN) $(NAMES) $(CORE) $(ADJREC) stems/stems-shaanxi.lexc
SHAANXI_TWOL  := twol/rules-shaanxi.twol

.PHONY: all gan shaanxi test clean
all: gan shaanxi

# Sentence-initial capitalization folder (composed before each analyser)
caps.hfst: caps.regex
	hfst-regexp2fst -S -i caps.regex -o caps.hfst

# ---------------------------------------------------------------------------
# Gansu
# ---------------------------------------------------------------------------
gan: dng-gan.automorf.hfst dng-gan.autogen.hfst

dng-gan.lexc.hfst: $(GAN_LEXC)
	cat $(GAN_LEXC) | $(LEXC) -o $@

dng-gan.twol.hfst: $(GAN_TWOL)
	$(TWOLC) $(GAN_TWOL) -o $@

dng-gan.gen.hfst: dng-gan.lexc.hfst dng-gan.twol.hfst
	$(COMPOSE) -1 dng-gan.lexc.hfst -2 dng-gan.twol.hfst -o $@

dng-gan.autogen.hfst: dng-gan.gen.hfst
	$(FST2FST) -O $< -o $@

dng-gan.morph.hfst: dng-gan.gen.hfst
	$(INVERT) $< -o $@

dng-gan.automorf.hfst: dng-gan.morph.hfst $(CAPS)
	hfst-compose $(CAPS) dng-gan.morph.hfst -o dng-gan.capmorph.hfst
	$(FST2FST) -O dng-gan.capmorph.hfst -o $@
	rm -f dng-gan.capmorph.hfst

# ---------------------------------------------------------------------------
# Shaanxi
# ---------------------------------------------------------------------------
shaanxi: dng-shaanxi.automorf.hfst dng-shaanxi.autogen.hfst

dng-shaanxi.lexc.hfst: $(SHAANXI_LEXC)
	cat $(SHAANXI_LEXC) | $(LEXC) -o $@

dng-shaanxi.twol.hfst: $(SHAANXI_TWOL)
	$(TWOLC) $(SHAANXI_TWOL) -o $@

dng-shaanxi.gen.hfst: dng-shaanxi.lexc.hfst dng-shaanxi.twol.hfst
	$(COMPOSE) -1 dng-shaanxi.lexc.hfst -2 dng-shaanxi.twol.hfst -o $@

dng-shaanxi.autogen.hfst: dng-shaanxi.gen.hfst
	$(FST2FST) -O $< -o $@

dng-shaanxi.morph.hfst: dng-shaanxi.gen.hfst
	$(INVERT) $< -o $@

dng-shaanxi.automorf.hfst: dng-shaanxi.morph.hfst $(CAPS)
	hfst-compose $(CAPS) dng-shaanxi.morph.hfst -o dng-shaanxi.capmorph.hfst
	$(FST2FST) -O dng-shaanxi.capmorph.hfst -o $@
	rm -f dng-shaanxi.capmorph.hfst

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Testing
#   make test       gold-standard analysis+generation tests (gates CI)
#   make coverage   print coverage report for both dialects
#   make check      coverage-floor gate (gates CI)
#   make check-all  everything CI runs
# ---------------------------------------------------------------------------
.PHONY: coverage check precision swadesh check-all
test: all
	python3 tests/run-tests.py

coverage: all
	@echo "==== Gansu coverage ===="    ; python3 tests/coverage.py gan
	@echo "==== Shaanxi coverage ===="  ; python3 tests/coverage.py shaanxi

check: all
	python3 tests/check-coverage.py

# Correctness gate: are the right analyses produced (not just any analysis)?
# Scored against hand-annotated gold from the parallel corpus (hanzi = truth).
precision: all
	python3 tests/precision.py gan

# Core-vocabulary gate: does the analyser recognise the most basic words?
# Checked against the ASJP Swadesh list (CC-BY, Janšansin & Šinlo 2008).
swadesh: all
	python3 tests/swadesh.py

check-all: test check precision swadesh
	@echo "All CI checks passed."

# ---------------------------------------------------------------------------
# Reported experiments
#
# These are NOT gates: they print the numbers quoted in the paper and are meant
# to be read, not asserted against. All of them are deterministic --- no
# randomness is used anywhere --- so a rerun on the same tree reproduces the
# published figures exactly.
#
# Which of them need the two held-out texts (third-party publications, fetched
# rather than redistributed; run `make fetch-heldout` once, cache directory
# $DNG_HELDOUT_DIR, default ./heldout):
#
#   ablation, subject-overlap  no  --- fully offline
#   heldout, holdout-ablation  yes --- these ARE the held-out measurements
#   profile, typology          partly --- they run offline but then cover only
#                              the encyclopaedic register and print `[skip]`
#                              for the folkloric and narrative ones. The
#                              three-register figures in the paper need the
#                              fetch.
#
# `make experiments` therefore runs to completion from a clean checkout, but
# reproduces the full published profile/typology tables only after the fetch.
# ---------------------------------------------------------------------------
.PHONY: ablation profile typology subject-overlap heldout holdout-ablation \
        fetch-heldout adjudication experiments

# Word-list ablation: coverage with the stem lexicon reduced to the root
# morphotactics, isolating what the lexicon itself contributes.
ablation: all
	@echo "==== Gansu ===="   ; python3 tests/ablation.py gan
	@echo "==== Shaanxi ====" ; python3 tests/ablation.py shaanxi

# Morphological profile: overt marking, ambiguity and category frequencies
# across the encyclopaedic, folkloric and narrative registers.
profile: all
	python3 tests/morphology_profile.py gan

# What the recognition failures are made of: (A) morphotactic gaps,
# (B) deferred phenomena, (C) reduplication, (D) lexical gaps.
typology: all
	python3 tests/failure_typology.py gan

# Lower bound on the subject-matter overlap between the development corpus and
# the held-out texts. Needs no build and no download.
subject-overlap:
	python3 tests/subject_overlap.py

# Coverage on text not used during development.
heldout: all
	python3 tests/heldout.py gan

# Is held-out coverage carried by the corpus-mined lexicon additions? Rebuilds
# the analyser with every Corpus* sublexicon emptied and re-measures.
holdout-ablation: all
	python3 tests/holdout_ablation.py gan

# tests/heldout.py downloads the two texts into the cache directory on its
# first run, so `make heldout` is itself the fetch step; this target is kept as
# an explicit name for it.
fetch-heldout: heldout

# Stratified worksheet for independent native-speaker adjudication of precision.
adjudication: all
	python3 tests/build_adjudication.py

# Everything that runs to completion from a clean checkout without a download.
# Note that profile and typology cover only the encyclopaedic register until the
# held-out texts have been fetched --- see the note in the header.
experiments: ablation profile typology subject-overlap

clean:
	rm -f *.hfst
