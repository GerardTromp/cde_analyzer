#!/bin/bash
# One-time script: copy ML-approved pattern files into the codebase reference ledger
set -euo pipefail

BASE=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3
DEST=/mnt/d/GT/Professional/NLM_CDE/coding/cde_analyzer/data/reference_ledger/production_patterns

mkdir -p "$DEST"

cp "$BASE/phase1_output/inst_patterns_full.tsv"                    "$DEST/"
cp "$BASE/phase1_output/inst_patterns_sub.tsv"                     "$DEST/"
cp "$BASE/comparison/curator_patterns/phrase_patterns_ML.tsv"      "$DEST/"
cp "$BASE/comparison/substitute_patterns/substitute_ML.tsv"        "$DEST/"
cp "$BASE/phase2_output/boilerplate_substitutes_combined.tsv"      "$DEST/boilerplate_substitutes.tsv"

echo "All files copied to $DEST"
wc -l "$DEST"/*.tsv
