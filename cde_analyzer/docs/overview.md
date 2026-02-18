# Overview

CDE Analyzer is a Python CLI toolkit for parsing and analyzing Common Data Elements (CDEs) from the [National Library of Medicine](https://cde.nlm.nih.gov/api) at the National Institutes of Health.

## Motivation

CDE text fields contain substantial boilerplate: instrument names ("Patient-Reported Outcomes Measurement Information System (PROMIS) Anxiety Short Form 8a"), temporal preambles ("In the past 7 days"), and repeated definitional phrases. This noise obscures the underlying semantic content and hinders clustering, classification, and comparison of CDEs. CDE Analyzer provides an automated, multi-phase pipeline to detect and strip these patterns while preserving content-bearing text.

## Three-Phase Pipeline

The primary workflow runs in three sequential phases:

### Phase 1: Instrument Detection

Discovers and strips measurement instrument names from CDE text using anchor detection, abbreviation expansion, and pattern coalescing. Output: instrument-stripped JSON.

- **Mine** instrument patterns via abbreviation anchors and supplementary config
- **Discover** verbatim occurrences with variant expansion
- **Coalesce** redundant patterns via tinyId-aware subsumption
- **Strip** in two passes: long patterns first (tier-1), then short fragments (tier-2)

### Phase 2: Phrase Stripping

Detects repeated non-instrument phrases using iterative descending k-mer mining, then strips them with curator oversight. Output: fully cleaned JSON.

- **Mine** phrases using k-mer descent (k=25 down to k=3) with token masking
- **Discover** verbatim occurrences and coalesce variants
- **Enrich** with field analysis (definition/designation counts)
- **Strip** curated phrases with remnant cleanup

### Phase 3: Branching Strip

Applies temporal pattern expansion and case-sensitive/insensitive stripping in a branching pipeline that produces multiple output variants for comparison. Output: quality reports per branch.

## Architecture

CDE Analyzer uses a **layered monolithic** architecture with a plugin-style action system:

```
cde_analyzer.py          # Entry point with ACTION_REGISTRY
+-- actions/             # Each action has cli.py + run.py
|   +-- phrase_miner/    # Argument parsing + orchestration
|   +-- ...
+-- logic/               # Business logic implementations
+-- utils/               # Helper functions
+-- CDE_Schema/          # Pydantic data models
```

**Key design principles:**

- **Lazy Loading** --- Actions loaded only when invoked for fast CLI startup
- **Three-Layer Actions** --- CLI (argument parsing) / Orchestration (I/O) / Logic (algorithms)
- **Visitor Pattern** --- Single recursive engine for nested CDE traversal
- **YAML Workflows** --- Multi-step pipelines defined declaratively with checkpoint support

## Further Reading

- [Workflow Architecture](workflow-architecture.md) --- Detailed pipeline diagrams and command reference
- [Architecture](architecture.md) --- Code-level design, ADRs, and extension points
- [Data Models](data-models.md) --- Pydantic model reference (CDEItem, CDEForm, 50+ supporting models)
- [Commands Overview](commands/index.md) --- All available CLI commands by category
- [Curation Guide](curation-guide.md) --- Decision guidelines for human pattern review
