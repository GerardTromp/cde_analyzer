# Codebase Map

> **Updated**: v1.5.0 (2026-04-02)

## Project Root

```
cde_analyzer/                   # Project root (flat layout, not nested package)
├── cde_analyzer.py             # Main entry point — ACTION_REGISTRY + lazy dispatch
├── cli.py                      # Top-level CLI (entry point for `cde-analyzer` console script)
├── __init__.py                 # Package marker
├── pyproject.toml              # Build config, dependencies, tool settings
├── setup.py                    # Legacy setuptools (delegates to pyproject.toml)
├── CLAUDE.md                   # AI assistant context (condensed)
├── CLAUDE_full.md              # AI assistant context (full history)
├── mkdocs.yml                  # Documentation site config
│
├── actions/                    # CLI action modules (3-layer pattern)
├── logic/                      # Business logic (algorithms, engines)
├── utils/                      # Reusable utilities and helpers
├── core/                       # Recursive descent engine
├── CDE_Schema/                 # Pydantic data models
├── config/                     # YAML configuration files
├── workflows/                  # Pipeline YAML definitions
├── data/                       # Reference data (curation ledger)
├── tools/                      # Standalone tools (editor zipapp)
├── scripts/                    # Build/utility scripts
├── docs/                       # Documentation (MkDocs site)
├── examples/                   # Example configs
├── tests/                      # Test suite
└── .claude/                    # Claude Code context + checkpoints
```

## Actions Directory

Each action follows the 3-file pattern: `cli.py` (args) → `run.py` (orchestration) → `logic/` (algorithms).

```
actions/
├── curation/                   # Curation lifecycle (edit, gate, finalize, init/merge, serve)
├── instrument_miner/           # Phase 1: instrument name mining
├── instrument_util/            # Instrument utilities (hierarchy, strip patterns, splits)
├── pattern_util/               # Pattern TSV utilities (coalesce, merge, field analysis, etc.)
├── pattern_diag/               # Pattern diagnostics (curation-status)
├── supplementary/              # Supplementary pattern management
├── phrase_miner/               # Phase 2: k-mer phrase mining
├── strip_branching/            # Phase 3: N-way branching strip (single-pass engine)
├── strip_phrases/              # Phrase stripping engine
├── strip_discover/             # Field distribution + text index
├── workflow/                   # Pipeline orchestration (run, scaffold, configure)
├── llm_classify/               # LLM-based classification (not yet in pipelines)
├── count/                      # Field counting and statistics
├── extract_embed/              # Field extraction for embeddings
├── subset/                     # CDE subset extraction
├── strip_html/                 # HTML markup removal
├── fix_underscores/            # Pydantic field name fixing
├── phrase/                     # Original phrase detection (legacy)
├── phrase_builder/             # Incremental phrase construction
├── phrase_grouper/             # Phrase grouping
├── lemma_fasta/                # FASTA format from lemma sequences
├── batch_expand_abbreviations/ # Batch abbreviation expansion
├── diagnose_strip/             # Strip diagnostics
├── discovery_report/           # Post-strip discovery report
├── pipeline_report/            # Pipeline summary report
├── recall_analyze/             # Recall analysis
├── strip_analyze/              # Strip analysis
├── strip_compare/              # A/B strip comparison
├── strip_report/               # Strip quality report
└── tsv_concat/                 # TSV file concatenation
```

## Logic Directory

```
logic/
├── branching_stripper.py       # N-way strip engine (StripStage, strip_branching, tinyid index)
├── curation_ledger.py          # CurationLedger, CurationDecision, classify_patterns
├── inter_rater.py              # Cohen's/Fleiss' kappa, Krippendorff's alpha
├── phrase_miner.py             # K-mer mining: dedup_field_texts(), mine_phrases()
├── phrase_stripper.py          # Phrase removal with parallel processing
├── phrase_extractor.py         # Original phrase detection
├── phrase_builder.py           # Incremental phrase construction
├── phrase_family_analyzer.py   # Phrase family analysis
├── phrase_grouper.py           # Phrase grouping
├── group_hierarchy.py          # Instrument group hierarchy assignment
├── verbatim_discoverer.py      # Verbatim pattern discovery
├── remnant_detector.py         # Post-strip remnant cleanup (--clean-remnants)
├── rare_word_detector.py       # Rare word detection (wordfreq)
├── span_boundary.py            # Span boundary detection
├── counter.py                  # Field counting and type classification
├── extract_embed.py            # Field extraction for embeddings
├── html_stripper.py            # HTML tag removal
├── lemma_fasta.py              # FASTA format generation
├── llm_classifier.py           # LLM classification orchestration
├── instrument_family_assigner.py # Family assignment workflow
├── phrase_anchor_extend.py     # Anchor extension (placeholder)
└── subset.py                   # Subset extraction
```

