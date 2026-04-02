"""YAML-driven query module for LLM tasks.

Loads system_prompt and user_prompt_template from config/llm_prompts.yaml,
enabling new LLM task types (e.g., boilerplate_substitution) without writing
a new QueryModule subclass.

Usage:
    from utils.query_modules.yaml_prompt_module import YamlPromptModule

    module = YamlPromptModule("boilerplate_substitution")
    system_prompt = module.build_system_prompt()
    user_prompt = module.format_user_prompt(text="...", designation="...")
"""

import logging
from typing import Any, Dict, List, Optional

from .module_base import QueryModule, QueryModuleConfig

logger = logging.getLogger(__name__)


class YamlPromptModule(QueryModule):
    """Query module driven by YAML prompt templates.

    Loads prompts from config/llm_prompts.yaml for a given task_type.
    Supports text generation tasks (boilerplate_substitution, semantic_proxy)
    as well as classification tasks.
    """

    def __init__(
        self,
        task_type: str,
        config: Optional[QueryModuleConfig] = None,
        reference_file=None,
        prompts: Optional[Dict[str, Any]] = None,
    ):
        """Initialize from YAML config or explicit prompt dict.

        Args:
            task_type: Key in llm_prompts.yaml (e.g., "boilerplate_substitution")
            config: Optional module config
            reference_file: Not used (compatibility with QueryModule interface)
            prompts: Optional explicit prompt dict (overrides YAML loading)
        """
        self._task_type = task_type

        # Load prompts before super().__init__() since base class
        # accesses module_name and output_categories during init
        if prompts is not None:
            self._prompts = prompts
        else:
            from utils.config_loader import load_llm_prompts
            self._prompts = load_llm_prompts(task_type)
            if self._prompts is None:
                raise ValueError(
                    f"No prompts found for task type '{task_type}' in "
                    f"config/llm_prompts.yaml"
                )

        super().__init__(config=config, reference_file=reference_file)

        logger.info(f"YamlPromptModule initialized for task '{task_type}'")

    # ── QueryModule interface ──────────────────────────────────────────

    @property
    def module_name(self) -> str:
        return self._task_type

    @property
    def output_categories(self) -> List[str]:
        """Categories for classification tasks; empty for generation tasks."""
        return self._prompts.get("categories", [])

    @property
    def description(self) -> str:
        return self._prompts.get("description", f"YAML-driven task: {self._task_type}")

    def build_system_prompt(self) -> str:
        return self._prompts.get("system_prompt", "")

    def build_user_prompt_template(self) -> str:
        return self._prompts.get("user_prompt_template", "")

    # ── Generation-specific methods ────────────────────────────────────

    @property
    def output_format(self) -> str:
        """Output format: 'text' for generation, 'json' for classification."""
        return self._prompts.get("output_format", "json")

    @property
    def max_output_tokens(self) -> int:
        return self._prompts.get("max_output_tokens", 1024)

    def format_user_prompt(self, **kwargs) -> str:
        """Format the user prompt template with the given values.

        Common placeholders:
            text: Input text to process
            designation: CDE designation for context
            tinyId: CDE identifier
            max_length: Target max output length

        For classification tasks:
            phrase_text, verbatim_forms, contexts, frequency, n_tinyids
        """
        template = self.build_user_prompt_template()
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing placeholder {e} in user prompt template for {self._task_type}")
            # Partial format: replace what we can, leave missing as-is
            for key, value in kwargs.items():
                template = template.replace(f"{{{key}}}", str(value))
            return template
