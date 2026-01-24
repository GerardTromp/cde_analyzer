"""
Google Gemini LLM provider implementation.

Provides async classification using Gemini models via the Google AI API.
"""

import asyncio
import time
import logging
from typing import List, Optional, Dict, Any

from .provider_base import (
    LLMProvider,
    LLMResponse,
    PhraseContext,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
)

logger = logging.getLogger(__name__)

# Default model
DEFAULT_MODEL = "gemini-1.5-pro"


class GoogleProvider(LLMProvider):
    """
    Google Gemini provider for phrase classification.

    Uses the google-generativeai Python SDK.
    """

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs,
    ):
        """
        Initialize Google Gemini provider.

        Args:
            api_key: Google AI API key
            model: Model identifier (default: gemini-1.5-pro)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 for deterministic)
            **kwargs: Additional parameters passed to API calls
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._extra_params = kwargs
        self._client = None
        self._configured = False

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_id(self) -> str:
        return self._model

    def _configure(self):
        """Configure the Google AI SDK with API key."""
        if not self._configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._configured = True
            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                )

    def _get_model(self):
        """Get configured Gemini model."""
        self._configure()
        import google.generativeai as genai

        generation_config = genai.GenerationConfig(
            max_output_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        return genai.GenerativeModel(
            model_name=self._model,
            generation_config=generation_config,
        )

    async def classify_single(
        self,
        phrase: PhraseContext,
        system_prompt: str,
        user_prompt: str,
        categories: List[str],
    ) -> LLMResponse:
        """
        Classify a single phrase using Gemini.

        Args:
            phrase: PhraseContext to classify
            system_prompt: System prompt for the task
            user_prompt: Complete user prompt
            categories: Valid category outputs

        Returns:
            LLMResponse with classification
        """
        model = self._get_model()
        start_time = time.perf_counter()

        # Combine system and user prompts (Gemini uses different format)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        try:
            # Run in executor since google-generativeai doesn't have native async
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: model.generate_content(full_prompt)
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract response text
            response_text = response.text if response.text else ""

            # Estimate tokens (Gemini doesn't always provide exact counts)
            tokens_used = None
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                if hasattr(usage, 'prompt_token_count') and hasattr(usage, 'candidates_token_count'):
                    tokens_used = usage.prompt_token_count + usage.candidates_token_count

            # Parse the response
            category, confidence, reasoning = self.parse_classification_response(
                response_text, categories
            )

            return self.create_response(
                phrase=phrase,
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                raw_response=response_text,
                latency_ms=latency_ms,
                tokens_used=tokens_used,
            )

        except Exception as e:
            return self._handle_error(e, phrase, categories)

    async def classify_batch(
        self,
        phrases: List[PhraseContext],
        system_prompt: str,
        user_prompt_template: str,
        categories: List[str],
        reference_examples: Optional[Dict[str, List[str]]] = None,
    ) -> List[LLMResponse]:
        """
        Classify a batch of phrases using Gemini.

        Processes phrases concurrently.

        Args:
            phrases: List of PhraseContext objects
            system_prompt: System prompt for classification
            user_prompt_template: Template with placeholders
            categories: Valid category outputs
            reference_examples: Optional known examples per category

        Returns:
            List of LLMResponse objects
        """
        # Build reference section if provided
        if reference_examples:
            ref_lines = ["\n\nReference examples:"]
            for cat, examples in reference_examples.items():
                ref_lines.append(f"\n{cat}:")
                for ex in examples[:5]:
                    ref_lines.append(f"  - {ex}")
            system_prompt = system_prompt + "\n".join(ref_lines)

        # Ensure JSON output instruction
        if "json" not in system_prompt.lower():
            system_prompt += (
                "\n\nRespond with valid JSON only in this format: "
                '{"category": "...", "confidence": 0.0-1.0, "reasoning": "..."}'
            )

        # Create tasks for concurrent execution
        tasks = []
        for phrase in phrases:
            user_prompt = self.format_phrase_prompt(
                template=user_prompt_template,
                phrase=phrase,
            )
            task = self.classify_single(phrase, system_prompt, user_prompt, categories)
            tasks.append(task)

        # Execute concurrently (with semaphore to limit parallelism)
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests

        async def limited_task(task):
            async with semaphore:
                return await task

        responses = await asyncio.gather(
            *[limited_task(t) for t in tasks],
            return_exceptions=True
        )

        # Convert exceptions to error responses
        results = []
        for i, resp in enumerate(responses):
            if isinstance(resp, Exception):
                logger.error(f"Classification failed for phrase {phrases[i].phrase_id}: {resp}")
                results.append(self._create_error_response(phrases[i], str(resp), categories))
            else:
                results.append(resp)

        return results

    def validate_api_key(self) -> bool:
        """
        Validate the API key by making a minimal request.

        Returns:
            True if API key is valid
        """
        try:
            self._configure()
            import google.generativeai as genai

            model = genai.GenerativeModel(model_name=self._model)
            response = model.generate_content("Hi")
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str:
                logger.error("Google API key is invalid")
            elif "not found" in error_str or "model" in error_str:
                logger.error(f"Google model not found: {self._model}")
            else:
                logger.error(f"Google API validation failed: {e}")
            return False

    def _handle_error(
        self,
        error: Exception,
        phrase: PhraseContext,
        categories: List[str],
    ) -> LLMResponse:
        """Handle API errors and return appropriate response."""
        error_str = str(error).lower()

        if "rate" in error_str or "quota" in error_str:
            logger.warning(f"Google rate limit hit: {error}")
            raise RateLimitError(str(error))
        elif "api key" in error_str or "authentication" in error_str:
            raise AuthenticationError(str(error))
        elif "not found" in error_str:
            raise ModelNotFoundError(str(error))
        else:
            logger.error(f"Google API error: {error}")
            return self._create_error_response(phrase, str(error), categories)

    def _create_error_response(
        self,
        phrase: PhraseContext,
        error_msg: str,
        categories: List[str],
    ) -> LLMResponse:
        """Create an error response for failed classification."""
        return self.create_response(
            phrase=phrase,
            category=categories[0] if categories else "error",
            confidence=0.0,
            reasoning=f"Classification failed: {error_msg}",
            raw_response=None,
        )