## Utils Directory

```
utils/
├── flexible_pattern_matcher.py # Coalescer (Phase 1a prefix-kept, Phase 1b NP-continuity)
├── instrument_extractor.py     # Instrument name extraction (InstrumentExtractor, InstrumentCatalog)
├── instrument_family_patterns.py # Regex patterns for 13 instrument families
├── pattern_variant_generator.py  # Temporal/case/number/plural variant generators
├── pattern_tsv_utils.py        # Pattern TSV file loading/writing
├── phrase_miner_vocab.py       # Vocabulary class (token-to-ID mapping)
├── subsumption_filter.py       # Subsumption filtering
├── verbatim_coalesce.py        # Verbatim pattern coalescing
├── verbatim_template.py        # Verbatim pattern templates
├── verbatim_tracker.py         # Verbatim pattern tracking
├── verbatim_diff.py            # Verbatim diff utilities
├── aho_corasick_token.py       # Aho-Corasick token matching
├── context_aware_masking.py    # Context-aware masking
├── debruijn_graph.py           # De Bruijn graph utilities
├── config_loader.py            # YAML config loading
├── constants.py                # Shared constants
├── cli_args.py                 # CLI argument helpers
├── diff_utils.py               # Diff utilities
├── file_utils.py               # File I/O helpers
├── histogram_generator.py     # Histogram generation
├── cde_impexport.py            # JSON import/export
├── datatype_check.py           # Type validation
├── designation_parser.py       # Designation field parsing
├── helpers.py                  # Common helpers
├── html.py                     # HTML processing
├── extract_embed.py            # Field extraction helpers
├── output_writer.py            # Multi-format output
├── path_utils.py               # File path utilities
├── phrase_extraction.py        # Phrase detection algorithms
├── phrase_pruning.py           # Phrase filtering
├── phrase_builder.py           # Phrase construction helpers
├── logger.py                   # Logging configuration
├── analyzer_state.py           # Global state (verbosity)
├── tinyid_utils.py             # TinyID manipulation
├── unicode.py                  # Unicode handling
├── llm/                        # Async LLM providers (Claude, OpenAI, Gemini)
├── query_modules/              # Pluggable classification modules + YamlPromptModule
├── legacy_kmer/                # Archived legacy kmer code
├── kmer_extend_phrases1.py     # Legacy kmer (retained)
├── kmer_legacy_algorithms.py   # Legacy kmer (retained)
└── plot_kmer_counts.py         # Legacy plotting (retained)
```

## Other Directories

```
CDE_Schema/                     # Pydantic data models
├── CDE_Item.py                 # CDEItem model
├── CDE_Form.py                 # CDEForm model
├── EmbedText.py                # EmbedText model
├── LLM_Classification.py       # LLM classification results
└── classes.py                  # Shared model classes

core/
└── recursor.py                 # Recursive descent engine

config/
├── temporal_seed_patterns.yaml     # 25 temporal seeds (~2100 expanded)
├── verbatim_strip_patterns.yaml    # Verbatim patterns (106 with tinyIds, 16 universal)
├── supplementary_patterns.yaml     # Supplementary pattern registry
├── anchor_expansions.yaml          # Anchor expansion rules
├── rare_word_whitelist.yaml        # Rare word whitelist
├── llm_prompts.yaml                # LLM prompt templates (boilerplate_substitution, semantic_proxy)
└── permanent_skip_abbreviations.yaml # Abbreviations exempt from k-fold re-evaluation

workflows/
├── instrument_pipeline.yaml    # Phase 1
├── phrase_pipeline.yaml        # Phase 2
├── branching_strip.yaml        # Phase 3 (legacy 10-step)
└── branching_strip_nway.yaml   # Phase 3 (N-way 3-step)

data/reference_ledger/          # Official bootstrap curation ledger (allcde03)
tools/editor_standalone/        # Standalone TSV editor server (zipapp)
scripts/                        # build_editor_zipapp.py, branching_loss_analysis.py
```

## Key HTML Assets

```
actions/curation/tsv_editor.html         # Browser-based TSV curation editor
actions/curation/curation_diff.html      # Multi-curator diff viewer
```
