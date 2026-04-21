"""Ollama LLM integration service for GMP document content generation.

When Ollama isn't reachable and an OpenAI/Anthropic API key is
configured via environment variables, generation transparently falls
back to the cloud provider. See ``ml_model.gmp.llm_provider`` for the
provider abstraction.
"""

import json
import logging
import requests
from typing import Optional

from .llm_provider import LLMProvider, build_fallback_provider

logger = logging.getLogger(__name__)


class OllamaService:
    """Client for the Ollama local LLM API with optional cloud fallback."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3",
                 fallback: Optional[LLMProvider] = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 120  # seconds
        # Auto-build a fallback provider from env vars unless one was
        # passed in explicitly. Keeps the "local-first" default — the
        # fallback is only *used* when Ollama is unreachable.
        self.fallback: Optional[LLMProvider] = (
            fallback if fallback is not None else build_fallback_provider()
        )

    @property
    def active_provider_name(self) -> str:
        """Return the name of the provider that would handle a request
        right now — "ollama" when it's healthy, else the fallback's name,
        or "none" when neither is available."""
        if self.check_health():
            return "ollama"
        if self.fallback and self.fallback.check_health():
            return self.fallback.name
        return "none"

    def check_health(self) -> bool:
        """Check if Ollama is running and responsive."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def list_models(self) -> list[dict]:
        """List available models in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            return resp.json().get("models", [])
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                 temperature: float = 0.3, max_tokens: int = 8192,
                 json_mode: bool = False) -> str:
        """Generate text using Ollama.

        Args:
            prompt: The user prompt
            system_prompt: Optional system-level instructions
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            json_mode: If True, use Ollama's native JSON format constraint

        Returns:
            Generated text string
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if json_mode:
            payload["format"] = "json"

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.ConnectionError:
            # Ollama isn't running — try the configured cloud fallback
            # before giving up. Users who configured an API key get a
            # working experience without having to run Ollama at all.
            if self.fallback is not None:
                logger.info(
                    "Ollama unreachable — falling back to %s", self.fallback.name
                )
                return self.fallback.generate(
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            logger.error("Cannot connect to Ollama. Is it running? (ollama serve)")
            raise RuntimeError(
                "Ollama is not running. Start it with: ollama serve "
                "— or configure OPENAI_API_KEY / ANTHROPIC_API_KEY to use a cloud provider."
            )
        except requests.Timeout:
            logger.error("Ollama request timed out")
            raise RuntimeError("LLM request timed out. Try a shorter prompt.")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: float = 0.2, max_tokens: int = 8192) -> dict:
        """Generate and parse JSON output from the LLM.

        Uses Ollama's native JSON format constraint for reliable output.
        """
        raw = self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        raw = raw.strip()
        # Strip markdown fences if the model added them despite json_mode
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}")
            logger.debug(f"Raw output length: {len(raw)}; first 1000 chars:\n{raw[:1000]}")

            # Try to find JSON object bounds
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except json.JSONDecodeError:
                    pass

            # As a last resort, try to repair truncated JSON by appending closing braces
            if start >= 0:
                candidate = raw[start:]
                open_braces = candidate.count("{") - candidate.count("}")
                open_brackets = candidate.count("[") - candidate.count("]")
                if open_braces > 0 or open_brackets > 0:
                    repaired = candidate + ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
                    try:
                        return json.loads(repaired)
                    except json.JSONDecodeError:
                        pass

            raise ValueError(
                f"LLM did not produce valid JSON. Length={len(raw)}, "
                f"starts with: {raw[:200]!r}"
            )

    def generate_section_content(
        self,
        section_type: str,
        context: dict,
        custom_prompt: Optional[str] = None,
        extra_system: Optional[str] = None,
        temperature: float = 0.3,
    ) -> dict:
        """Generate content for a specific document section in JSON mode.

        Uses ``generate_json`` so the provider enforces JSON output and
        layers the strict GMP system prompt (``GMP_SYSTEM_PROMPT``) on
        top of any account-specific supplement.

        Args:
            section_type: Type key (``procedure_steps``, ``equipment_list``…)
            context: Template variables (product_name, process_type, …)
            custom_prompt: Optional override for the section prompt
            extra_system: Account-specific prompt supplement (style notes,
                terminology, few-shot examples) — appended to the base
                system prompt.
            temperature: Sampling temperature.

        Returns:
            Parsed JSON dict.
        """
        from .prompts import get_section_prompt, GMP_SYSTEM_PROMPT

        system = GMP_SYSTEM_PROMPT
        if extra_system:
            system = f"{system}\n\n---\n{extra_system}"

        prompt = custom_prompt or get_section_prompt(section_type, context)
        return self.generate_json(prompt, system_prompt=system, temperature=temperature)

    def generate_flowchart_steps(self, process_description: str) -> list[dict]:
        """Generate structured flowchart steps from a process description.

        Returns:
            List of dicts with keys: id, label, type (action/decision/start/end),
            next (list of {target_id, label})
        """
        from .prompts import FLOWCHART_GENERATION_PROMPT

        system = (
            "You are a process flow expert for pharmaceutical manufacturing. "
            "Generate clear, sequential process flowcharts with decision points."
        )

        prompt = FLOWCHART_GENERATION_PROMPT.format(
            process_description=process_description
        )

        result = self.generate_json(prompt, system_prompt=system)
        return result.get("steps", [])
