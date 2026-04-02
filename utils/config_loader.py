# File: utils/config_loader.py
"""
Configuration file loader utilities.

Provides functions to load YAML configuration files from the config/ directory.
Used for externalized pattern lists and other configurable data.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

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


def _parse_tinyid_field(raw: str) -> Optional[Set[str]]:
    """Parse a tinyIds string (comma, space, or pipe delimited) into a set.

    Returns None if the string is empty or absent (meaning universal/all CDEs).
    """
    if not raw:
        return None
    ids = set()
    for part in raw.replace(",", " ").replace("|", " ").split():
        stripped = part.strip()
        if stripped:
            ids.add(stripped)
    return ids if ids else None


def _extract_verbatim_patterns_from_config(
    config: Dict,
    source: str = "unknown"
) -> List[Tuple[str, str, Optional[Set[str]]]]:
    """
    Extract verbatim strip patterns from a parsed YAML config dict.

    Args:
        config: Parsed YAML config with category sections containing pattern lists
        source: Source name for logging (e.g., "global", "local")

    Returns:
        List of (pattern_text, replace_with, tinyIds) tuples.
        replace_with defaults to empty string if not specified.
        tinyIds is None when absent (pattern applies to all CDEs).
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
            tinyids = _parse_tinyid_field(item.get('tinyIds', ''))

            if pattern:
                patterns.append((pattern, replace_with, tinyids))
            else:
                logger.warning(f"Skipping entry without pattern in {category} ({source}): {item}")

    return patterns


def _auto_propagate_bare_patterns(
    patterns: List[Tuple[str, str, Optional[Set[str]]]]
) -> List[Tuple[str, str, Optional[Set[str]]]]:
    """Auto-propagate bracketed [TAG] patterns to bare TAG with same tinyId scope.

    Rules:
    - Bracketed [TAG] with tinyIds -> creates bare TAG with same tinyIds (if bare
      TAG doesn't already exist, or unions tinyIds if it does)
    - Bracketed [TAG] without tinyIds (universal) -> no propagation needed
      (bracketed form disambiguates already)
    - Existing bare TAG with tinyIds=None (universal) -> not downgraded

    Returns:
        Extended pattern list with auto-propagated bare forms appended.
    """
    import re
    bracket_re = re.compile(r'^\[(.+)\]$')

    # Index existing bare patterns
    bare_index: Dict[str, int] = {}  # bare_text -> index in patterns list
    for i, (pat, _, _) in enumerate(patterns):
        if not bracket_re.match(pat):
            bare_index[pat] = i

    # Collect bracketed patterns with tinyIds
    propagated = []
    for pat, replace_with, tinyids in patterns:
        if tinyids is None:
            continue  # Universal bracketed -> no propagation needed
        m = bracket_re.match(pat)
        if not m:
            continue
        bare = m.group(1)
        if bare in bare_index:
            # Bare exists -> check if we should union tinyIds
            idx = bare_index[bare]
            existing_tinyids = patterns[idx][2]
            if existing_tinyids is None:
                pass  # Already universal, don't downgrade
            else:
                # Union the tinyId sets
                merged = existing_tinyids | tinyids
                patterns[idx] = (patterns[idx][0], patterns[idx][1], merged)
        else:
            # Create new bare entry with same scope
            propagated.append((bare, replace_with, tinyids))
            bare_index[bare] = len(patterns) + len(propagated) - 1

    if propagated:
        logger.info(f"Auto-propagated {len(propagated)} bare patterns from bracketed forms")

    return patterns + propagated


