# Guides & Vignettes

Practical walkthroughs for the CDE Analyzer pipeline. Each vignette is
self-contained and can be read independently — start with whichever matches
your current goal.

## Which vignette should I read?

| Your goal | Start here |
|-----------|------------|
| Brand-new to CDE Analyzer; want an end-to-end walkthrough | [Full Pipeline Quickstart](quickstart.md) |
| Tuning instrument detection or curating Phase 1 output | [Instrument Detection](instrument-detection.md) |
| Understanding the workflow engine, config files, and scaffold | [Pipeline Orchestration](pipeline-orchestration.md) |
| Adjusting parameters for small vs large datasets | [Parameter Tuning](parameter-tuning.md) |
| Already have curated patterns; want to strip and diagnose | [Phrase Stripping](phrase-stripping.md) |
| Distributing curation to multiple reviewers (file or server) | [Distributed Curation](distributed-curation.md) |
| Testing embedding/clustering with controlled noise | [Synthetic QC Data](synthetic-data.md) |

## Pipeline flow

The vignettes follow the pipeline order:

```
Phase 1               Phase 2             Phase 3
Instrument Detection → Phrase Mining     → Branching Strip
(instrument-detection)  (phrase-stripping)   (quickstart §6)
```

**[Pipeline Orchestration](pipeline-orchestration.md)** covers how to wire the
phases together using the workflow engine, `workflow scaffold`, and config files.

**[Parameter Tuning](parameter-tuning.md)** is a cross-cutting guide — read it
alongside whichever phase you are running.

## Reference documentation

These complement the vignettes with deeper technical detail:

- [Curation Guide](../curation-guide.md) — decision guidelines for human review checkpoints
- [Phrase Miner Logic](../phrase_miner_logic.md) — k-mer mining algorithm internals
- [Workflow Architecture](../workflow-architecture.md) — pipeline diagrams and design rationale
- [All Commands (CLI)](../help/all-commands.md) — complete flag reference for every command
