# dng-fst — Dungan morphological transducer

A finite-state morphological analyser/generator for **Dungan** (хуэйзў йүян, 回族語言) [ISO 639-3: `dng`], a Sinitic (Central Plains Mandarin) language of Central Asia written in the **Cyrillic** alphabet. Built with HFST (lexc + twol + composition), the standard open finite-state morphology toolchain.

To our knowledge this is the first finite-state morphology for any Sinitic language written in Cyrillic. (No such analyser exists in the major open minority-language FST collections — Apertium and GiellaLT — where Dungan appears only as a *hypothetical* teaching example.)

## Two dialects, one shared core

Dungan has two literary varieties that differ in regular, documented ways:

| | **Gansu** (standard, 3-tone) | **Shaanxi** (4-tone) |
|---|---|---|
| copula 是 | сы | шы |
| "to be/become" | ви | вый |
| 1sg 我 | вә | ңә |
| 1pl 我們 | вәму | ңәму |
| 1sg poss 俺 | (вәди) | ңэ |
| 3pl 他們 | таму | ана / тана / таму |

The **lexicon and morphotactics are ~90% shared**, so the project is split into a common core plus a thin per-dialect overlay, and builds **two analysers** from overlapping sources:

```
dng-fst.dng.lexc           Root + all morphotactics (continuation classes)
dng-fst.dng.twol           shared two-level rules (Gansu build)
stems/
  stems-common.lexc        hand-built core vocabulary (dialect-neutral)
  stems-wiktionary.lexc    lemmas harvested from en.wiktionary (dialect-neutral)
  stems-salmi.lexc         vocabulary + localizers from Salmi's grammar
  stems-yanshansin.lexc    entries from Yanshansin's Dungan-Russian dictionary
  stems-gan.lexc           Gansu-only forms  (PronDial/CopulaDial/VerbDial/ClsDial)
  stems-shaanxi.lexc       Shaanxi-only forms (incl. ңай, гуə)
twol/
  rules-common.twol        copy of the shared base rules
  rules-shaanxi.twol       shared rules + Shaanxi-only alternations
caps.regex                 sentence-initial capital folder (→ caps.hfst)
tests/
  gold-analyses.txt        gold-standard analysis cases (certain only)
  gold-generation.txt      gold-standard generation cases
  run-tests.py             gold-test runner (gates CI)
  check-coverage.py        coverage-floor gate (gates CI)
  coverage.py              coverage report
  data/                    bundled corpus so CI is self-contained
.github/workflows/ci.yml   GitHub Actions: build + test both dialects
Makefile                   builds dng-gan.* and dng-shaanxi.*
```

`Root` references three **dialect hooks** — `PronDial`, `CopulaDial`,
`VerbDial` — which are *defined only* in the per-dialect stem file. The Makefile
concatenates `root + common + one dialect file` and pipes to `hfst-lexc`
(which merges same-named sublexicons), composing with that dialect's twol.

## Morphology modelled

Dungan is highly **analytic** — almost no inflection; grammar is carried by separable particles and word order. What the transducer covers:

- **Animate plural** `-му` (們): `жын` → `жынму` `жын<n><an><pl>`
- **Possessive/genitive** `-ди` (的): `вә` → `вәди` `<prn>…<px>`
- **Verbal aspect** particles (Salmi 1984; Драгунов analysis), cliticised:
  `-ли` perfective (哩/了), `-дини`/`-ди` progressive (底呢/底), `-ни`
  prospective (呢), `-гуə` experiential (過):
  `чы` → `чыли` `чы<vblex><pst>`, `чыгуə` `чы<vblex><exp>`
- **Localizers** (Salmi 3.1.2), disyllabic ones take optional `-ди`:
  `либян` `<loc>`, `либянди` `<loc><gen>`
- **Adjective intensifier** `-дихын` (得很): `да` → `дадихын` `да<adj><advl>`
- **Numeral + classifier** compounds: `сан`+`гә` → `сангә` `сан<num><cls>`
- Closed classes fully enumerated: pronouns, demonstratives, interrogatives,
  classifiers, postpositions/localizers, conjunctions, particles, copula.

