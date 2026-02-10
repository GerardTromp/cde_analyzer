# Knowledge Graph Approach Summary

> **Note**: This document is supplementary context. Not required for routine checkpointing.

## Overview

Investigated whether graph-based representations of pattern relationships could improve stripping quality compared to simple length-first ordering. Built on the `knowledge-graph` branch (merged features back to `phrase-curator`).

## Four Graph Types Implemented

### 1. Co-occurrence Graph (`logic/pattern_graph.py`)
- **Nodes**: Patterns; **Edges**: Jaccard similarity of tinyId sets
- Community detection via greedy modularity (networkx)
- Identifies pattern bundles that co-occur in the same CDEs

### 2. Subsumption DAG
- **Edges**: Parent -> child when parent is a substring and covers child's tinyIds
- DAG roots = maximal patterns (longest, most general)
- Transitive children and rollup queries

### 3. Semantic Similarity Graph
- Sentence-transformer embeddings (`all-MiniLM-L6-v2`, 384-dim)
- Edges where cosine similarity >= threshold (default 0.7)
- Groups conceptually similar patterns (e.g., different PROMIS subscales)

### 4. Edit Distance Graph
- Token-level Jaccard similarity between pattern texts
- Catches near-duplicates differing by 1-2 tokens

## CLI Integration

```bash
cde-analyzer pattern_util --build-graph coalesced_fields.tsv \
  --graph-type all -o enriched.tsv --export-graphml graph.graphml \
  --graph-tool gephi
```

Enriched TSV gets columns: `cluster_id`, `cluster_size`, `dag_depth`, `is_root`, `parent_pattern`, `semantic_cluster_id`, `edit_dist_cluster_id`.

GraphML export supports Gephi and Cytoscape annotation conventions.

## A/B Comparison Results

Ran `strip_compare` on scheuermann09 dataset:

| Metric | Naive (length-first) | Smart (graph-ordered) |
|--------|---------------------|----------------------|
| Remnant count | Same | Same |
| Patterns matched | Same | Same |
| Field modifications | Same | Same |

**Result: No measurable difference.** The subsumption DAG was too shallow (depth 1-2) for ordering to matter. Length-first ordering already approximates root-first ordering because roots are the longest patterns.

## Value Assessment

| Use Case | Value |
|----------|-------|
| Strip ordering | None (results identical) |
| Curation assistance | Moderate (community detection groups related patterns) |
| Visualization | Moderate (Gephi/Cytoscape graphs reveal pattern clusters) |
| Near-duplicate detection | Useful (edit distance graph finds patterns to merge) |

## Recommendation

- **Do not** use graph ordering for stripping (no benefit, added complexity)
- **Consider** graph visualization for curation of large pattern sets (>100 patterns)
- `--clean-remnants` provides 99.9% remnant reduction regardless of strip ordering
