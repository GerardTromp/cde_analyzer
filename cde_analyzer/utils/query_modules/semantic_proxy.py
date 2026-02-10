"""
Semantic proxy generation query module.

Generates short (1-3 word) semantic proxies for long instrument/boilerplate
phrases. Unlike classification modules, the output is a replacement string
rather than a category.
"""

from typing import List, Dict, Optional, Tuple

from .module_base import QueryModule, QueryModuleConfig


class SemanticProxyModule(QueryModule):
    """
    Query module for generating semantic proxies for phrase substitution.

    Given a long instrument or boilerplate phrase and its CDE context,
    generates a 1-3 word semantic proxy that captures the essential meaning
    without causing CDEs to cluster by instrument name.

    Output JSON format:
        {"proxy": "depression-screen", "confidence": 0.9, "reasoning": "..."}
    """

    @property
    def module_name(self) -> str:
        return "semantic_proxy"

    @property
    def output_categories(self) -> List[str]:
        # Not used for classification, but required by base class.
        # We repurpose the category field to hold the proxy string.
        return ["_proxy_placeholder"]

    @property
    def description(self) -> str:
        return "Generate short semantic proxies for long phrases (substitution wireframe)"

    def build_system_prompt(self) -> str:
        return """You are an expert in biomedical terminology and clinical data harmonization.

## Task

Given a long phrase that appears in Common Data Element (CDE) text fields,
generate a SHORT semantic proxy (1-3 hyphenated words) that captures the
phrase's essential meaning.

The proxy will REPLACE the original phrase in the text before embedding
and clustering. The goal is to preserve semantic signal (what domain the
CDE relates to) without letting long instrument names dominate clustering.

## Rules

1. Output 1-3 words, hyphenated (e.g., "depression-screen")
2. Capture the SEMANTIC ROLE, not the instrument name
   - Good: "depression-screen" (what it measures)
   - Bad: "phq9" (just an abbreviation of the name)
3. For instruments, focus on what they measure or assess
4. For boilerplate phrases, focus on what they indicate about the CDE
5. If a phrase is truly content-free (punctuation, connectors), use "boilerplate"
6. Prefer established medical/clinical domain terms

## Examples

- "Patient Health Questionnaire-9 (PHQ-9)" -> "depression-screen"
- "Unified Parkinson's Disease Rating Scale" -> "parkinson-motor"
- "as part of the Neuro-QOL Upper Extremity Function" -> "upper-limb-function"
- "Center for Epidemiologic Studies Depression Scale (CES-D)" -> "depression-scale"
- "PROMIS Physical Function" -> "physical-function"
- "in the past 7 days" -> "recency-window"
- "on a scale from 0 to 10" -> "numeric-rating"

## Output Format

Respond with valid JSON only:
```json
{
  "proxy": "short-proxy-text",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of why this proxy captures the semantic essence"
}
```"""

    def build_user_prompt_template(self) -> str:
        return """Generate a semantic proxy for this phrase:

**Phrase**: {phrase_text}

{context_section}

What 1-3 word proxy captures the semantic essence of this phrase?"""

    def parse_response(self, response_text: str) -> Tuple[str, float, str]:
        """
        Parse LLM response to extract proxy.

        Returns (proxy, confidence, reasoning) where proxy is stored
        in the category field position.
        """
        import json
        import re

        try:
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response_text)

            proxy = data.get("proxy", "").strip().lower()
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

            # Normalize: replace spaces with hyphens, strip quotes
            proxy = proxy.replace(" ", "-").strip('"\'')

            confidence = max(0.0, min(1.0, confidence))
            return proxy, confidence, reasoning

        except (json.JSONDecodeError, ValueError, KeyError):
            return "", 0.0, f"Failed to parse response: {response_text[:200]}"

    def get_json_schema(self) -> Dict:
        """JSON schema for proxy generation output."""
        return {
            "type": "object",
            "properties": {
                "proxy": {
                    "type": "string",
                    "description": "1-3 word hyphenated semantic proxy",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Confidence in the proxy quality",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of the proxy choice",
                },
            },
            "required": ["proxy", "confidence", "reasoning"],
        }
