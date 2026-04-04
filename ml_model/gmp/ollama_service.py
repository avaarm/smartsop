"""Ollama LLM integration service for GMP document content generation."""

import json
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaService:
    """Client for the Ollama local LLM API."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 120  # seconds

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
                 temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """Generate text using Ollama.

        Args:
            prompt: The user prompt
            system_prompt: Optional system-level instructions
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate

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

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except requests.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running? (ollama serve)")
            raise RuntimeError(
                "Ollama is not running. Start it with: ollama serve"
            )
        except requests.Timeout:
            logger.error("Ollama request timed out")
            raise RuntimeError("LLM request timed out. Try a shorter prompt.")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: float = 0.2) -> dict:
        """Generate and parse JSON output from the LLM.

        Adds JSON formatting instructions to the prompt and parses the response.
        """
        json_prompt = (
            f"{prompt}\n\n"
            "IMPORTANT: Respond with valid JSON only. No markdown, no explanation, "
            "no code fences. Just the JSON object."
        )
        raw = self.generate(json_prompt, system_prompt, temperature)

        # Try to extract JSON from the response
        raw = raw.strip()
        # Remove markdown code fences if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first and last lines if they're fences
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}")
            logger.debug(f"Raw output: {raw[:500]}")
            # Try to find JSON object in the text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(raw[start:end])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM did not produce valid JSON: {raw[:200]}")

    def generate_section_content(self, section_type: str, context: dict,
                                 custom_prompt: Optional[str] = None) -> str:
        """Generate content for a specific document section.

        Args:
            section_type: Type of section (e.g. 'procedure_steps', 'equipment_list')
            context: Dict with context info (product_name, process_type, etc.)
            custom_prompt: Optional override for the section-specific prompt

        Returns:
            Generated content string
        """
        from .prompts import get_section_prompt

        system = (
            "You are a GMP documentation specialist for pharmaceutical and "
            "biotech manufacturing. Generate precise, regulatory-compliant "
            "content for GMP documents. Use technical language appropriate for "
            "cell therapy and biologics manufacturing. Be specific and detailed."
        )

        prompt = custom_prompt or get_section_prompt(section_type, context)
        return self.generate(prompt, system_prompt=system, temperature=0.3)

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
