"""
LLM configuration and API key resolution.

API key priority order (first found wins):
1. Config file: ~/.cde_analyzer/llm_config.json
2. Environment variables: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
3. CLI arguments: --api-keys (documented as least preferred)

Note: CLI arguments are least preferred because they may appear in
shell history. Environment variables or config files are more secure.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default config file location
DEFAULT_CONFIG_PATH = Path.home() / ".cde_analyzer" / "llm_config.json"

# Environment variable names for each provider
ENV_VAR_NAMES = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}

# Default models for each provider
DEFAULT_MODELS = {
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "google": "gemini-1.5-pro",
}


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    provider: str                         # "claude", "openai", "google"
    api_key: str                          # The API key
    model: str                            # Model identifier
    source: str                           # "config_file", "env_var", or "cli"
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """
    Complete LLM configuration for a classification run.

    Contains resolved configurations for all requested providers.
    """
    providers: Dict[str, ProviderConfig]  # Keyed by provider name
    config_file_path: Optional[Path] = None  # Path to config file (if used)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get configuration for a specific provider."""
        return self.providers.get(name)

    def get_providers(self) -> List[ProviderConfig]:
        """Get all configured providers."""
        return list(self.providers.values())

    def has_provider(self, name: str) -> bool:
        """Check if a provider is configured."""
        return name in self.providers


def load_config_file(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file (uses default if None)

    Returns:
        Dict with provider configurations, empty if file doesn't exist

    Config file format:
    {
        "claude": {"api_key": "sk-ant-...", "model": "claude-sonnet-4-20250514"},
        "openai": {"api_key": "sk-...", "model": "gpt-4o"},
        "google": {"api_key": "...", "model": "gemini-1.5-pro"}
    }
    """
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        logger.debug(f"Config file not found: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded LLM config from: {path}")
        return config
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in config file {path}: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Error reading config file {path}: {e}")
        return {}


def parse_cli_api_keys(api_keys: Optional[List[str]]) -> Dict[str, str]:
    """
    Parse API keys from CLI arguments.

    Args:
        api_keys: List of "provider:key" strings

    Returns:
        Dict mapping provider name to API key

    Example:
        ["claude:sk-ant-xxx", "openai:sk-yyy"] ->
        {"claude": "sk-ant-xxx", "openai": "sk-yyy"}
    """
    if not api_keys:
        return {}

    result = {}
    for entry in api_keys:
        if ":" not in entry:
            logger.warning(f"Invalid API key format (expected 'provider:key'): {entry[:20]}...")
            continue

        provider, key = entry.split(":", 1)
        provider = provider.lower().strip()

        if provider not in ENV_VAR_NAMES:
            logger.warning(f"Unknown provider '{provider}'. Known: {list(ENV_VAR_NAMES.keys())}")
            continue

        result[provider] = key.strip()
        logger.debug(f"Parsed CLI API key for provider: {provider}")

    return result


def resolve_provider_config(
    provider: str,
    config_file_data: Dict[str, Any],
    cli_api_keys: Dict[str, str],
    default_model: Optional[str] = None,
) -> Optional[ProviderConfig]:
    """
    Resolve configuration for a single provider.

    Priority order:
    1. Config file
    2. Environment variable
    3. CLI argument

    Args:
        provider: Provider name ("claude", "openai", "google")
        config_file_data: Data loaded from config file
        cli_api_keys: API keys parsed from CLI arguments
        default_model: Override default model (optional)

    Returns:
        ProviderConfig if API key found, None otherwise
    """
    api_key = None
    source = None
    model = default_model or DEFAULT_MODELS.get(provider, "")
    extra_params = {}

    # Priority 1: Config file
    if provider in config_file_data:
        provider_data = config_file_data[provider]
        if isinstance(provider_data, dict):
            api_key = provider_data.get("api_key")
            if api_key:
                source = "config_file"
                model = provider_data.get("model", model)
                extra_params = {k: v for k, v in provider_data.items()
                               if k not in ("api_key", "model")}
                logger.debug(f"Using config file for {provider}")

    # Priority 2: Environment variable
    if not api_key:
        env_var = ENV_VAR_NAMES.get(provider)
        if env_var:
            api_key = os.environ.get(env_var)
            if api_key:
                source = "env_var"
                logger.debug(f"Using environment variable {env_var} for {provider}")

    # Priority 3: CLI argument (least preferred)
    if not api_key:
        api_key = cli_api_keys.get(provider)
        if api_key:
            source = "cli"
            logger.debug(f"Using CLI argument for {provider} (least secure)")

    if not api_key:
        return None

    return ProviderConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        source=source,
        extra_params=extra_params,
    )


def resolve_config(
    requested_providers: List[str],
    config_file_path: Optional[Path] = None,
    cli_api_keys: Optional[List[str]] = None,
) -> LLMConfig:
    """
    Resolve complete LLM configuration.

    Resolves API keys for all requested providers using the priority order:
    config file -> environment variables -> CLI arguments.

    Args:
        requested_providers: List of provider names to configure
        config_file_path: Optional custom config file path
        cli_api_keys: Optional CLI API key arguments

    Returns:
        LLMConfig with all resolved provider configurations

    Raises:
        ValueError: If no API keys found for any requested provider
    """
    # Load config file
    config_file_data = load_config_file(config_file_path)

    # Parse CLI API keys
    parsed_cli_keys = parse_cli_api_keys(cli_api_keys)

    # Resolve each provider
    providers = {}
    missing_providers = []

    for provider in requested_providers:
        provider = provider.lower().strip()

        if provider not in ENV_VAR_NAMES:
            logger.warning(f"Unknown provider '{provider}', skipping")
            continue

        config = resolve_provider_config(
            provider=provider,
            config_file_data=config_file_data,
            cli_api_keys=parsed_cli_keys,
        )

        if config:
            providers[provider] = config
        else:
            missing_providers.append(provider)

    # Report missing providers
    if missing_providers:
        hints = []
        for p in missing_providers:
            env_var = ENV_VAR_NAMES.get(p, "")
            hints.append(f"  - {p}: set {env_var} or add to config file")
        hint_text = "\n".join(hints)
        logger.warning(
            f"No API keys found for providers: {missing_providers}\n"
            f"To fix:\n{hint_text}\n"
            f"Config file location: {config_file_path or DEFAULT_CONFIG_PATH}"
        )

    if not providers:
        raise ValueError(
            f"No API keys found for any requested provider: {requested_providers}. "
            f"Set environment variables, create config file at "
            f"{config_file_path or DEFAULT_CONFIG_PATH}, or provide --api-keys."
        )

    return LLMConfig(
        providers=providers,
        config_file_path=config_file_path or DEFAULT_CONFIG_PATH,
    )


def create_example_config(output_path: Optional[Path] = None) -> Path:
    """
    Create an example configuration file.

    Useful for first-time setup. Creates a template with placeholder values.

    Args:
        output_path: Where to write the file (uses default if None)

    Returns:
        Path to created file
    """
    path = output_path or DEFAULT_CONFIG_PATH

    example_config = {
        "claude": {
            "api_key": "sk-ant-your-key-here",
            "model": DEFAULT_MODELS["claude"],
        },
        "openai": {
            "api_key": "sk-your-key-here",
            "model": DEFAULT_MODELS["openai"],
        },
        "google": {
            "api_key": "your-key-here",
            "model": DEFAULT_MODELS["google"],
        },
    }

    # Create parent directory if needed
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(example_config, f, indent=2)

    logger.info(f"Created example config at: {path}")
    return path