Boundary symbols `%>` (affix) and `%+` (clitic) are deleted on the surface by twol, so the analyser round-trips: it both analyses and **generates**.

**Sentence-initial capitalization** is handled by a small case-folding transducer (`caps.regex` → `caps.hfst`) composed before each analyser, so `Тади` analyses identically to `тади`. This adds ~3 points of real-text coverage (capitalized sentence-initial words are common).

## Build

Requires HFST (`hfst-lexc`, `hfst-twolc`, `hfst-compose-intersect`, …).

```sh
make            # build both dialects (analyser + generator, optimised lookup)
make gan        # Gansu only
make shaanxi    # Shaanxi only
make test       # coverage for both
make clean
```

Outputs: 
`dng-{gan,shaanxi}.automorf.hfst` (analyser) and
`dng-{gan,shaanxi}.autogen.hfst` (generator).

## Use

```sh
echo "жынму" | hfst-lookup -q dng-gan.automorf.hfst
# жынму  жын<n><an><pl>   0.0

echo "жын<n><an><pl>" | hfst-lookup -q dng-gan.autogen.hfst
# жын<n><an><pl>  жынму   0.0
```

The dialect split is real: `сы` analyses as `<cop>` in Gansu but only `<num>`
("four") in Shaanxi; `шы` is the reverse.

## Evaluation

All figures below reproduce via `make check-all` and the scripts in `tests/`.

**Coverage** (`make coverage`; both dialects measured on the *same* 12,721-token
development corpus — Wikipedia articles plus trilingual parallel texts, original
case):

| dialect | token coverage | literary subset |
|---|---|---|
| Gansu   | **72.6%** (9232/12721) | 83.3% |
| Shaanxi | **73.8%** (9386/12721) | 84.7% |

**Held-out** (`tests/heldout.py`; texts never used in development, fetched at
run time and used for statistics only): folk proverbs **85.2%** (14,016 tokens)
and the Pentateuch **79.8%** (119,920 tokens) — both *above* the development
corpus, i.e. coverage is not a corpus-fitting artefact. Remaining misses are
dominated by proper nouns and rare vocabulary; the unknown-token lists printed
by `make coverage` are the expansion worklist (coverage is Zipfian — the most
frequent unknowns move the number fastest).

**Precision** (`make precision`; 104 hand-annotated tokens): the correct
reading is present for **104/104**; exact match including tone 69.2%; mean 1.21
analyses per recognized token. Caveat: the gold readings derive from the same
dictionary that feeds the lexicon, so this validates internal consistency
rather than speaker-verified truth — see `tests/adjudication/` for the
independent-annotation worksheet.

**Lexicon**: 7,858 stem entries across the source files (≈7,850 per dialect
build): hand-built core 210, Wiktionary 287, Salmi grammar/dictionary 206,
Yanshansin dictionary 6,987, proper nouns & loanwords 145, corpus-curated items
in the above, dialect overlays 6 (Gansu) / 13 (Shaanxi).

### Lexical tone (`<t1>` / `<t2>` / `<t3>`)

Dungan Cyrillic omits tone in running text, so a bare spelling like `задё` is
tonally ambiguous — and the dictionary lists it as **three different verbs**
(高 *высосать*, *загородить*, *взорвать*) distinguished only by tone. Dictionary
entries therefore carry a headword-tone tag drawn from the source's I/II/III
syllable marks (the Gansu 3-tone standard). This keeps same-spelling, same-POS
homographs distinct on the analysis side:

```
задё  ->  задё<vblex><t1>   (высосать)
          задё<vblex><t2>   (загородить)
          задё<vblex><t3>   (взорвать)
```

The tag sits between the POS tags and any inflection, so it composes with the
rest of the morphology and round-trips both ways:

```
задё<vblex><t3><pst>      <->  задёли      (взорвать + perfective -ли)
җятўзы<n><an><t1><pl>     <->  җятўзыму    (rabbit + animate plural -му)
```

