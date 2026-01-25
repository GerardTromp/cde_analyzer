"""
OpenAI ChatGPT LLM provider implementation.

Provides async classification using OpenAI models via the OpenAI API.
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
DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    """
    OpenAI ChatGPT provider for phrase classification.

    Uses the openai Python SDK with async support.
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
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model identifier (default: gpt-4o)
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

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_id(self) -> str:
        return self._model

    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError(
                    "openai package not installed. Run: pip install openai"
                )
        return self._client

    async def classify_single(
        self,
        phrase: PhraseContext,
        system_prompt: str,
        user_prompt: str,
        categories: List[str],
    ) -> LLMResponse:
        """
        Classify a single phrase using OpenAI.

        Args:
            phrase: PhraseContext to classify
            system_prompt: System prompt for the task
            user_prompt: Complete user prompt
            categories: Valid category outputs

        Returns:
            LLMResponse with classification
        """
        client = self._get_client()
        start_time = time.perf_counter()

        try:
            response = await client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Extract response text
            response_text = response.choices[0].message.content or ""

            # Calculate tokens used
            tokens_used = (
                response.usage.prompt_tokens + response.usage.completion_tokens
                if response.usage else None
            )

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
        Classify a batch of phrases using OpenAI.

        Processes phrases concurrently with rate limiting.

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

        # Ensure JSON output instruction is in system prompt
        if "json" not in system_prompt.lower():
            system_prompt += "\n\nRespond with valid JSON only."

        # Create tasks for concurrent execution
        tasks = []
        for phrase in phrases:
            user_prompt = self.format_phrase_prompt(
                template=user_prompt_template,
                phrase=phrase,
            )
            task = self.classify_single(phrase, system_prompt, user_prompt, categories)
            tasks.append(task)

        # Execute concurrently
        responses = await asyncio.gather(*tasks, return_exceptions=True)

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
            import openai
            # Use sync client for validation
            client = openai.OpenAI(api_key=self._api_key)
            # Make a minimal request
            response = client.chat.completions.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except openai.AuthenticationError:
            logger.error("OpenAI API key is invalid")
            return False
        except openai.NotFoundError:
            logger.error(f"OpenAI model not found: {self._model}")
            return False
        except Exception as e:
            logger.error(f"OpenAI API validation failed: {e}")
            return False

    def _handle_error(
        self,
        error: Exception,
        phrase: PhraseContext,
        categories: List[str],
    ) -> LLMResponse:
        """Handle API errors and return appropriate response."""
        try:
            import openai

            if isinstance(error, openai.RateLimitError):
                logger.warning(f"OpenAI rate limit hit: {error}")
                raise RateLimitError(str(error))
            elif isinstance(error, openai.AuthenticationError):
                raise AuthenticationError(str(error))
            elif isinstance(error, openai.NotFoundError):
                raise ModelNotFoundError(str(error))
            else:
                logger.error(f"OpenAI API error: {error}")
                return self._create_error_response(phrase, str(error), categories)
        except ImportError:
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
