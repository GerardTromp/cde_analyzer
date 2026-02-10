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


def _extract_patterns_from_config(
    config: Dict,
    source: str = "unknown"
) -> List[Tuple[str, str, Optional[str]]]:
    """
    Extract pattern tuples from a parsed YAML config dict.

    Args:
        config: Parsed YAML config with category sections containing pattern lists
        source: Source name for logging (e.g., "global", "local")

    Returns:
        List of (pattern_text, display_name, acronym) tuples.
    """
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
                logger.warning(f"Skipping incomplete pattern entry in {category} ({source}): {item}")

    return patterns


def load_supplementary_patterns() -> List[Tuple[str, str, Optional[str]]]:
    """
    Load supplementary instrument patterns from config files.

    Loading priority (later extends earlier):
      1. Global config: config/supplementary_patterns.yaml (in project root)
      2. Local override: ./supplementary_patterns.yaml (in working directory)

    Local files extend (add to) the global list rather than replacing it.
    This allows rapid iteration during curation without modifying installed code.

    Returns:
        List of (pattern_text, display_name, acronym) tuples.
        Acronym may be None if not specified.
    """
    patterns = []
    seen_patterns = set()  # Track pattern text to avoid exact duplicates
    configs_loaded = []

    # 1. Load global config from project config/ directory
    global_config = load_yaml_config('supplementary_patterns')
    if global_config:
        global_patterns = _extract_patterns_from_config(global_config, "global")
        for p in global_patterns:
            if p[0] not in seen_patterns:
                seen_patterns.add(p[0])
                patterns.append(p)
        configs_loaded.append(str(get_config_dir() / 'supplementary_patterns.yaml'))

    # 2. Load local override from working directory (extends global)
    local_path = Path.cwd() / 'supplementary_patterns.yaml'
    if local_path.exists():
        try:
            import yaml
            with open(local_path, encoding='utf-8') as f:
                local_config = yaml.safe_load(f)
            if local_config:
                local_patterns = _extract_patterns_from_config(local_config, "local")
                added_count = 0
                for p in local_patterns:
                    if p[0] not in seen_patterns:
                        seen_patterns.add(p[0])
                        patterns.append(p)
                        added_count += 1
                if added_count > 0:
                    configs_loaded.append(str(local_path))
                    logger.info(f"Added {added_count} patterns from local override: {local_path}")
        except ImportError:
            logger.warning("PyYAML not installed, cannot load local supplementary_patterns.yaml")
        except Exception as e:
            logger.warning(f"Error loading local {local_path}: {e}")

    if configs_loaded:
        logger.info(f"Loaded {len(patterns)} supplementary patterns from: {', '.join(configs_loaded)}")
    else:
        logger.warning("No supplementary patterns config found, using empty list")

    return patterns


def _extract_verbatim_patterns_from_config(
    config: Dict,
    source: str = "unknown"
) -> List[Tuple[str, str]]:
    """
    Extract verbatim strip patterns from a parsed YAML config dict.

    Args:
        config: Parsed YAML config with category sections containing pattern lists
        source: Source name for logging (e.g., "global", "local")

    Returns:
        List of (pattern_text, replace_with) tuples.
        replace_with defaults to empty string if not specified.
    """
    patterns = []

    # Iterate through all category sections
    for category, items in config.items():
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue

            pattern = item.get('pattern')
            replace_with = item.get('replace_with', '')  # Default to empty string

            if pattern:
                patterns.append((pattern, replace_with))
            else:
                logger.warning(f"Skipping entry without pattern in {category} ({source}): {item}")

    return patterns


def load_verbatim_strip_patterns() -> List[Tuple[str, str]]:
    """
    Load verbatim strip patterns from config files.

    These patterns are stripped directly during phrase stripping, unlike
    supplementary_patterns which are used for instrument extraction.

    Loading priority (later extends earlier):
      1. Global config: config/verbatim_strip_patterns.yaml (in project root)
      2. Local override: ./verbatim_strip_patterns.yaml (in working directory)

    Local files extend (add to) the global list rather than replacing it.
    This allows rapid iteration during curation without modifying installed code.

    Returns:
        List of (pattern_text, replace_with) tuples.
        replace_with is typically empty string for removal.
    """
    patterns = []
    seen_patterns = set()  # Track pattern text to avoid exact duplicates
    configs_loaded = []

    # 1. Load global config from project config/ directory
    global_config = load_yaml_config('verbatim_strip_patterns')
    if global_config:
        global_patterns = _extract_verbatim_patterns_from_config(global_config, "global")
        for p in global_patterns:
            if p[0] not in seen_patterns:
                seen_patterns.add(p[0])
                patterns.append(p)
        configs_loaded.append(str(get_config_dir() / 'verbatim_strip_patterns.yaml'))

    # 2. Load local override from working directory (extends global)
    local_path = Path.cwd() / 'verbatim_strip_patterns.yaml'
    if local_path.exists():
        try:
            import yaml
            with open(local_path, encoding='utf-8') as f:
                local_config = yaml.safe_load(f)
            if local_config:
                local_patterns = _extract_verbatim_patterns_from_config(local_config, "local")
                added_count = 0
                for p in local_patterns:
                    if p[0] not in seen_patterns:
                        seen_patterns.add(p[0])
                        patterns.append(p)
                        added_count += 1
                if added_count > 0:
                    configs_loaded.append(str(local_path))
                    logger.info(f"Added {added_count} verbatim patterns from local override: {local_path}")
        except ImportError:
            logger.warning("PyYAML not installed, cannot load local verbatim_strip_patterns.yaml")
        except Exception as e:
            logger.warning(f"Error loading local {local_path}: {e}")

    if configs_loaded:
        logger.info(f"Loaded {len(patterns)} verbatim strip patterns from: {', '.join(configs_loaded)}")
    elif patterns:
        # Patterns loaded but no configs tracked (shouldn't happen)
        logger.info(f"Loaded {len(patterns)} verbatim strip patterns")

    return patterns


def clear_config_cache():
    """Clear the configuration cache to force reload on next access."""
    global _config_cache
    _config_cache = {}