def load_verbatim_strip_patterns() -> List[Tuple[str, str, Optional[Set[str]]]]:
    """
    Load verbatim strip patterns from config files.

    These patterns are stripped directly during phrase stripping, unlike
    supplementary_patterns which are used for instrument extraction.

    Loading priority (later extends earlier):
      1. Global config: config/verbatim_strip_patterns.yaml (in project root)
      2. Local override: ./verbatim_strip_patterns.yaml (in working directory)

    Auto-propagation: Bracketed [TAG] patterns with tinyIds automatically
    generate bare TAG patterns with the same tinyId scope.

    Local files extend (add to) the global list rather than replacing it.
    This allows rapid iteration during curation without modifying installed code.

    Returns:
        List of (pattern_text, replace_with, tinyIds) tuples.
        replace_with is typically empty string for removal.
        tinyIds is None when pattern applies to all CDEs (universal).
    """
    patterns: List[Tuple[str, str, Optional[Set[str]]]] = []
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

    # 3. Auto-propagate bracketed [TAG] -> bare TAG with same tinyId scope
    patterns = _auto_propagate_bare_patterns(patterns)

    if configs_loaded:
        n_scoped = sum(1 for _, _, t in patterns if t is not None)
        logger.info(f"Loaded {len(patterns)} verbatim strip patterns "
                    f"({n_scoped} scoped) from: {', '.join(configs_loaded)}")
    elif patterns:
        logger.info(f"Loaded {len(patterns)} verbatim strip patterns")

    return patterns


def load_abbreviation_dictionary(
    dict_path: Optional[str] = None,
) -> Optional[Any]:
    """
    Load an abbreviation dictionary from TSV.

    Loading priority:
      1. Explicit path (if provided)
      2. Local override: ./abbreviation_dictionary.tsv (in working directory)
      3. Global config: config/abbreviation_dictionary.tsv (in project root)

    Returns:
        AbbreviationDictionary instance, or None if no dictionary found.
    """
    from logic.abbreviation_dictionary import AbbreviationDictionary

    # Try explicit path
    if dict_path:
        p = Path(dict_path)
        if p.exists():
            d = AbbreviationDictionary(str(p))
            d.load()
            logger.info(f"Loaded abbreviation dictionary: {p} ({len(d.entries)} entries)")
            return d

    # Try local override
    local_path = Path.cwd() / "abbreviation_dictionary.tsv"
    if local_path.exists():
        d = AbbreviationDictionary(str(local_path))
        d.load()
        logger.info(f"Loaded local abbreviation dictionary: {local_path} ({len(d.entries)} entries)")
        return d

    # Try global config
    global_path = get_config_dir() / "abbreviation_dictionary.tsv"
    if global_path.exists():
        d = AbbreviationDictionary(str(global_path))
        d.load()
        logger.info(f"Loaded global abbreviation dictionary: {global_path} ({len(d.entries)} entries)")
        return d

    return None


def load_permanent_skip_abbreviations() -> Set[str]:
    """
    Load permanent skip abbreviations from YAML config.

    Returns a set of abbreviation strings that should never be re-evaluated
    regardless of corpus frequency changes.
    """
    import yaml

    skips: Set[str] = set()

    # Global config
    global_path = get_config_dir() / "permanent_skip_abbreviations.yaml"
    if global_path.exists():
        try:
            with open(global_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for entry in data.get("permanent_skips", []):
                abbrev = entry.get("abbreviation", "").strip()
                if abbrev:
                    skips.add(abbrev)
            logger.info(f"Loaded {len(skips)} permanent skip abbreviations from {global_path}")
        except Exception as e:
            logger.warning(f"Error loading permanent skips: {e}")

    # Local override (additive)
    local_path = Path.cwd() / "permanent_skip_abbreviations.yaml"
    if local_path.exists() and local_path != global_path:
        try:
            with open(local_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            before = len(skips)
            for entry in data.get("permanent_skips", []):
                abbrev = entry.get("abbreviation", "").strip()
                if abbrev:
                    skips.add(abbrev)
            logger.info(f"Added {len(skips) - before} permanent skips from local {local_path}")
        except Exception as e:
            logger.warning(f"Error loading local permanent skips: {e}")

    return skips


def clear_config_cache():
    """Clear the configuration cache to force reload on next access."""
    global _config_cache
    _config_cache = {}
