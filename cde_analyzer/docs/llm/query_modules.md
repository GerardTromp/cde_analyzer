# Query Modules

Classification modules for different semantic tasks.

## Overview

Query modules define specific classification tasks with their own categories, prompts, and response parsing. Each module is designed for a particular type of phrase analysis.

## Available Modules

| Module | Purpose | Categories |
|--------|---------|------------|
| `instrument` | Detect measurement instruments, devices, assessment tools | 3 categories |
| `temporal` | Identify temporal patterns and time expressions | 6 categories |

## Instrument Detection Module

**Module Name**: `instrument`

Identifies measurement instruments, medical devices, laboratory equipment, and standardized assessment tools in CDE definitions.

### Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `instrument_name` | Definitively an instrument or device | "Beck Depression Inventory", "MRI scanner", "flow cytometer" |
| `possible_instrument` | Might be an instrument, context ambiguous | "imaging", "measurement tool", "assessment" |
| `not_instrument` | Not an instrument | "blood pressure", "diagnosis", "mg/dL" |

### What Counts as an Instrument?

**Included**:

- Laboratory instruments (spectrophotometer, centrifuge, pipette)
- Medical devices (MRI scanner, ECG machine, pulse oximeter)
- Measurement tools (caliper, thermometer, ruler, scale)
- Scientific apparatus (microscope, oscilloscope, chromatograph)
- Survey instruments (Beck Depression Inventory, SF-36, PHQ-9)
- Assessment tools (MMSE, Glasgow Coma Scale, Apgar Score)

**Excluded**:

- Anatomical terms (heart, brain, blood)
- Diseases or conditions (diabetes, hypertension)
- Procedures without device names (surgery, examination)
- Units of measurement (mg, mmHg, kg)
- Generic descriptors (normal, abnormal, present)

### Usage

```bash
cde_analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module instrument
```

### Reference File Support

Provide a list of known instruments to improve accuracy:

```bash
cde_analyzer llm_classify \
  --input-dir phrase_output \
  --module instrument \
  --reference-file known_instruments.tsv
```

**Reference File Format** (TSV):
```tsv
Beck Depression Inventory
Mini-Mental State Examination
Glasgow Coma Scale
PHQ-9
SF-36 Health Survey
```

### Example Output

```tsv
phrase_id	phrase_text	category	quintile	confidence
phrase_00042	beck depression inventory	instrument_name	highly_likely	0.95
phrase_00108	blood pressure measurement	possible_instrument	indeterminate	0.52
phrase_00215	patient age	not_instrument	likely	0.78
```

---

## Temporal Detection Module

**Module Name**: `temporal`

Identifies different types of temporal expressions in CDE definitions, useful for understanding time constraints and data collection windows.

### Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `recency_window` | Recent time periods relative to an event | "in the past 30 days", "within the last week" |
| `age_range` | Age-related expressions | "18 years or older", "pediatric", "elderly" |
| `time_point` | Specific moments in time | "at baseline", "upon admission", "pre-operative" |
| `duration` | Length or span of time | "for 6 months", "during treatment", "over 2 years" |
| `frequency` | How often something occurs | "daily", "twice weekly", "every 4 hours" |
| `not_temporal` | Not primarily temporal | "blood pressure", "questionnaire", "diagnosis" |

### Category Details

#### recency_window

Phrases describing recent time periods:

- "in the past 30 days"
- "within the last 2 weeks"
- "over the previous 6 months"
- "recent history of"
- "7-day recall period"

#### age_range

Phrases specifying ages or age groups:

- "18 years of age or older"
- "pediatric population"
- "between 40 and 65 years"
- "age at diagnosis"
- "elderly patients over 75"

#### time_point

Specific moments or reference points:

- "at baseline"
- "upon hospital admission"
- "at the time of diagnosis"
- "pre-operative assessment"
- "post-discharge"

#### duration

Length or span of time:

- "for at least 3 months"
- "during the treatment period"
- "over the course of 1 year"
- "length of hospital stay"
- "throughout the study"

#### frequency

How often something occurs:

- "once daily"
- "three times per week"
- "every 8 hours"
- "as needed (PRN)"
- "per menstrual cycle"

### Usage

```bash
cde_analyzer llm_classify \
  --input-dir phrase_output \
  --output-dir llm_output \
  --module temporal
```

### Example Output

```tsv
phrase_id	phrase_text	category	quintile	confidence
phrase_00015	in the past 30 day	recency_window	highly_likely	0.92
phrase_00089	18 year of age	age_range	highly_likely	0.88
phrase_00134	at baseline	time_point	highly_likely	0.95
phrase_00201	twice weekly	frequency	likely	0.76
phrase_00267	blood glucose level	not_temporal	likely	0.82
```

---

## Module Architecture

### Base Class

All modules inherit from `QueryModule`:

```python
class QueryModule(ABC):
    @property
    def module_name(self) -> str: ...
    @property
    def output_categories(self) -> List[str]: ...
    def build_system_prompt(self) -> str: ...
    def build_user_prompt_template(self) -> str: ...
    def parse_response(self, response_text: str) -> Tuple[str, float, str]: ...
```

### Prompt Structure

Each module defines:

1. **System Prompt**: Task description, category definitions, output format
2. **User Prompt Template**: Per-phrase prompt with placeholders
3. **Reference Examples**: Optional examples for few-shot learning

### Response Format

LLMs are instructed to respond with JSON:

```json
{
  "category": "instrument_name",
  "confidence": 0.92,
  "reasoning": "Beck Depression Inventory is a well-known standardized assessment tool for measuring depression severity."
}
```

---

## Creating Custom Modules

### Module Template

Create a new file in `utils/query_modules/`:

```python
from typing import List, Dict, Optional
from .module_base import QueryModule

class MyDetectorModule(QueryModule):
    @property
    def module_name(self) -> str:
        return "my_detector"

    @property
    def output_categories(self) -> List[str]:
        return ["category_a", "category_b", "not_relevant"]

    def build_system_prompt(self) -> str:
        return """Your task description here...

Categories:
- category_a: Definition...
- category_b: Definition...
- not_relevant: Default category...

Respond with JSON:
{"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}
"""

    def build_user_prompt_template(self) -> str:
        return """Classify this phrase:

**Phrase**: {phrase_text}

{context_section}
"""
```

### Registration

Add to the registry in `utils/query_modules/__init__.py`:

```python
_MODULE_REGISTRY = {
    "instrument": "utils.query_modules.instrument_detector.InstrumentDetectorModule",
    "temporal": "utils.query_modules.temporal_detector.TemporalDetectorModule",
    "my_detector": "utils.query_modules.my_detector.MyDetectorModule",  # Add this
}

MODULE_DESCRIPTIONS = {
    "instrument": "Detect instrument/device names in phrases",
    "temporal": "Detect temporal patterns",
    "my_detector": "Description of my detector",  # Add this
}
```

### CLI Update

Add to `actions/llm_classify/cli.py`:

```python
subparser.add_argument(
    "-m", "--module",
    required=True,
    choices=["instrument", "temporal", "my_detector"],  # Add choice
    help="Query module to use for classification."
)
```

---

## Best Practices

### Module Design

1. **Clear Categories**: Each category should be mutually exclusive
2. **Default Category**: Include a "not_X" category for non-matching phrases
3. **Detailed Prompts**: Provide explicit definitions and examples
4. **Reference Examples**: Include positive and negative examples

### Prompt Engineering

1. **Be Specific**: Define exactly what each category includes/excludes
2. **Use Examples**: Few-shot examples improve accuracy significantly
3. **JSON Output**: Always request structured JSON responses
4. **Confidence Guidance**: Explain when to use high vs. low confidence

### Testing

1. **Sample Dataset**: Test with representative phrases first
2. **Edge Cases**: Include ambiguous examples in testing
3. **Multi-Provider**: Compare results across different LLMs
4. **Iterate**: Refine prompts based on classification errors

## See Also

- [llm_classify Command](llm_classify.md) - Full command reference
- [Configuration](configuration.md) - API key setup
- [LLM Overview](index.md) - Module introduction
