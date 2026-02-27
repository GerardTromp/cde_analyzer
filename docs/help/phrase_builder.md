# `phrase_builder` Command

Build and analyze repeated phrases using k-mer analysis.

## Overview

The `phrase_builder` command performs k-mer (n-gram) analysis on CDE text fields to identify repeated phrases across records. It generates frequency statistics and visualizations to help identify candidate phrases for curation and removal.

> **Note**: For advanced phrase detection with masking and subsumption filtering, consider using the [`phrase_miner`](phrase_miner.md) command instead.

## Usage

```bash
cde-analyzer phrase_builder -i INPUT -m MODEL -o OUTPUT
```

## Arguments

| Argument | Description |
|----------|-------------|
| `-i, --input` | Path to input JSON file (or JSON with `lemmatized` key) |
| `-m, --model` | Pydantic model name (e.g., `CDEItem`, `CDEForm`) |
| `-o, --output` | Output path prefix (timestamp will be appended) |

## How It Works

1. **Load Data**: Reads CDE JSON file, supports both raw and pre-lemmatized formats
2. **Extract Fields**: Pulls text from Name, Question, and Definition fields
3. **Tokenize**: Breaks text into tokens for k-mer analysis
4. **Generate K-mers**: Creates k-mers for k values from 3 to 17
5. **Count Frequencies**: Tallies occurrences of each k-mer
6. **Visualize**: Generates plot of k-mer frequency distributions
7. **Export**: Saves k-mer data to timestamped CSV file

## Output

The command produces:

- **CSV file**: `{output}_{timestamp}.csv` containing all k-mers and their counts
- **Visualization**: Plot showing k-mer count distributions across different k values

### CSV Output Format

| Column | Description |
|--------|-------------|
| k | K-mer length |
| kmer | The token sequence |
| count | Number of occurrences |

## Example

```bash
cde-analyzer phrase_builder \
    -i cdes_lemmatized.json \
    -m CDEItem \
    -o output/kmer_analysis
```

This produces:
- `output/kmer_analysis_20250123-143052.csv`
- Interactive plot window

## K-mer Range

The default k-mer range is 3 to 17 tokens:

| K | Use Case |
|---|----------|
| 3-5 | Short phrases, may need careful curation |
| 6-10 | Medium phrases, often meaningful patterns |
| 11-17 | Long phrases, typically boilerplate text |

## Workflow

Typical phrase curation workflow:

1. **Run phrase_builder** to identify repeated phrases
2. **Review CSV output** - examine high-frequency k-mers
3. **Curate list** - decide which phrases to remove
4. **Create phrases file** for `strip_phrases` command
5. **Strip phrases** from data before embedding

## Input Format

Accepts either:

1. **Raw CDE JSON**: List of CDE records
2. **Lemmatized format**: JSON with `lemmatized` key containing pre-processed records

```json
{
  "lemmatized": [
    {"tinyId": "abc123", "Name": "...", "Definition": "..."},
    ...
  ]
}
```

## Analyzed Fields

Currently extracts text from:

- `Name` - CDE name/title
- `Question` - Question text if present
- `Definition` - CDE definition

## Visualization

The generated plot shows:

- X-axis: K-mer frequency (occurrence count)
- Y-axis: Proportion of k-mers at that frequency
- Separate curves for each k value (3-17)

This helps identify the frequency threshold for phrase curation - k-mers with high counts are candidates for removal.

## See Also

- [`phrase_miner`](phrase_miner.md) - Advanced phrase detection with iterative descent
- [`phrase`](phrase.md) - Original phrase detection implementation
- [`strip_phrases`](strip_phrases.md) - Remove detected phrases from data
