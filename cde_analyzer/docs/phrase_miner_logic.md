# Phrase Miner Logic

This document describes the internal logic and data flow of the `phrase_miner` action, which implements an iterative descending k-mer algorithm for detecting repeated phrases across CDE (Common Data Element) records.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            PHRASE MINER PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────┐         ┌──────────────────────────────────────────────────┐ │
│   │  INPUT      │         │  ORCHESTRATION (run.py)                          │ │
│   │  CDE JSON   │────────►│  • Parse CLI arguments                           │ │
│   └─────────────┘         │  • Build MinerConfig                             │ │
│                           │  • Route to Phase 1 or Phase 2                   │ │
│                           └────────────────┬─────────────────────────────────┘ │
│                                            │                                    │
│                 ┌──────────────────────────┴──────────────────────┐             │
│                 │                                                  │             │
│                 ▼                                                  ▼             │
│   ┌─────────────────────────────┐          ┌────────────────────────────────┐  │
│   │  PHASE 1 (--instruments-only)│          │  PHASE 2 (Full Mining)        │  │
│   │  • Extract instruments       │          │  • Tokenize & lemmatize       │  │
│   │  • Write instruments.tsv     │          │  • Iterative k-mer descent    │  │
│   │  • For human curation        │          │  • Mask detected phrases      │  │
│   └─────────────────────────────┘          │  • Optional filters           │  │
│                                            └────────────────┬───────────────┘  │
│                                                             │                   │
│                                                             ▼                   │
│                                            ┌────────────────────────────────┐  │
│                                            │  OUTPUT FILES                  │  │
│                                            │  • phrases.tsv                 │  │
│                                            │  • occurrences.tsv             │  │
│                                            │  • verbatim_phrases.tsv        │  │
│                                            │  • verbatim_variants.tsv       │  │
│                                            │  • verbatim_templates.tsv      │  │
│                                            │  • instruments.tsv (optional)  │  │
│                                            └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Algorithm: Iterative Descending K-mer Mining

The algorithm finds repeated phrases by searching for k-mers (token sequences of length k) starting from long sequences and working down to shorter ones. Detected phrases are "masked" to prevent re-detection at smaller k values.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ITERATIVE DESCENDING K-MER LOOP                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   k_max = 25                                                                    │
│   k_min = 3                                                                     │
│                                                                                 │
│   for k in range(k_max, k_min - 1, -1):    ◄── Descend from 25 to 3            │
│       │                                                                         │
│       ▼                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐          │
│   │  STAGE 1: Count k-mers in UNMASKED regions only                 │          │
│   │  ┌─────────────────────────────────────────────────────────┐    │          │
│   │  │  Token Sequence:  [A][B][C][D][E][F][G][H][I][J]       │    │          │
│   │  │  Mask State:       -  -  X  X  X  -  -  -  X  -        │    │          │
│   │  │                           ▲▲▲▲▲        (X = masked)    │    │          │
│   │  │                     Previously detected phrase          │    │          │
│   │  │                                                         │    │          │
│   │  │  Only count k-mers in unmasked windows:                │    │          │
│   │  │    [A,B] ✓    [B,C] ✗    [E,F] ✗    [F,G,H] ✓          │    │          │
│   │  └─────────────────────────────────────────────────────────┘    │          │
│   └─────────────────────────────────────────────────────────────────┘          │
│       │                                                                         │
│       ▼                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐          │
│   │  STAGE 2: Filter by frequency and tinyId support                │          │
│   │  • freq_min: Minimum occurrence count (default: 3)              │          │
│   │  • min_tinyids: Minimum distinct documents (default: 2)         │          │
│   └─────────────────────────────────────────────────────────────────┘          │
│       │                                                                         │
│       ▼                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐          │
│   │  STAGE 3: (Optional) De Bruijn Graph Extension                  │          │
│   │  • Extends k-mers by finding overlapping sequences              │          │
│   │  • Enabled with --enable-debruijn                               │          │
│   └─────────────────────────────────────────────────────────────────┘          │
│       │                                                                         │
│       ▼                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐          │
│   │  STAGE 4: MASK detected phrases (prevent re-detection)          │          │
│   │  • Using Aho-Corasick automaton (fast, O(n+m+z))               │          │
│   │  • Or naive sliding window (slower, O(n*m*k))                   │          │
│   └─────────────────────────────────────────────────────────────────┘          │
│       │                                                                         │
│       └──────► Next k value (k - 1) ──────────────────────────────────────►    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Data Structures

