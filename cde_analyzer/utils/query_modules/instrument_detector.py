"""
Instrument/device name detection query module.

Classifies phrases as instrument names, possible instruments, or non-instruments.
"""

from typing import List, Dict, Optional
from pathlib import Path

from .module_base import QueryModule, QueryModuleConfig


class InstrumentDetectorModule(QueryModule):
    """
    Query module for detecting instrument and device names in phrases.

    Classifies phrases into:
    - instrument_name: Definitively an instrument or measurement device
    - possible_instrument: Could be an instrument but context is ambiguous
    - not_instrument: Not an instrument name

    Designed to identify measurement instruments, medical devices, laboratory
    equipment, and scientific apparatus mentioned in CDE definitions.
    """

    @property
    def module_name(self) -> str:
        return "instrument"

    @property
    def output_categories(self) -> List[str]:
        return ["instrument_name", "possible_instrument", "not_instrument"]

    @property
    def description(self) -> str:
        return "Detect instrument and measurement device names in phrases"

    def build_system_prompt(self) -> str:
        """Build system prompt for instrument detection."""
        prompt = """You are an expert at identifying scientific instruments, measurement devices, and medical equipment in text.

Your task is to classify phrases as instrument names or not.

## Categories

**instrument_name**: The phrase IS definitively the name of:
- Laboratory instruments (spectrophotometer, centrifuge, pipette)
- Medical devices (MRI scanner, ECG machine, stethoscope)
- Measurement tools (caliper, thermometer, scale, ruler)
- Scientific apparatus (microscope, oscilloscope, chromatograph)
- Survey instruments (questionnaire names like "Beck Depression Inventory", "SF-36")
- Assessment tools with proper names (MMSE, PHQ-9, Glasgow Coma Scale)

**possible_instrument**: The phrase MIGHT be an instrument but:
- Context is ambiguous
- Could refer to a procedure rather than a device
- Is a generic term that could be instrument-related
- Is an abbreviation that might refer to an instrument

**not_instrument**: The phrase is NOT an instrument:
- Anatomical terms (heart, brain, blood)
- Diseases or conditions (diabetes, hypertension)
- Procedures without device names (surgery, examination)
- Units of measurement (mg, mmHg, kg)
- Time periods or frequencies
- Generic descriptors (normal, abnormal, present)

## Output Format

Respond with valid JSON only:
```json
{
  "category": "instrument_name|possible_instrument|not_instrument",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation for the classification"
}
```

## Guidelines

1. Consider the verbatim forms - original capitalization may indicate proper names
2. Consider the field context - where does this phrase appear in the CDE?
3. Instrument names often include brand names, model numbers, or standardized test names
4. Be conservative: if uncertain, use "possible_instrument"
5. Survey instruments and assessment scales count as instruments"""

        # Add reference examples if available
        ref_examples = self.get_reference_examples()
        if ref_examples:
            prompt += "\n\n## Reference Examples\n"
            for cat, examples in ref_examples.items():
                prompt += f"\n**{cat}**:\n"
                for ex in examples[:5]:
                    prompt += f"- {ex}\n"

        return prompt

    def build_user_prompt_template(self) -> str:
        """Build user prompt template with placeholders."""
        return """Classify this phrase as an instrument name or not:

**Phrase**: {phrase_text}

{context_section}

Is this phrase an instrument, measurement device, or assessment tool name?"""

    def get_reference_examples(self) -> Optional[Dict[str, List[str]]]:
        """
        Get reference examples for each category.

        These help the LLM understand the classification criteria.
        """
        # Load from reference file if available
        ref_data = self.load_reference_data()
        if ref_data:
            return {"instrument_name": ref_data[:20]}

        # Default examples
        return {
            "instrument_name": [
                "Beck Depression Inventory",
                "Mini-Mental State Examination",
                "MRI scanner",
                "flow cytometer",
                "spectrophotometer",
                "Glasgow Coma Scale",
                "PHQ-9",
                "SF-36 Health Survey",
                "electrocardiogram",
                "pulse oximeter",
            ],
            "possible_instrument": [
                "imaging",
                "scan",
                "measurement tool",
                "diagnostic test",
                "assessment",
            ],
            "not_instrument": [
                "blood pressure",
                "heart rate",
                "body mass index",
                "diagnosis",
                "patient",
                "treatment",
                "mg/dL",
                "baseline",
            ],
        }


# Alias for registry
InstrumentDetector = InstrumentDetectorModule
