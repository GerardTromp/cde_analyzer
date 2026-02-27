"""
Abstract base class for query modules.

Query modules define specific classification tasks with their own
prompts, categories, and response parsing logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from CDE_Schema.LLM_Classification import PhraseContext


@dataclass
class QueryModuleConfig:
    """Configuration for a query module."""
    module_name: str
    output_categories: List[str]
    reference_file: Optional[Path] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


class QueryModule(ABC):
    """
    Abstract base class for classification query modules.

    Each module defines:
    - A specific classification task (e.g., instrument detection)
    - Output categories
    - System and user prompts
    - Response parsing logic
    """

    def __init__(
        self,
        config: Optional[QueryModuleConfig] = None,
        reference_file: Optional[Path] = None,
    ):
        """
        Initialize query module.

        Args:
            config: Module configuration
            reference_file: Path to reference data file (e.g., known instruments)
        """
        self._config = config or QueryModuleConfig(
            module_name=self.module_name,
            output_categories=self.output_categories,
        )
        self._reference_file = reference_file
        self._reference_data: Optional[List[str]] = None

    @property
    @abstractmethod
    def module_name(self) -> str:
        """
        Unique identifier for this module.

        Returns:
            Module name (e.g., "instrument", "temporal")
        """
        pass

    @property
    @abstractmethod
    def output_categories(self) -> List[str]:
        """
        Valid output categories for this classification.

        Returns:
            List of category names (e.g., ["instrument_name", "not_instrument"])
        """
        pass

    @property
    def description(self) -> str:
        """
        Human-readable description of what this module does.

        Returns:
            Description string
        """
        return f"Query module: {self.module_name}"

    @abstractmethod
    def build_system_prompt(self) -> str:
        """
        Build the system prompt for this classification task.

        Should include:
        - Task description
        - Output format instructions (JSON)
        - Category definitions
        - Any reference examples

        Returns:
            Complete system prompt
        """
        pass

    @abstractmethod
    def build_user_prompt_template(self) -> str:
        """
        Build the user prompt template with placeholders.

        Available placeholders:
        - {phrase_text}: Lemmatized phrase text
        - {verbatim_forms}: Pipe-separated original forms
        - {field_contexts}: Field paths and surrounding text
        - {frequency}: Occurrence count
        - {n_tinyids}: Number of unique documents

        Returns:
            User prompt template string
        """
        pass

    def format_phrase_context(self, phrase: PhraseContext) -> str:
        """
        Format phrase context for inclusion in prompt.

        Args:
            phrase: PhraseContext object

        Returns:
            Formatted context string
        """
        lines = []

        # Verbatim forms
        if phrase.verbatim_forms:
            forms = " | ".join(phrase.verbatim_forms[:10])  # Limit to 10
            if len(phrase.verbatim_forms) > 10:
                forms += f" ... (+{len(phrase.verbatim_forms) - 10} more)"
            lines.append(f"Verbatim forms: {forms}")

        # Field contexts
        if phrase.field_contexts:
            lines.append("Field contexts:")
            for ctx in phrase.field_contexts[:5]:  # Limit to 5 contexts
                field_path = ctx.field_path
                # Show surrounding text if available
                if ctx.before_text or ctx.after_text:
                    before = ctx.before_text[-50:] if ctx.before_text else ""
                    after = ctx.after_text[:50] if ctx.after_text else ""
                    context_text = f"...{before}[{ctx.text}]{after}..."
                else:
                    context_text = ctx.text
                lines.append(f"  - {field_path}: {context_text}")

        # Statistics
        lines.append(f"Frequency: {phrase.frequency} occurrences in {phrase.n_tinyids} documents")

        return "\n".join(lines)

    def load_reference_data(self) -> Optional[List[str]]:
        """
        Load reference data from file.

        Reference files are TSV with at least one column containing
        reference items (e.g., known instrument names).

        Returns:
            List of reference items or None
        """
        if self._reference_data is not None:
            return self._reference_data

        if self._reference_file is None or not self._reference_file.exists():
            return None

        try:
            items = []
            with open(self._reference_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Take first column if TSV
                        parts = line.split("\t")
                        items.append(parts[0].strip())
            self._reference_data = items
            return items
        except Exception:
            return None

    def get_reference_examples(self) -> Optional[Dict[str, List[str]]]:
        """
        Get reference examples organized by category.

        Override this method to provide category-specific examples.

        Returns:
            Dict mapping category to list of examples, or None
        """
        return None

    def parse_response(
        self,
        response_text: str,
    ) -> Tuple[str, float, str]:
        """
        Parse LLM response to extract classification.

        Default implementation expects JSON with category, confidence, reasoning.
        Override for custom parsing logic.

        Args:
            response_text: Raw LLM response text

        Returns:
            Tuple of (category, confidence, reasoning)
        """
        import json
        import re

        # Try to extract JSON from response
        try:
            # Look for JSON object in response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)

            category = data.get("category", self.output_categories[0])
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            # Validate category
            if category not in self.output_categories:
                # Try fuzzy match
                category_lower = category.lower()
                for valid_cat in self.output_categories:
                    if valid_cat.lower() in category_lower or category_lower in valid_cat.lower():
                        category = valid_cat
                        break
                else:
                    category = self.output_categories[0]

            # Clamp confidence
            confidence = max(0.0, min(1.0, confidence))

            return category, confidence, reasoning

        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback: try to find category keywords in response
            response_lower = response_text.lower()
            for cat in self.output_categories:
                if cat.lower() in response_lower:
                    return cat, 0.5, f"Extracted from non-JSON response: {response_text[:200]}"

            return self.output_categories[0], 0.0, f"Failed to parse response: {response_text[:200]}"

    def validate_category(self, category: str) -> str:
        """
        Validate and normalize category name.

        Args:
            category: Category from LLM response

        Returns:
            Valid category name
        """
        if category in self.output_categories:
            return category

        # Try case-insensitive match
        category_lower = category.lower()
        for valid_cat in self.output_categories:
            if valid_cat.lower() == category_lower:
                return valid_cat

        # Return default
        return self.output_categories[0]

    def get_json_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for expected LLM output.

        Useful for providers that support structured output.

        Returns:
            JSON schema dict
        """
        return {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": self.output_categories,
                    "description": "Classification category",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence score (0.0-1.0)",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief reasoning for the classification",
                },
            },
            "required": ["category", "confidence", "reasoning"],
        }