### Core Classes (phrase_miner.py)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA STRUCTURES                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────────────┐                                                       │
│  │      CDEItem         │◄── Input: Pydantic model of CDE record               │
│  │  • tinyId            │                                                       │
│  │  • designations[]    │                                                       │
│  │  • definitions[]     │                                                       │
│  └──────────────────────┘                                                       │
│            │                                                                    │
│            │ extract_field_texts()                                              │
│            ▼                                                                    │
│  ┌──────────────────────┐     ┌────────────────────────────────┐               │
│  │     TokenSeq         │     │        Vocabulary              │               │
│  │  • tokens: [int]     │◄───►│  • token → id mapping         │               │
│  │  • mask_owner: [str] │     │  • id → token mapping         │               │
│  │  • original_tokens   │     └────────────────────────────────┘               │
│  │  • original_text     │                                                       │
│  │  • char_offsets      │     ┌────────────────────────────────┐               │
│  │  • cde_ref ──────────┼────►│         CDERef                 │               │
│  └──────────────────────┘     │  • tinyId                      │               │
│                               │  • field_path                  │               │
│                               │  • token_span                  │               │
│                               │  • verbatim_text               │               │
│                               │  • char_span                   │               │
│                               └────────────────────────────────┘               │
│                                                                                 │
│  ┌──────────────────────┐     ┌────────────────────────────────┐               │
│  │      KmerCount       │────►│          Phrase                │               │
│  │  • kmer: (int,...)   │     │  • phrase_id                   │               │
│  │  • frequency         │     │  • token_ids: (int,...)        │               │
│  │  • tinyids: set      │     │  • text                        │               │
│  │  • occurrences       │     │  • frequency                   │               │
│  └──────────────────────┘     │  • distinct_tinyids            │               │
│                               │  • occurrences: [CDERef]       │               │
│                               │  • extension_method            │               │
│                               └────────────────────────────────┘               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Masking State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          TOKEN MASKING MECHANISM                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   TokenSeq.mask_owner tracks which phrase "owns" each token position:           │
│                                                                                 │
│   Original text: "Patient Reported Outcome Measure for Anxiety Questionnaire"   │
│                                                                                 │
│   tokens:     [ patient | report | outcome | measure | anxiety | questionnaire ]│
│   mask_owner: [  None   |  None  | phrase_01| phrase_01| None  |    None      ]│
│                                  ╰────┬────╯                                    │
│                         "outcome measure" detected at k=2                       │
│                                                                                 │
│   When counting k-mers at k=3:                                                  │
│   • [patient, report, outcome] → BLOCKED (outcome is masked)                   │
│   • [report, outcome, measure] → BLOCKED (both masked)                         │
│   • [measure, anxiety, questionnaire] → BLOCKED (measure is masked)            │
│   • [anxiety, questionnaire, ...] → OK if next token unmasked                  │
│                                                                                 │
│   Pre-masking (before k-mer loop):                                              │
│   • Instrument patterns: mask_owner = "__INSTRUMENT__:Instrument Name"          │
│   • Curated patterns:    mask_owner = "__CURATED_INSTRUMENT__:pattern"          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Aho-Corasick Multi-Pattern Matching

