"""
Temporal pattern detection query module.

Classifies phrases into different types of temporal expressions.
"""

from typing import List, Dict, Optional
from pathlib import Path

from .module_base import QueryModule, QueryModuleConfig


class TemporalDetectorModule(QueryModule):
    """
    Query module for detecting temporal patterns in phrases.

    Classifies phrases into temporal categories:
    - recency_window: Recent time periods (last 30 days, past week)
    - age_range: Age-related expressions (18-65 years old, pediatric)
    - time_point: Specific points in time (at baseline, at diagnosis)
    - duration: Length of time (for 6 months, during treatment)
    - frequency: How often something occurs (daily, twice weekly)
    - not_temporal: Not a temporal expression

    Designed to identify temporal constraints and time-related language
    in CDE definitions for data harmonization.
    """

    @property
    def module_name(self) -> str:
        return "temporal"

    @property
    def output_categories(self) -> List[str]:
        return [
            "recency_window",
            "age_range",
            "time_point",
            "duration",
            "frequency",
            "not_temporal",
        ]

    @property
    def description(self) -> str:
        return "Detect temporal patterns (recency, age ranges, durations, frequencies)"

    def build_system_prompt(self) -> str:
        """Build system prompt for temporal detection."""
        prompt = """You are an expert at identifying temporal expressions and time-related language in medical and scientific text.

Your task is to classify phrases into specific temporal categories.

## Categories

**recency_window**: Phrases describing recent time periods relative to now or an event:
- "in the past 30 days"
- "within the last week"
- "over the previous month"
- "recent history of"
- Reference periods like "7-day recall"

**age_range**: Phrases specifying ages or age groups:
- "18 years or older"
- "between 5 and 12 years old"
- "pediatric patients"
- "elderly (>65)"
- "adult population"
- Age at specific events ("age at onset")

**time_point**: Specific moments or reference points in time:
- "at baseline"
- "at diagnosis"
- "pre-operative"
- "post-treatment"
- "upon admission"
- "at the time of"
- Specific dates or study visits

**duration**: Length or span of time:
- "for at least 6 months"
- "during the study period"
- "over 2 years"
- "throughout pregnancy"
- "length of hospital stay"
- Treatment durations

**frequency**: How often something occurs:
- "once daily"
- "twice weekly"
- "every 4 hours"
- "as needed"
- "per episode"
- Dosing frequencies

**not_temporal**: The phrase does not primarily express time:
- Anatomical terms
- Disease names
- Measurement units (unless time-based)
- Procedures without temporal aspect
- Instrument names

## Output Format

Respond with valid JSON only:
```json
{
  "category": "recency_window|age_range|time_point|duration|frequency|not_temporal",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation for the classification"
}
```

## Guidelines

1. Focus on the PRIMARY temporal meaning of the phrase
2. Some phrases may have multiple temporal aspects - choose the dominant one
3. Consider the CDE field context for disambiguation
4. Age-related phrases go to "age_range" even if they include durations
5. Time of day without recurrence goes to "time_point", with recurrence to "frequency"
6. Be conservative: if temporal aspect is incidental, use "not_temporal"
7. Medical staging (Stage I, Phase 2) is NOT temporal unless explicitly time-based"""

        # Add reference examples
        ref_examples = self.get_reference_examples()
        if ref_examples:
            prompt += "\n\n## Reference Examples\n"
            for cat, examples in ref_examples.items():
                prompt += f"\n**{cat}**:\n"
                for ex in examples[:4]:
                    prompt += f"- {ex}\n"

        return prompt

    def build_user_prompt_template(self) -> str:
        """Build user prompt template with placeholders."""
        return """Classify the temporal nature of this phrase:

**Phrase**: {phrase_text}

{context_section}

What type of temporal expression is this, if any?"""

    def get_reference_examples(self) -> Optional[Dict[str, List[str]]]:
        """
        Get reference examples for each category.
        """
        return {
            "recency_window": [
                "in the past 30 days",
                "within the last 2 weeks",
                "over the previous 6 months",
                "recent history",
                "7-day recall period",
            ],
            "age_range": [
                "18 years of age or older",
                "pediatric population",
                "between 40 and 65 years",
                "age at diagnosis",
                "elderly patients over 75",
            ],
            "time_point": [
                "at baseline",
                "upon hospital admission",
                "at the time of diagnosis",
                "pre-operative assessment",
                "post-discharge",
            ],
            "duration": [
                "for at least 3 months",
                "during the treatment period",
                "over the course of 1 year",
                "length of hospital stay",
                "throughout the study",
            ],
            "frequency": [
                "once daily",
                "three times per week",
                "every 8 hours",
                "as needed (PRN)",
                "per menstrual cycle",
            ],
            "not_temporal": [
                "blood pressure",
                "body mass index",
                "questionnaire",
                "laboratory test",
                "diagnosis code",
            ],
        }


# Alias for registry
TemporalDetector = TemporalDetectorModule
