"""
Abstract base class for LLM providers.

Defines the interface that all LLM provider implementations must follow.
This allows the classification system to work with any LLM provider
through a common interface.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
import logging

from CDE_Schema.LLM_Classification import (
    LLMResponse,
    PhraseContext,
    ConfidenceQuintile,
)

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Each provider (Claude, OpenAI, Google) implements this interface
    to provide consistent classification capabilities.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the provider identifier.

        Returns:
            Provider name string: "claude", "openai", or "google"
        """
        pass

    @property
    @abstractmethod
    def model_id(self) -> str:
        """
        Return the specific model identifier.

        Returns:
            Model identifier string (e.g., "claude-sonnet-4-20250514")
        """
        pass

    @abstractmethod
    async def classify_batch(
        self,
        phrases: List[PhraseContext],
        system_prompt: str,
        user_prompt_template: str,
        categories: List[str],
        reference_examples: Optional[Dict[str, List[str]]] = None,
    ) -> List[LLMResponse]:
        """
        Classify a batch of phrases.

        This is the core classification method that sends phrases to the LLM
        and parses the responses.

        Args:
            phrases: List of PhraseContext objects to classify
            system_prompt: System prompt establishing the classification task
            user_prompt_template: Template for user prompts (contains {phrase} placeholder)
            categories: List of valid category outputs for validation
            reference_examples: Optional dict mapping categories to known examples

        Returns:
            List of LLMResponse objects, one per input phrase
        """
        pass

    @abstractmethod
    async def classify_single(
        self,
        phrase: PhraseContext,
        system_prompt: str,
        user_prompt: str,
        categories: List[str],
    ) -> LLMResponse:
        """
        Classify a single phrase.

        Lower-level method for individual phrase classification.

        Args:
            phrase: Single PhraseContext to classify
            system_prompt: System prompt for the task
            user_prompt: Complete user prompt for this phrase
            categories: Valid category outputs

        Returns:
            LLMResponse with classification result
        """
        pass

    @abstractmethod
    def validate_api_key(self) -> bool:
        """
        Validate that the API key is working.

        Makes a minimal API call to verify the key is valid and the
        provider is accessible.

        Returns:
            True if API key is valid and provider is accessible
        """
        pass

    def format_phrase_prompt(
        self,
        template: str,
        phrase: PhraseContext,
        max_contexts: int = 3,
        max_context_chars: int = 500,
    ) -> str:
        """
        Format a user prompt from template and phrase context.

        Default implementation that can be overridden by providers
        if they need special formatting.

        Args:
            template: Prompt template with placeholders
            phrase: PhraseContext to format
            max_contexts: Maximum number of context examples to include
            max_context_chars: Maximum characters per context

        Returns:
            Formatted prompt string
        """
        # Format verbatim forms
        verbatim_list = ", ".join(f'"{v}"' for v in phrase.verbatim_forms[:5])
        if len(phrase.verbatim_forms) > 5:
            verbatim_list += f" ... (+{len(phrase.verbatim_forms) - 5} more)"

        # Format contexts
        context_lines = []
        for ctx in phrase.field_contexts[:max_contexts]:
            text = ctx.full_text
            if len(text) > max_context_chars:
                # Truncate around the phrase position
                start = max(0, ctx.phrase_start - max_context_chars // 2)
                end = min(len(text), ctx.phrase_end + max_context_chars // 2)
                text = "..." + text[start:end] + "..."
            context_lines.append(f"  - [{ctx.field_path}]: {text}")

        contexts_str = "\n".join(context_lines) if context_lines else "(no contexts available)"

        # Basic template substitution
        prompt = template.replace("{phrase_text}", phrase.lemma_text)
        prompt = prompt.replace("{verbatim_forms}", verbatim_list)
        prompt = prompt.replace("{contexts}", contexts_str)
        prompt = prompt.replace("{frequency}", str(phrase.frequency))
        prompt = prompt.replace("{n_tinyids}", str(phrase.n_tinyids))

        return prompt

    def parse_classification_response(
        self,
        response_text: str,
        categories: List[str],
    ) -> Tuple[str, float, str]:
        """
        Parse LLM response into structured classification.

        Default implementation that expects JSON format:
        {"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}

        Can be overridden by providers for custom response parsing.

        Args:
            response_text: Raw response text from LLM
            categories: Valid categories for validation

        Returns:
            Tuple of (category, confidence, reasoning)

        Raises:
            ValueError: If response cannot be parsed
        """
        import json
        import re

        # Try to extract JSON from response
        # Look for JSON block in markdown code fence
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find bare JSON object
            json_match = re.search(r"\{[^{}]*\}", response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError(f"No JSON found in response: {response_text[:200]}")

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

        # Extract fields
        category = data.get("category", "").lower().strip()
        confidence = float(data.get("confidence", 0.5))
        reasoning = data.get("reasoning", "")

        # Validate category
        category_lower = {c.lower(): c for c in categories}
        if category not in category_lower:
            # Try fuzzy matching
            for valid in category_lower:
                if valid in category or category in valid:
                    category = category_lower[valid]
                    break
            else:
                logger.warning(f"Unknown category '{category}', defaulting to first")
                category = categories[0] if categories else "unknown"
        else:
            category = category_lower[category]

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        return category, confidence, reasoning

    def create_response(
        self,
        phrase: PhraseContext,
        category: str,
        confidence: float,
        reasoning: str,
        raw_response: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
    ) -> LLMResponse:
        """
        Create an LLMResponse object.

        Helper method to construct response objects consistently.

        Args:
            phrase: The classified phrase
            category: Classification result
            confidence: Confidence score (0.0-1.0)
            reasoning: Explanation from LLM
            raw_response: Full response text (for debugging)
            latency_ms: Response latency in milliseconds
            tokens_used: Tokens consumed

        Returns:
            LLMResponse object
        """
        return LLMResponse(
            provider=self.provider_name,
            model_id=self.model_id,
            classification=category,
            confidence=confidence,
            quintile=ConfidenceQuintile.from_confidence(confidence),
            reasoning=reasoning,
            raw_response=raw_response,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
        )


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class RateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(ProviderError):
    """Raised when API key is invalid or expired."""
    pass


class ModelNotFoundError(ProviderError):
    """Raised when requested model is not available."""
    pass