Used for efficient phrase masking after each k-bin iteration.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    AHO-CORASICK AUTOMATON (Token-Based)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Purpose: Find all phrase patterns simultaneously in O(n + m + z) time         │
│   (vs naive O(n * m * k))                                                       │
│                                                                                 │
│   Example patterns to find:                                                     │
│     phrase_01: [45, 23, 78]  → "patient reported outcome"                       │
│     phrase_02: [23, 78, 12]  → "reported outcome measure"                       │
│                                                                                 │
│   Automaton structure (token IDs as edges):                                     │
│                                                                                 │
│                    ┌───────┐                                                    │
│           ┌──────►│  ROOT  │◄──────────────────────┐                           │
│           │       └───┬───┘                         │ failure                   │
│           │           │                             │ link                      │
│           │      45   │   23                        │                           │
│           │           ▼                             │                           │
│           │       ┌───────┐                     ┌───┴───┐                       │
│           │       │ node1 │────── 23 ──────────►│ node3 │                       │
│           │       └───────┘                     └───┬───┘                       │
│           │           │                             │                           │
│           │      23   │                        78   │                           │
│           │           ▼                             ▼                           │
│           │       ┌───────┐                     ┌───────┐                       │
│           └───────│ node2 │                     │ node4 │ ← output: phrase_02   │
│      failure      └───┬───┘                     └───┬───┘                       │
│        link           │                             │                           │
│                  78   │                        12   │                           │
│                       ▼                             ▼                           │
│                   ┌───────┐                     ┌───────┐                       │
│                   │ node5 │ ← output: phrase_01 │ node6 │                       │
│                   └───────┘                     └───────┘                       │
│                                                                                 │
│   Search process:                                                               │
│   • Traverse automaton with input token sequence                                │
│   • On mismatch, follow failure links (like KMP algorithm)                      │
│   • Collect all patterns at output nodes                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Verbatim Text Recovery

Tracks original surface forms before lemmatization for output.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         VERBATIM TEXT RECOVERY                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Problem: Lemmatization loses original text                                    │
│     "Patient Reported Outcomes" → "patient report outcome"                      │
│     "patient-reported outcome"  → "patient report outcome"  (same lemmas!)      │
│                                                                                 │
│   Solution: Two-level tracking                                                  │
│                                                                                 │
│   1. Position-based (exact): CDERef stores verbatim_text per occurrence         │
│      ┌────────────────────────────────────────────────────────────────┐        │
│      │  occurrence = CDERef(                                          │        │
│      │      tinyId = "abc123",                                        │        │
│      │      field_path = "designations[0].designation",               │        │
│      │      token_span = (5, 8),                                      │        │
│      │      verbatim_text = "Patient Reported Outcomes",  ◄── exact  │        │
│      │      char_span = (42, 67)                                      │        │
│      │  )                                                             │        │
│      └────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
│   2. Lemma→Variants dictionary (VerbatimTracker):                               │
│      ┌────────────────────────────────────────────────────────────────┐        │
│      │  lemma_to_variants = {                                         │        │
│      │      "patient": PrefixTrie(["Patient", "patients", "PATIENT"]),│        │
│      │      "report":  PrefixTrie(["Reported", "reported", "report"]),│        │
│      │      "outcome": PrefixTrie(["Outcomes", "outcome", "Outcome"]) │        │
│      │  }                                                             │        │
│      └────────────────────────────────────────────────────────────────┘        │
│                                                                                 │
│   PrefixTrie enables O(k) lookup by first N characters:                         │
│                                                                                 │
│       ┌─────┐                                                                   │
│       │ "p" ├────► ┌───┐                                                        │
│       └─────┘      │"a"├──► {"Patient", "patients"}                             │
│                    └───┘                                                        │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Subsumption Filtering