The idea is borrowed from the **1928–1953 Latin orthography**, which (following
Gwoyeu Romatzyh) could spell tone into the letter string rather than dropping it
the way Cyrillic does. 7,164 stems are tone-tagged — about 91% of the lexicon — after the
dictionary's tone marks were back-filled across the whole alphabet onto core,
corpus, Wiktionary and Salmi stems as well. Dozens of spellings carry more than
one distinct tone, e.g. `йихуэй` = 一回 *once* (`<t1>`) vs 議會 *parliament*
(`<t3>`), or `со` = 鎖/嫂/燒/掃/縮 across five POS-and-tone readings. A stem stays
tone-neutral only when the dictionary didn't attest a single unambiguous tone
for it, so an analysis without a `<tN>` tag means tone wasn't recorded for that
lemma — not that the word is toneless.

## Testing & CI

Two kinds of test, both gating CI:

1. **Gold-standard tests** (`make test`) — `tests/run-tests.py` checks exact
   analyses and generations for forms we are *certain* of: closed-class items
   from the documented grammar (pronouns, copula, particles, aspect markers)
   and forms attested with glosses in the trilingual parallel corpus, rules
   from Salmi's grammar (experiential aspect, localizers), or dictionary-verified
   entries from Yanshansin. ~130 assertions across both dialects; the runner
   exits non-zero on any failure.

2. **Coverage-floor gate** (`make check`) — `tests/check-coverage.py` fails if
   token coverage drops below a per-dialect floor (68% for each dialect, both
   measured on the same full corpus),
   catching silent regressions from lexicon/rule edits.

`.github/workflows/ci.yml` installs HFST, runs `make all`, then `make test` and
`make check` on every push and PR. Test data is bundled under `tests/data/` so
CI is self-contained. Run everything locally with `make check-all`.




The **locative clitic** ни (裡 "in/at") attaches directly to nouns — 家里 *җя-ни*
"at home", 鍋里 *гуә-ни* "in the pot" — and is modeled as a `<loc>`-tagged clitic
on a shared `NounEnd` terminal, so every noun (tone-tagged or not) can take it
and it round-trips. Adding this single construction lifted Gansu corpus
recognition by several points, since locative phrases are pervasive in running
text.

Because Dungan is strongly analytic, **adjectives and stative predicates take
the same aspect marking as verbs**: 熱底呢 *жә-дини* "is (now) hot" is an adjective
plus the durative clitic, parallel to 吃底呢 *чы-дини* "is eating". The analyser
models this with a predicative `<prog>` slot on adjectives **and nouns**: in a
verb-object compound the aspect clitic lands on the object noun — 寫字底呢
*ще зы-дини* "is writing", 放風子底呢 *фон фынзы-дини* "is flying a kite" — so the
whole V-O predicate round-trips like verbal aspect does.

**Proper nouns** (names, places, ethnonyms) and established loanwords live in a
separate lexicon, since a dictionary of native Sino-Dungan vocabulary doesn't
contain them. They route through the regular morphology, so each lemma also
yields its genitive (撒馬利亞的 *самария-ди* "of Samaria") and collective plural
(希臘人們 *грек-жын-му* "Greeks") — one entry covering several surface forms.
This lifted Shaanxi type coverage by several points, since names are mostly
distinct types in encyclopedic text.
### Correctness, not just coverage (`make precision`)

Coverage measures *recognition* — does the analyser accept a token? It says
nothing about whether the **analysis is right**. `tests/precision.py` closes
that gap: it scores the analyser against a 104-token hand-annotated gold set
(`tests/gold-precision.txt`) drawn from the parallel corpus, where each token's
correct reading is fixed by the **hanzi** (which disambiguates the morpheme that
the tone-less Cyrillic leaves ambiguous). It reports:

- **recall** — is the correct analysis among those produced (100% on the
  104-token gold set, tone-insensitive)
- **exact** — correct *including* tone
- **mean ambiguity** — analyses returned per token (~1.5)
- **over-generation** — wrong extra readings per token (~0.16, almost all from
  genuinely ambiguous clitics like ни 裡/呢 the analyser cannot resolve without
  context)

