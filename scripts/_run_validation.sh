#!/bin/bash
# Validation: run production_strip.yaml and compare against test_v7/ML
set -euo pipefail

source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate
cd /mnt/d/GT/Professional/NLM_CDE/coding/cde_analyzer

INPUT=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/allcde.json
OUTDIR=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/validation
REF=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/ML

mkdir -p "$OUTDIR"

echo "=== Running production_strip.yaml ==="
echo "Input: $INPUT"
echo "Output: $OUTDIR"
echo ""

python cde_analyzer.py workflow run workflows/production_strip.yaml \
    --set input_json="$INPUT" \
    --set output_dir="$OUTDIR" \
    --set variants=MTSFPT,MTSTPT

echo ""
echo "=== Comparing outputs against reference (test_v7/ML) ==="

for V in MTSFPT MTSTPT; do
    echo ""
    echo "--- Variant: $V ---"

    # Compare TSV embed files
    NEW_TSV="$OUTDIR/embed_${V}.tsv"
    REF_TSV="$REF/embed_${V}_ML.tsv"

    if [ -f "$NEW_TSV" ] && [ -f "$REF_TSV" ]; then
        NEW_LINES=$(wc -l < "$NEW_TSV")
        REF_LINES=$(wc -l < "$REF_TSV")
        echo "TSV lines: new=$NEW_LINES ref=$REF_LINES"

        # Diff count (tinyId-sorted for stable comparison)
        DIFF_COUNT=$(diff <(sort "$NEW_TSV") <(sort "$REF_TSV") | grep -c '^[<>]' || true)
        echo "TSV diff lines: $DIFF_COUNT"

        if [ "$DIFF_COUNT" -gt 0 ]; then
            echo "TSV differences (first 20):"
            diff <(sort "$NEW_TSV") <(sort "$REF_TSV") | grep '^[<>]' | head -20
        fi
    else
        echo "MISSING: $NEW_TSV or $REF_TSV"
    fi

    # Compare CSV embed files
    NEW_CSV="$OUTDIR/embed_${V}.csv"
    REF_CSV="$REF/embed_${V}_ML.csv"

    if [ -f "$NEW_CSV" ] && [ -f "$REF_CSV" ]; then
        DIFF_COUNT=$(diff <(sort "$NEW_CSV") <(sort "$REF_CSV") | grep -c '^[<>]' || true)
        echo "CSV diff lines: $DIFF_COUNT"
    fi
done

echo ""
echo "=== Validation complete ==="