Optional post-processing to remove redundant shorter phrases.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SUBSUMPTION FILTERING                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Definition: Phrase P is SUBSUMED by Q if:                                     │
│   1. P's tokens are a contiguous subsequence of Q's tokens                      │
│   2. P and Q share at least one tinyId (document overlap)                       │
│                                                                                 │
│   Example:                                                                      │
│   ┌────────────────────────────────────────────────────────────────────┐       │
│   │  Detected phrases (before filtering):                              │       │
│   │                                                                    │       │
│   │  phrase_01: "patient reported outcome measure" (k=4)               │       │
│   │             tinyIds: {abc, def, ghi}                               │       │
│   │                                                                    │       │
│   │  phrase_02: "reported outcome" (k=2)                               │       │
│   │             tinyIds: {abc, def, xyz}                               │       │
│   │                        ▲▲▲  ▲▲▲                                    │       │
│   │                      overlap exists                                │       │
│   │                                                                    │       │
│   │  phrase_03: "outcome measure" (k=2)                                │       │
│   │             tinyIds: {abc, def}                                    │       │
│   │                                                                    │       │
│   │  phrase_04: "quality of life" (k=3)                                │       │
│   │             tinyIds: {xyz, 123}   ◄── no overlap with phrase_01   │       │
│   └────────────────────────────────────────────────────────────────────┘       │
│                                                                                 │
│   Result (after filtering):                                                     │
│   ┌────────────────────────────────────────────────────────────────────┐       │
│   │  ✓ phrase_01: "patient reported outcome measure" (KEPT - longest)  │       │
│   │  ✗ phrase_02: "reported outcome" (REMOVED - subsumed by phrase_01) │       │
│   │  ✗ phrase_03: "outcome measure" (REMOVED - subsumed by phrase_01)  │       │
│   │  ✓ phrase_04: "quality of life" (KEPT - no subsumer)               │       │
│   └────────────────────────────────────────────────────────────────────┘       │
│                                                                                 │
│   Algorithm: O(n²) pairwise comparison with early termination                   │
│   • Sort phrases by length (descending)                                         │
│   • For each phrase, check if it subsumes any shorter phrase                   │
│   • Optimized version uses prefix indexing for large datasets (>100 phrases)   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Two-Phase Workflow (Instrument Extraction)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    TWO-PHASE INSTRUMENT WORKFLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Purpose: Extract and mask "as part of <Instrument Name> (<ACRONYM>)" patterns │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                        PHASE 1: Discovery                               │  │
│   │   cde_analyzer phrase_miner -i data.json -o output/ --instruments-only  │  │
│   └────────────────────────────────┬────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────────┐   │
│   │  Input text: "...as part of Patient Health Questionnaire (PHQ-9)..."   │   │
│   │                    ▲                                               ▲    │   │
│   │                    │           extracted                           │    │   │
│   │                    └───────────────────────────────────────────────┘    │   │
│   └────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                            │
│                                    ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │  Output: instruments_verbatim.tsv                                       │  │
│   │  ┌─────────────────────────────────────────────────────────────────┐   │  │
│   │  │ normalized_name              │ full_match                       │   │  │
│   │  ├─────────────────────────────────────────────────────────────────┤   │  │
│   │  │ patient health questionnaire │ as part of Patient Health...    │   │  │
│   │  │ brief pain inventory         │ as part of Brief Pain...        │   │  │
│   │  │ false positive example       │ as part of False Positive...    │   │  │
│   │  └─────────────────────────────────────────────────────────────────┘   │  │
│   └─────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                            │
│                               Human curation                                    │
│                          (delete false positives)                               │
│                                    │                                            │
│                                    ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────────┐  │
│   │                        PHASE 2: Full Mining                             │  │
│   │   cde_analyzer phrase_miner -i data.json -o output/ \                   │  │
│   │       --instrument-list instruments_verbatim.tsv,full_match             │  │
│   └────────────────────────────────┬────────────────────────────────────────┘  │
│                                    │                                            │
│                                    ▼                                            │
│   ┌────────────────────────────────────────────────────────────────────────┐   │
│   │  Pre-masking: Curated patterns masked BEFORE k-mer loop                │   │
│   │                                                                        │   │
│   │  tokens:     [...| as | part | of | patient | health | quest |...]    │   │
│   │  mask_owner: [...|None|None |None|__CURATED__|__CURATED__|__CURATED__]│   │
│   │                                   ╰──────────────┬───────────────╯     │   │
│   │                              Pre-masked: won't be detected             │   │
│   │                              as separate k-mer phrases                  │   │
│   └────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE PIPELINE FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. LOAD DATA                                                                   │
│     ┌─────────────┐                                                            │
│     │  JSON File  │───► [CDEItem, CDEItem, CDEItem, ...]                       │
│     └─────────────┘                                                            │
│                                                                                 │
│  2. EXTRACT & TOKENIZE                                                          │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │  For each CDEItem:                                                  │    │
│     │    • Extract text from fields (designations, definitions, etc.)     │    │
│     │    • Tokenize with position tracking                                │    │
│     │    • (Optional) Extract instrument patterns                         │    │
│     │    • Lemmatize (optionally remove stopwords)                        │    │
│     │    • Build vocabulary (token ↔ integer ID)                          │    │
│     │    • Track lemma → original variants                                │    │
│     │    • Pre-mask curated patterns if provided                          │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│           │                                                                     │
│           ▼                                                                     │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │  Result: List[TokenSeq], Vocabulary, VerbatimTracker                │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  3. ITERATIVE K-MER MINING (k=25 down to k=3)                                   │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │  For k = 25, 24, 23, ..., 3:                                        │    │
│     │    ┌─────────────────────────────────────────────────────────┐      │    │
│     │    │ 3a. COUNT: Scan all TokenSeqs for k-length windows      │      │    │
│     │    │     • Skip if any token in window is masked             │      │    │
│     │    │     • Track frequency, tinyIds, verbatim text           │      │    │
│     │    └─────────────────────────────────────────────────────────┘      │    │
│     │                           │                                          │    │
│     │                           ▼                                          │    │
│     │    ┌─────────────────────────────────────────────────────────┐      │    │
│     │    │ 3b. FILTER: Keep k-mers with:                           │      │    │
│     │    │     • frequency >= freq_min (default: 3)                │      │    │
│     │    │     • distinct tinyIds >= min_tinyids (default: 2)      │      │    │
│     │    └─────────────────────────────────────────────────────────┘      │    │
│     │                           │                                          │    │
│     │                           ▼                                          │    │
│     │    ┌─────────────────────────────────────────────────────────┐      │    │
│     │    │ 3c. (Optional) DE BRUIJN: Extend k-mers via overlap     │      │    │
│     │    └─────────────────────────────────────────────────────────┘      │    │
│     │                           │                                          │    │
│     │                           ▼                                          │    │
│     │    ┌─────────────────────────────────────────────────────────┐      │    │
│     │    │ 3d. MASK: Mark detected phrase positions                │      │    │
│     │    │     • Build Aho-Corasick automaton from new phrases     │      │    │
│     │    │     • Find all matches in all TokenSeqs                 │      │    │
│     │    │     • Set mask_owner for matched positions              │      │    │
│     │    └─────────────────────────────────────────────────────────┘      │    │
│     │                           │                                          │    │
│     │                           └──────► Continue with k-1                 │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  4. POST-PROCESSING                                                             │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │  • (Optional) Subsumption filter: Remove redundant shorter phrases  │    │
│     │  • (Optional) Anchor extension: Extend phrases at boundaries        │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
│  5. OUTPUT                                                                      │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │  phrases.tsv           - Lemmatized phrase summary                  │    │
│     │  occurrences.tsv       - Every occurrence with location             │    │
│     │  verbatim_phrases.tsv  - Unique surface forms per phrase            │    │
│     │  verbatim_variants.tsv - Lemma → variants dictionary                │    │
│     │  verbatim_templates.tsv- Structural patterns from multi-form phrases│    │
│     │  instruments.tsv       - Detected instruments (if enabled)          │    │
│     │  instruments_verbatim.tsv - For human curation (if enabled)         │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Key Files

