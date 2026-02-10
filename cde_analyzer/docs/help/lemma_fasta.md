# `lemma_fasta` Command

Extract CDE fields as pseudo-FASTA format for genomic tools.

## Overview

The `lemma_fasta` command encodes lemmatized CDE text as uint16 tokens in base85 encoding, producing output compatible with genomic repeat-finder tools. This enables the use of established bioinformatics algorithms for pattern detection in CDE text data.

## Concept

Genomic tools excel at finding repeated sequences in DNA/protein data. By encoding lemmatized words as numeric tokens (similar to nucleotides), we can leverage these tools for phrase detection:

| Domain | Alphabet | Token Size |
|--------|----------|------------|
| DNA | A, C, G, T | 4 symbols |
| Protein | 20 amino acids | 20 symbols |
| CDE Text | Vocabulary words | ~65K symbols (uint16) |

## Usage

```bash
cde-analyzer lemma_fasta --input INPUT -m MODEL -o OUTPUT [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Input JSON file |
| `-m, --model` | Pydantic model (required) |
| `-o, --output` | Output path prefix (multiple files generated) |
| `--path-file` | File specifying fields to extract (as `name:path` pairs) |
| `--output-format` | Output format: `pfasta` or `lfasta` (default: `pfasta`) |

### ID Filtering

| Argument | Description |
|----------|-------------|
| `--id-list` | List of tinyIds to process |
| `--id-file` | File containing tinyIds |
| `--id-type` | Type of ID (default: tinyId) |
| `--exclude / --no-exclude` | Exclude or include specified IDs (default: exclude) |

### Processing Options

| Argument | Description |
|----------|-------------|
| `--remove-spaces` | Remove spaces from lemmatized content (default: True) |
| `--remove-stopwords` | Remove common English stop words |
| `--min-freq N` | Minimum token frequency for uint16 encoding (default: 1) |

## Output Files

Multiple files are generated with the output prefix:

### JSON Outputs

| File | Content |
|------|---------|
| `{output}_lemmatized.json` | Simplified model with lemmatized text |
| `{output}_verbatim.json` | Simplified model with original text |
| `{output}_b85.json` | Base85 encoded strings per field |
| `{output}_b85_concat.json` | Base85 of concatenated `fasta_uint16` key |
| `{output}_vocab.json` | Vocabulary dictionary (lemma → uint16 mapping) |

### FASTA Output

| File | Content |
|------|---------|
| `{output}.fasta` | Pseudo-FASTA with tinyId headers and base85 sequences |

## FASTA Format

```
>abc123
YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXo...
>def456
MTIzNDU2Nzg5MGFiY2RlZmdoaWprbG1ub3...
```

Where:
- Header line: `>tinyId`
- Sequence line: Base85-encoded uint16 token sequence

## Example

```bash
cde-analyzer lemma_fasta \
    --input cdes.json \
    -m CDEItem \
    -o output/cde_fasta \
    --path-file fields.txt \
    --remove-stopwords \
    --min-freq 3
```

### Path File Format

```
Name:designations[0].designation
Definition:definitions[0].definition
Question:referenceDocuments[*].document
```

## Token Encoding

1. **Lemmatization**: Text is lemmatized (e.g., "running" → "run")
2. **Vocabulary Building**: Unique lemmas are assigned uint16 IDs
3. **Frequency Filtering**: Tokens below `--min-freq` are encoded as 0x0000
4. **Base85 Encoding**: uint16 sequences are encoded in base85 for FASTA compatibility

### Vocabulary JSON

```json
{
  "patient": 1,
  "report": 2,
  "outcome": 3,
  "measure": 4,
  ...
}
```

## Use Case: Genomic Repeat Finders

The output can be processed by modified genomic tools:

1. **RepeatMasker-like tools**: Find repeated phrases
2. **BLAST-like tools**: Find similar text across CDEs
3. **Suffix array tools**: Build indices for pattern matching

> **Note**: Standard genomic tools need modification to decode base85 and work with uint16 tokens instead of nucleotides.

## Workflow

1. **Export to FASTA**: `cde-analyzer lemma_fasta ...`
2. **Run repeat finder**: Modified genomic tool on FASTA output
3. **Decode results**: Convert uint16 tokens back to words using vocabulary
4. **Curate phrases**: Review and select phrases for removal
5. **Strip phrases**: Use `strip_phrases` command on original data

## See Also

- [`extract_embed`](extract_embed.md) - Extract fields for transformer embeddings
- [`phrase_builder`](phrase_builder.md) - K-mer analysis for phrase detection
- [`phrase_miner`](phrase_miner.md) - Native phrase mining without genomic tools
