"""
Query module registry for LLM classification.

This module provides a registry of available query modules and
factory functions for creating module instances.

Usage:
    from utils.query_modules import get_module, list_modules

    # List available modules
    available = list_modules()

    # Get a module instance
    module = get_module("instrument", reference_file=Path("instruments.tsv"))
"""

from typing import Dict, List, Optional, Type, TYPE_CHECKING
from pathlib import Path
import logging

from .module_base import QueryModule, QueryModuleConfig

logger = logging.getLogger(__name__)

# Module registry - maps module names to their class paths for lazy loading
_MODULE_REGISTRY: Dict[str, str] = {
    "instrument": "utils.query_modules.instrument_detector.InstrumentDetectorModule",
    "temporal": "utils.query_modules.temporal_detector.TemporalDetectorModule",
    "instrument_family": "utils.query_modules.instrument_family_detector.InstrumentFamilyDetectorModule",
}

# Module descriptions for help text
MODULE_DESCRIPTIONS: Dict[str, str] = {
    "instrument": "Detect instrument/device names in phrases",
    "temporal": "Detect temporal patterns (recency, age ranges, durations)",
    "instrument_family": "Detect instrument family membership for grouping (e.g., Neuro-QOL, PROMIS)",
}

# Cached module classes
_module_classes: Dict[str, Type[QueryModule]] = {}


def _import_module_class(module_name: str) -> Type[QueryModule]:
    """
    Dynamically import a module class.

    Args:
        module_name: Module identifier

    Returns:
        Module class

    Raises:
        ValueError: If module not found
        ImportError: If module cannot be imported
    """
    if module_name in _module_classes:
        return _module_classes[module_name]

    if module_name not in _MODULE_REGISTRY:
        raise ValueError(
            f"Unknown query module: {module_name}. "
            f"Available modules: {list(_MODULE_REGISTRY.keys())}"
        )

    module_path = _MODULE_REGISTRY[module_name]
    package_name, class_name = module_path.rsplit(".", 1)

    try:
        import importlib
        module = importlib.import_module(package_name)
        cls = getattr(module, class_name)
        _module_classes[module_name] = cls
        return cls
    except ImportError as e:
        raise ImportError(f"Cannot import module {module_name}: {e}") from e
    except AttributeError as e:
        raise ImportError(f"Module class {class_name} not found in {package_name}: {e}") from e


def get_module(
    module_name: str,
    reference_file: Optional[Path] = None,
    config: Optional[QueryModuleConfig] = None,
) -> QueryModule:
    """
    Get an instance of a query module.

    Args:
        module_name: Module identifier (e.g., "instrument", "temporal")
        reference_file: Optional path to reference data file
        config: Optional module configuration

    Returns:
        Configured QueryModule instance

    Raises:
        ValueError: If module not found
    """
    cls = _import_module_class(module_name)

    # Create instance
    instance = cls(config=config, reference_file=reference_file)

    logger.info(f"Created query module: {module_name}")
    return instance


def list_modules() -> List[str]:
    """
    List available query module names.

    Returns:
        List of module identifiers
    """
    return list(_MODULE_REGISTRY.keys())


def get_module_description(module_name: str) -> str:
    """
    Get description for a module.

    Args:
        module_name: Module identifier

    Returns:
        Description string
    """
    return MODULE_DESCRIPTIONS.get(module_name, f"Query module: {module_name}")


def get_module_categories(module_name: str) -> List[str]:
    """
    Get output categories for a module without instantiating it.

    Args:
        module_name: Module identifier

    Returns:
        List of category names
    """
    cls = _import_module_class(module_name)
    # Create temporary instance to get categories
    instance = cls()
    return instance.output_categories


def register_module(module_name: str, module_class: Type[QueryModule]):
    """
    Register a custom query module.

    Allows extending the system with custom modules at runtime.

    Args:
        module_name: Unique module identifier
        module_class: QueryModule subclass
    """
    if not issubclass(module_class, QueryModule):
        raise TypeError(f"Module class must be a QueryModule subclass")

    _module_classes[module_name] = module_class
    _MODULE_REGISTRY[module_name] = f"{module_class.__module__}.{module_class.__name__}"
    logger.info(f"Registered custom query module: {module_name}")


# Public exports
__all__ = [
    "QueryModule",
    "QueryModuleConfig",
    "get_module",
    "list_modules",
    "get_module_description",
    "get_module_categories",
    "register_module",
    "MODULE_DESCRIPTIONS",
]
