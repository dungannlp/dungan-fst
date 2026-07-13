
LEXC      := hfst-lexc
TWOLC     := hfst-twolc
COMPOSE   := hfst-compose-intersect
INVERT    := hfst-invert
FST2FST   := hfst-fst2fst

ROOT      := dng-fst.dng.lexc
COMMON    := stems/stems-common.lexc
CAPS      := caps.hfst

WIK           := stems/stems-wiktionary.lexc
SALMI         := stems/stems-salmi.lexc
SALMIDICT     := stems/stems-salmi-dict.lexc
YAN           := stems/stems-yanshansin.lexc
NAMES         := stems/stems-names.lexc
CORE          := stems/stems-core-swadesh.lexc
GAN_LEXC      := $(ROOT) $(COMMON) $(WIK) $(SALMI) $(SALMIDICT) $(YAN) $(NAMES) $(CORE) stems/stems-gan.lexc
GAN_TWOL      := dng-fst.dng.twol

SHAANXI_LEXC  := $(ROOT) $(COMMON) $(WIK) $(SALMI) $(SALMIDICT) $(YAN) $(NAMES) $(CORE) stems/stems-shaanxi.lexc
SHAANXI_TWOL  := twol/rules-shaanxi.twol

.PHONY: all gan shaanxi test clean
all: gan shaanxi

caps.hfst: caps.regex
	hfst-regexp2fst -S -i caps.regex -o caps.hfst

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

.PHONY: coverage check precision swadesh check-all
test: all
	python3 tests/run-tests.py

coverage: all
	@echo "==== Gansu coverage ===="    ; python3 tests/coverage.py gan
	@echo "==== Shaanxi coverage ===="  ; python3 tests/coverage.py shaanxi

check: all
	python3 tests/check-coverage.py

precision: all
	python3 tests/precision.py gan

swadesh: all
	python3 tests/swadesh.py

check-all: test check precision swadesh
	@echo "All CI checks passed."

clean:
	rm -f *.hfst
