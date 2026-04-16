#!/bin/bash
# Validation part 2: extract embeds + compare against reference
set -euo pipefail

source /mnt/d/GT/Professional/NLM_CDE/cde_python/py313_base/bin/activate
cd /mnt/d/GT/Professional/NLM_CDE/coding/cde_analyzer

OUTDIR=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/validation
REF=/mnt/d/GT/Professional/NLM_CDE/work_202602/phrase_curation3/test_v7/ML
SCHEMA=/mnt/d/GT/Professional/NLM_CDE/coding/cde_analyzer/config/embed_path_schemas/NQD.csv

echo "=== Step 6: Extract embed files ==="
python cde_analyzer.py extract_embed \
    --batch-dir "$OUTDIR" \
    --batch-variants MTSFPT,MTSTPT \
    --path-file "$SCHEMA" \
    -m CDE \
    --embed-separator ' :--: '

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

        # Diff on sorted tinyId lines
        DIFF_COUNT=$(diff <(sort "$NEW_TSV") <(sort "$REF_TSV") | grep -c '^[<>]' || true)
        echo "TSV diff lines: $DIFF_COUNT"

        if [ "$DIFF_COUNT" -gt 0 ] && [ "$DIFF_COUNT" -le 100 ]; then
            echo ""
            echo "Changed tinyIds (new vs ref):"
            # Extract tinyIds that differ
            diff <(sort "$NEW_TSV") <(sort "$REF_TSV") | grep '^[<>]' | awk -F'\t' '{print $1, substr($0,1,3)}' | sed 's/^< /NEW: /; s/^> /REF: /' | sort | head -40
        fi
    else
        echo "MISSING: $NEW_TSV or $REF_TSV"
    fi

    # Compare CSV embed files
    NEW_CSV="$OUTDIR/embed_${V}.csv"
    REF_CSV="$REF/embed_${V}_ML.csv"

    if [ -f "$NEW_CSV" ] && [ -f "$REF_CSV" ]; then
        DIFF_COUNT_CSV=$(diff <(sort "$NEW_CSV") <(sort "$REF_CSV") | grep -c '^[<>]' || true)
        echo "CSV diff lines: $DIFF_COUNT_CSV"
    fi
done

echo ""
echo "=== Detailed diff: extract differing tinyIds for MTSFPT ==="
NEW_TSV="$OUTDIR/embed_MTSFPT.tsv"
REF_TSV="$REF/embed_MTSFPT_ML.tsv"

if [ -f "$NEW_TSV" ] && [ -f "$REF_TSV" ]; then
    # Get tinyIds that differ
    diff <(sort "$NEW_TSV") <(sort "$REF_TSV") | grep '^[<>]' | awk -F'\t' '{print $1}' | sed 's/^[<>] //' | sort -u > /tmp/diff_tinyids.txt
    N_DIFF=$(wc -l < /tmp/diff_tinyids.txt)
    echo "Unique tinyIds with differences: $N_DIFF"

    if [ "$N_DIFF" -gt 0 ] && [ "$N_DIFF" -le 50 ]; then
        echo ""
        echo "Side-by-side for each differing tinyId:"
        while IFS= read -r tid; do
            echo ""
            echo "  tinyId: $tid"
            echo "  NEW: $(grep "^${tid}	" "$NEW_TSV" | cut -f2 | head -c 200)"
            echo "  REF: $(grep "^${tid}	" "$REF_TSV" | cut -f2 | head -c 200)"
        done < /tmp/diff_tinyids.txt
    fi
fi

echo ""
echo "=== Validation complete ==="
