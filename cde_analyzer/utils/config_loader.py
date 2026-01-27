# File: utils/config_loader.py
"""
Configuration file loader utilities.

Provides functions to load YAML configuration files from the config/ directory.
Used for externalized pattern lists and other configurable data.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Cache for loaded configs to avoid repeated file reads
_config_cache: Dict[str, Any] = {}


def get_config_dir() -> Path:
    """
    Get the path to the config directory.

    Returns:
        Path to config/ directory relative to project root.
    """
    # Navigate from utils/ to project root, then to config/
    utils_dir = Path(__file__).parent
    project_root = utils_dir.parent
    return project_root / "config"


def load_yaml_config(filename: str, use_cache: bool = True) -> Optional[Dict]:
    """
    Load a YAML configuration file from the config directory.

    Args:
        filename: Name of the YAML file (with or without .yaml extension)
        use_cache: If True, return cached version if available

    Returns:
        Parsed YAML as dict, or None if file doesn't exist or parse fails
    """
    if not filename.endswith('.yaml') and not filename.endswith('.yml'):
        filename = filename + '.yaml'

    if use_cache and filename in _config_cache:
        return _config_cache[filename]

    config_path = get_config_dir() / filename
    logger.debug(f"Looking for config file: {config_path}")

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        logger.warning(f"Config directory exists: {get_config_dir().exists()}")
        return None

    try:
        import yaml
        logger.debug(f"Loading YAML from: {config_path}")
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if use_cache:
                _config_cache[filename] = config
            return config
    except ImportError:
        logger.error("PyYAML not installed. Run: pip install pyyaml")
        return None
    except Exception as e:
        logger.error(f"Failed to load config {filename}: {e}")
        return None


def load_supplementary_patterns() -> List[Tuple[str, str, Optional[str]]]:
    """
    Load supplementary instrument patterns from config file.

    Returns:
        List of (pattern_text, display_name, acronym) tuples.
        Acronym may be None if not specified.
    """
    config = load_yaml_config('supplementary_patterns')
    if not config:
        logger.warning("No supplementary patterns config found, using empty list")
        return []

    patterns = []

    # Iterate through all category sections
    for category, items in config.items():
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            pattern = item.get('pattern')
            name = item.get('name')
            acronym = item.get('acronym')  # Optional, defaults to None

            if pattern and name:
                patterns.append((pattern, name, acronym))
            else:
                logger.warning(f"Skipping incomplete pattern entry in {category}: {item}")

    logger.info(f"Loaded {len(patterns)} supplementary patterns from config")
    return patterns


def clear_config_cache():
    """Clear the configuration cache to force reload on next access."""
    global _config_cache
    _config_cache = {}