The gold set has grown to 104 tokens over successive rounds, and building it has
repeatedly caught issues recognition had hidden: a missing common word (客
*guest*), several mis-imported dictionary entries (娃們 "children" lexicalized as
a verb, 他的 "his" as a noun, an OCR fragment "двугорбый"), and cases where the
analyser's compositional reading (numeral + classifier, animate nouns) was *more*
correct than the first hand annotation. It also drove the discovery of three real
grammatical constructions — the locative clitic, and predicative aspect on
adjectives and on object nouns in verb-object compounds. `make precision` is part
of `make check-all`, with a 90% recall floor.



### Core-vocabulary check (`make swadesh`)

As an independent cross-check, the analyser is tested against the **ASJP Swadesh
wordlist** for Dungan (CC-BY; compiled by André Müller from Janšansin & Šinlo's
2008 Russian-Dungan dictionary — a *different* source than the Yanshansin
dictionary the lexicon is built from). An analyser of a language should
recognise its most basic words, so `tests/swadesh.py` checks that a recognised
form exists for each core concept (body parts, nature, basic verbs). This
surfaced a handful of fundamental words that were genuinely missing — *leaf*
(葉子 езы), *sun* (太陽 тэён), *knee* (膝蓋子 щигэзы), *liver* (肝子 ганзы) — which
were then added from the dictionary. The ASJP list provided the pronunciation
that flagged the gap; the actual Cyrillic spellings and tones came from the
dictionary, to avoid importing the lossy ASJP transcription as data. `make
swadesh` is part of `make check-all`.

## Sources

Full bibliography: **SOURCES.md**. Per-rule, page-level provenance is given in
the accompanying article (under review).

- **Morphology & dialect contrasts**: Russian Wikipedia *Дунганский язык*
  (citing Имазов 1993, 林涛 2012, Драгунов 1937/1940, Яншансин 1968,
  Zavjalova 1978); and Olli Salmi, *The Syntax of Central Asian Dungan*
  (draft, Oslo Digital Archive of Dungan Studies) — aspect system, localizers,
  precise Gansu/Shaanxi correspondences (e.g. Shaanxi 1pl ңай, classifier гуə).
- **Lexicon**: hand-built core from corpus frequency; POS-tagged lemmas
  harvested from **en.wiktionary.org**; vocabulary attested in Salmi's grammar
  example sentences; and entries from **Yusup Yanshansin's Concise
  Dungan-Russian Dictionary** (2009; the openly available PDF scan;
  6,987 entries mined into `stems-yanshansin.lexc`). POS is derived from the Russian gloss's *head* noun
  (verbs from -ть/-ти infinitives, adjectives from -ый/-ий/-ой/-ая, animate
  nouns from person/animal glosses). POS is taken from the gloss's *head* noun,
  not its first word — Russian noun phrases lead with the adjective
  ("многоэтажный дом" = a house, not an adjective), so a naive first-word check
  misfires; `tools/classify_pos.py` implements the head-noun logic. The PDF's
  OCR renders the special Dungan letters as systematic artifacts (e.g. Җ →
  leading "9", ў → "7", ә → "H" in web-fetched text). A local copy of the PDF
  decodes differently — the special letters appear as named markers
  (ХcyrZhedesc → Җ, Хcyrstraight3 → Ү, Хcyrinv → ә, etc.) and tones as roman
  numerals joined by hyphens — and `pypdf` then allows extracting any page
  range. The entire Cyrillic alphabet (А–Я) has now been processed from the dictionary
  (~6,900 stems), each carrying its headword tone where the source attests one.
- **Coverage corpus**: the Dungan Wikipedia (Wikimedia Incubator `Wp/dng`), the
  Dungan Association of Kyrgyzstan literature portal, and trilingual
  (Dungan/Chinese/Russian) parallel data extracted from Wikipedia.

## Status & roadmap

Early-stage seed. Natural next steps:
- grow `stems-common.lexc` from the unknown-token worklists
- add a Gansu-specific test corpus (Association literature in JSON form)
- consider migrating the dialect split to **flag diacritics**
  (`@U.DIAL.GAN@`) for a single-source build, once the lexicon is larger
- optional interop: export to `.dix`/`lt-comp` (Apertium) or package for
  GiellaLT, if integrating with either ecosystem later; add Constraint Grammar
  disambiguation

## Licence

Intended for release under GNU GPL v3 (the usual licence for open FST language
data).
