"""
Instrument family detection query module for LLM adjudication.

Classifies instrument names into known families (e.g., Neuro-QOL, PROMIS, MDS-UPDRS)
for uncertain cases where pattern-based detection has low confidence.

Used as a fallback when the rule-based InstrumentFamilyDetector cannot
confidently assign a family.
"""

from typing import List, Dict, Optional
from pathlib import Path

from .module_base import QueryModule, QueryModuleConfig


class InstrumentFamilyDetectorModule(QueryModule):
    """
    Query module for detecting instrument family membership.

    Classifies instruments into known families:
    - neuro-qol: Neuro-QOL subscales (e.g., Ability to Participate, Positive Affect)
    - promis: PROMIS instruments (e.g., PROMIS Anxiety, PROMIS Depression)
    - mds-updrs: MDS-UPDRS parts and variants
    - sf-health: SF-36, SF-12, Short Form Health Survey
    - beck: Beck Depression/Anxiety Inventory
    - phq: Patient Health Questionnaire family (PHQ-9, PHQ-8)
    - gad: Generalized Anxiety Disorder scales
    - mmse: Mini-Mental State Examination
    - moca: Montreal Cognitive Assessment
    - nihss: NIH Stroke Scale
    - pdqualif: Parkinson's Disease Quality of Life
    - dsq: DePaul Symptom Questionnaire
    - rome: Rome criteria modules
    - other_instrument: Recognized instrument but unknown family
    - not_instrument: Not an instrument name
    """

    @property
    def module_name(self) -> str:
        return "instrument_family"

    @property
    def output_categories(self) -> List[str]:
        return [
            "neuro-qol",
            "promis",
            "mds-updrs",
            "sf-health",
            "beck",
            "phq",
            "gad",
            "mmse",
            "moca",
            "nihss",
            "pdqualif",
            "dsq",
            "rome",
            "other_instrument",
            "not_instrument",
        ]

    @property
    def description(self) -> str:
        return "Detect instrument family membership for family grouping"

    def build_system_prompt(self) -> str:
        """Build system prompt for instrument family detection."""
        prompt = """You are an expert at identifying standardized research instruments, questionnaires, and assessment tools used in clinical research and biomedical studies.

Your task is to classify instruments into their known families to enable grouping of related subscales and versions.

## Instrument Families

**neuro-qol**: Quality of Life in Neurological Disorders
- Examples: Neuro-QOL Ability to Participate in SRA, Neuro-QOL Positive Affect, Neuro-QOL Cognitive Function
- Look for: "Neuro-QOL" or "Quality of Life in Neurological"

**promis**: Patient-Reported Outcomes Measurement Information System
- Examples: PROMIS Anxiety, PROMIS Depression, PROMIS Physical Function
- Look for: "PROMIS" prefix

**mds-updrs**: Movement Disorder Society - Unified Parkinson's Disease Rating Scale
- Examples: MDS-UPDRS Part I, MDS-UPDRS Part II, MDS UPDRS
- Look for: "MDS-UPDRS", "MDS UPDRS", "Unified Parkinson's Disease Rating Scale"

**sf-health**: Short Form Health Survey family
- Examples: SF-36, SF-12, 36-item Short Form Health Survey
- Look for: "SF-36", "SF-12", "Short Form Health Survey", "Short-Form"

**beck**: Beck Inventory family
- Examples: Beck Depression Inventory, Beck Anxiety Inventory, BDI-II, BAI
- Look for: "Beck Depression", "Beck Anxiety", "BDI", "BAI"

**phq**: Patient Health Questionnaire family
- Examples: PHQ-9, PHQ-8, PHQ-2, Patient Health Questionnaire
- Look for: "PHQ-", "Patient Health Questionnaire"

**gad**: Generalized Anxiety Disorder scales
- Examples: GAD-7, GAD-2
- Look for: "GAD-"

**mmse**: Mini-Mental State Examination
- Examples: MMSE, Mini-Mental State Examination
- Look for: "MMSE", "Mini-Mental"

**moca**: Montreal Cognitive Assessment
- Examples: MoCA, Montreal Cognitive Assessment
- Look for: "MoCA", "Montreal Cognitive"

**nihss**: NIH Stroke Scale
- Examples: NIHSS, NIH Stroke Scale, National Institutes of Health Stroke Scale
- Look for: "NIHSS", "NIH Stroke Scale"

**pdqualif**: Parkinson's Disease Quality of Life
- Examples: PDQUALIF, Parkinson's Disease Quality of Life
- Look for: "PDQUALIF", "Parkinson's Disease Quality of Life"

**dsq**: DePaul Symptom Questionnaire
- Examples: DSQ, DePaul Symptom Questionnaire
- Look for: "DSQ", "DePaul Symptom"

**rome**: Rome Diagnostic Criteria for Functional GI Disorders
- Examples: Rome III Constipation Module, RCM3, Rome IV
- Look for: "Rome II", "Rome III", "Rome IV", "RCM"

**other_instrument**: This IS an instrument/questionnaire/assessment tool, but doesn't belong to any of the above families
- Use this for recognized instruments that don't match known families
- Examples: Glasgow Coma Scale, CAGE questionnaire, Epworth Sleepiness Scale

**not_instrument**: NOT an instrument name
- Anatomical terms, diseases, procedures, generic descriptors
- Use this only if the phrase is clearly NOT a research instrument

## Output Format

Respond with valid JSON only:
```json
{
  "category": "neuro-qol|promis|mds-updrs|sf-health|beck|phq|gad|mmse|moca|nihss|pdqualif|dsq|rome|other_instrument|not_instrument",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation identifying the instrument and why it belongs to this family"
}
```

## Guidelines

1. Look for family-identifying keywords (PROMIS, Neuro-QOL, PHQ, etc.)
2. Consider abbreviations and acronyms in the verbatim forms
3. If the instrument is recognized but doesn't fit known families, use "other_instrument"
4. Only use "not_instrument" if clearly NOT an instrument/questionnaire/scale
5. Higher confidence (0.8+) when family-identifying keywords are present
6. Lower confidence (0.5-0.7) when family assignment is based on partial patterns"""

        # Add reference examples if available
        ref_examples = self.get_reference_examples()
        if ref_examples:
            prompt += "\n\n## Reference Examples\n"
            for cat, examples in ref_examples.items():
                if examples:
                    prompt += f"\n**{cat}**:\n"
                    for ex in examples[:3]:
                        prompt += f"- {ex}\n"

        return prompt

    def build_user_prompt_template(self) -> str:
        """Build user prompt template with placeholders."""
        return """Classify this instrument into its family:

**Instrument Name**: {phrase_text}

{context_section}

Which instrument family does this belong to?"""

    def get_reference_examples(self) -> Optional[Dict[str, List[str]]]:
        """
        Get reference examples for each family.

        These help the LLM understand each family's instruments.
        """
        # Load from reference file if available
        ref_data = self.load_reference_data()
        if ref_data:
            return {"other_instrument": ref_data[:20]}

        # Default examples per family
        return {
            "neuro-qol": [
                "Neuro-QOL Ability to Participate in SRA",
                "Neuro-QOL Positive Affect",
                "Neuro-QOL Cognitive Function",
            ],
            "promis": [
                "PROMIS Anxiety",
                "PROMIS Depression",
                "PROMIS Physical Function",
            ],
            "mds-updrs": [
                "Movement Disorder Society - Unified Parkinson's Disease Rating Scale (MDS UPDRS)",
                "MDS-UPDRS Part I",
                "MDS-UPDRS Part II",
            ],
            "sf-health": [
                "SF-36 Health Survey",
                "SF-12",
                "36-item Short Form Health Survey",
            ],
            "beck": [
                "Beck Depression Inventory",
                "Beck Anxiety Inventory",
                "BDI-II",
            ],
            "phq": [
                "PHQ-9",
                "PHQ-8",
                "Patient Health Questionnaire",
            ],
            "pdqualif": [
                "Parkinson's Disease Quality of Life (PDQUALIF)",
                "PDQUALIF form",
            ],
            "dsq": [
                "DePaul Symptom Questionnaire (DSQ)",
            ],
            "rome": [
                "Rome III Constipation Module (RCM3)",
                "Rome IV Diagnostic Criteria",
            ],
            "other_instrument": [
                "Glasgow Coma Scale",
                "CAGE questionnaire",
                "Epworth Sleepiness Scale",
                "Social interaction test",
                "Partition test",
            ],
        }


# Alias for registry
InstrumentFamilyDetector = InstrumentFamilyDetectorModule
