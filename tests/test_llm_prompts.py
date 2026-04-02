"""Tests for YAML-driven LLM prompt system.

Tests:
- config_loader.load_llm_prompts: loading from YAML
- config_loader.list_llm_prompt_tasks: listing available tasks
- YamlPromptModule: initialization and prompt formatting
"""

import pytest
from utils.config_loader import load_llm_prompts, list_llm_prompt_tasks


class TestLoadLlmPrompts:
    def test_loads_boilerplate_substitution(self):
        prompts = load_llm_prompts("boilerplate_substitution")
        assert prompts is not None
        assert "system_prompt" in prompts
        assert "user_prompt_template" in prompts
        assert "INCLUDE" in prompts["system_prompt"]
        assert "EXCLUDE" in prompts["system_prompt"]

    def test_loads_semantic_proxy(self):
        prompts = load_llm_prompts("semantic_proxy")
        assert prompts is not None
        assert "system_prompt" in prompts
        assert "proxy" in prompts["system_prompt"].lower()

    def test_unknown_task_returns_none(self):
        prompts = load_llm_prompts("nonexistent_task_xyz")
        assert prompts is None

    def test_boilerplate_excludes_items(self):
        """System prompt must instruct to exclude item counts and scales."""
        prompts = load_llm_prompts("boilerplate_substitution")
        sys = prompts["system_prompt"]
        assert "Number of items" in sys
        assert "Response format" in sys
        assert "Subscale" in sys
        assert "Licensing" in sys or "licensing" in sys

    def test_boilerplate_template_has_placeholders(self):
        prompts = load_llm_prompts("boilerplate_substitution")
        tpl = prompts["user_prompt_template"]
        assert "{text}" in tpl
        assert "{designation}" in tpl

    def test_output_format_field(self):
        prompts = load_llm_prompts("boilerplate_substitution")
        assert prompts.get("output_format") == "text"

    def test_max_output_tokens(self):
        prompts = load_llm_prompts("boilerplate_substitution")
        assert prompts.get("max_output_tokens") == 256


class TestListLlmPromptTasks:
    def test_lists_known_tasks(self):
        tasks = list_llm_prompt_tasks()
        assert "boilerplate_substitution" in tasks
        assert "semantic_proxy" in tasks

    def test_returns_sorted(self):
        tasks = list_llm_prompt_tasks()
        assert tasks == sorted(tasks)


class TestYamlPromptModule:
    def test_init_from_yaml(self):
        from utils.query_modules.yaml_prompt_module import YamlPromptModule
        module = YamlPromptModule("boilerplate_substitution")
        assert module.module_name == "boilerplate_substitution"
        assert module.output_format == "text"

    def test_init_unknown_raises(self):
        from utils.query_modules.yaml_prompt_module import YamlPromptModule
        with pytest.raises(ValueError, match="No prompts found"):
            YamlPromptModule("nonexistent_task_xyz")

    def test_init_from_explicit_prompts(self):
        from utils.query_modules.yaml_prompt_module import YamlPromptModule
        module = YamlPromptModule("custom", prompts={
            "system_prompt": "You are helpful.",
            "user_prompt_template": "Summarize: {text}",
            "output_format": "text",
        })
        assert module.build_system_prompt() == "You are helpful."

    def test_format_user_prompt(self):
        from utils.query_modules.yaml_prompt_module import YamlPromptModule
        module = YamlPromptModule("boilerplate_substitution")
        result = module.format_user_prompt(
            text="Some verbose definition text here.",
            designation="Test CDE Name",
        )
        assert "Test CDE Name" in result
        assert "Some verbose definition text here." in result

    def test_format_missing_placeholder_graceful(self):
        from utils.query_modules.yaml_prompt_module import YamlPromptModule
        module = YamlPromptModule("boilerplate_substitution")
        # Only provide text, not designation — should not crash
        result = module.format_user_prompt(text="Definition text.")
        assert "Definition text." in result

    def test_get_module_yaml_fallback(self):
        """get_module() falls back to YAML for non-registry tasks."""
        from utils.query_modules import get_module
        module = get_module("boilerplate_substitution")
        assert module.module_name == "boilerplate_substitution"

    def test_get_module_registry_still_works(self):
        """Existing registered modules still load normally."""
        from utils.query_modules import get_module
        module = get_module("instrument")
        assert module.module_name == "instrument"
