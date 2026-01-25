"""
LLM integration module for phrase classification.

This module provides a unified interface for querying multiple LLM providers
(Claude, OpenAI, Google Gemini) with support for:
- Async parallel queries
- Rate limiting and retry logic
- Multi-LLM result aggregation
- Configurable API key resolution

Usage:
    from utils.llm import create_providers, resolve_config

    # Resolve configuration (config file -> env vars -> CLI)
    config = resolve_config(
        requested_providers=["claude", "openai"],
        cli_api_keys=args.api_keys,
    )

    # Create provider instances
    providers = await create_providers(config)

    # Use providers for classification
    for provider in providers:
        responses = await provider.classify_batch(phrases, system_prompt, ...)
"""

from typing import List, Optional, TYPE_CHECKING
import logging

from .config import (
    LLMConfig,
    ProviderConfig,
    resolve_config,
    load_config_file,
    create_example_config,
    DEFAULT_CONFIG_PATH,
    ENV_VAR_NAMES,
    DEFAULT_MODELS,
)

from .provider_base import (
    LLMProvider,
    ProviderError,
    RateLimitError,
    AuthenticationError,
    ModelNotFoundError,
)

logger = logging.getLogger(__name__)

# Provider class registry (lazy loaded)
_PROVIDER_CLASSES = {
    "claude": "utils.llm.provider_claude.ClaudeProvider",
    "openai": "utils.llm.provider_openai.OpenAIProvider",
    "google": "utils.llm.provider_google.GoogleProvider",
}


def _import_provider_class(provider_name: str):
    """
    Dynamically import a provider class.

    Enables lazy loading of provider modules to avoid importing
    dependencies (anthropic, openai, google-generativeai) at startup.

    Args:
        provider_name: Provider identifier ("claude", "openai", "google")

    Returns:
        Provider class

    Raises:
        ImportError: If provider module or dependencies are not installed
    """
    if provider_name not in _PROVIDER_CLASSES:
        raise ValueError(f"Unknown provider: {provider_name}")

    module_path = _PROVIDER_CLASSES[provider_name]
    module_name, class_name = module_path.rsplit(".", 1)

    try:
        import importlib
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except ImportError as e:
        # Provide helpful error message for missing dependencies
        dep_hints = {
            "claude": "pip install anthropic",
            "openai": "pip install openai",
            "google": "pip install google-generativeai",
        }
        hint = dep_hints.get(provider_name, "")
        raise ImportError(
            f"Cannot import {provider_name} provider: {e}. "
            f"Install dependencies: {hint}"
        ) from e


def create_provider(config: ProviderConfig) -> LLMProvider:
    """
    Create a single LLM provider instance.

    Args:
        config: ProviderConfig with API key and settings

    Returns:
        Configured LLMProvider instance

    Raises:
        ImportError: If provider dependencies are not installed
        ValueError: If provider is unknown
    """
    provider_class = _import_provider_class(config.provider)
    return provider_class(
        api_key=config.api_key,
        model=config.model,
        **config.extra_params,
    )


async def create_providers(config: LLMConfig) -> List[LLMProvider]:
    """
    Create provider instances for all configured providers.

    Args:
        config: LLMConfig with resolved provider configurations

    Returns:
        List of LLMProvider instances

    Raises:
        ImportError: If any provider dependencies are not installed
    """
    providers = []

    for provider_config in config.get_providers():
        try:
            provider = create_provider(provider_config)
            logger.info(
                f"Created {provider.provider_name} provider "
                f"(model: {provider.model_id}, source: {provider_config.source})"
            )
            providers.append(provider)
        except ImportError as e:
            logger.error(f"Failed to create provider: {e}")
            raise

    return providers


async def validate_providers(providers: List[LLMProvider]) -> List[LLMProvider]:
    """
    Validate API keys for all providers.

    Filters out providers with invalid keys and logs warnings.

    Args:
        providers: List of provider instances to validate

    Returns:
        List of providers with valid API keys
    """
    valid_providers = []

    for provider in providers:
        try:
            if provider.validate_api_key():
                valid_providers.append(provider)
                logger.info(f"Validated API key for {provider.provider_name}")
            else:
                logger.warning(f"Invalid API key for {provider.provider_name}")
        except Exception as e:
            logger.warning(f"Failed to validate {provider.provider_name}: {e}")

    return valid_providers


# Public exports
__all__ = [
    # Config
    "LLMConfig",
    "ProviderConfig",
    "resolve_config",
    "load_config_file",
    "create_example_config",
    "DEFAULT_CONFIG_PATH",
    "ENV_VAR_NAMES",
    "DEFAULT_MODELS",
    # Providers
    "LLMProvider",
    "create_provider",
    "create_providers",
    "validate_providers",
    # Exceptions
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
]