| File                                                              | Purpose                       |
| ----------------------------------------------------------------- | ----------------------------- |
| [actions/phrase_miner/cli.py](../actions/phrase_miner/cli.py)     | CLI argument parser           |
| [actions/phrase_miner/run.py](../actions/phrase_miner/run.py)     | Orchestration layer           |
| [logic/phrase_miner.py](../logic/phrase_miner.py)                 | Core mining algorithm         |
| [utils/aho_corasick_token.py](../utils/aho_corasick_token.py)     | Multi-pattern matching        |
| [utils/subsumption_filter.py](../utils/subsumption_filter.py)     | Redundancy removal            |
| [utils/verbatim_tracker.py](../utils/verbatim_tracker.py)         | Original text recovery        |
| [utils/instrument_extractor.py](../utils/instrument_extractor.py) | Instrument pattern extraction |

## Complexity Analysis

| Operation                 | Time Complexity | Notes                           |
| ------------------------- | --------------- | ------------------------------- |
| Tokenization              | O(n)            | n = total characters            |
| K-mer counting (per k)    | O(m * k)        | m = total tokens                |
| Aho-Corasick construction | O(p)            | p = sum of pattern lengths      |
| Aho-Corasick search       | O(m + z)        | z = number of matches           |
| Naive masking             | O(m * s * k)    | s = number of phrases           |
| Subsumption filter        | O(s²)           | Optimized version uses indexing |

Overall pipeline: **O(n + (k_max - k_min) * m * log(s))** where:

- n = total characters in input
- m = total tokens after processing
- s = number of detected phrases
- k_max, k_min = k-mer range (default 25 to 3)
