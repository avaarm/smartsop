"""LLM provider abstraction: Ollama first, with optional OpenAI / Anthropic
fallback when the local model is unreachable.

The goal is to keep SmartSOP's "your data stays on your machine" promise by
default (Ollama is used whenever it's running) while also unblocking users
who can't or don't want to install Ollama. They can flip to a cloud
provider by configuring an API key — either through the first-run wizard
(which writes to ``~/.smartsop/llm.json``) or via env vars for headless use.

Intentionally no SDK dependency — pure ``requests`` — so the PyInstaller
bundle stays small and we don't chase version churn in openai / anthropic
client libraries.

Config precedence (later wins):
  1. Env vars
  2. ``~/.smartsop/llm.json`` (written by the frontend wizard)

Env vars / config keys:

  LLM_PROVIDER          ollama (default) | openai | anthropic
  OPENAI_API_KEY        required when using OpenAI
  OPENAI_MODEL          default: gpt-4o-mini
  OPENAI_BASE_URL       default: https://api.openai.com/v1
  ANTHROPIC_API_KEY     required when using Anthropic
  ANTHROPIC_MODEL       default: claude-3-5-haiku-20241022
  ANTHROPIC_BASE_URL    default: https://api.anthropic.com
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ── Base interface ─────────────────────────────────────────────────

class LLMProvider:
    """Common interface every concrete provider implements.

    Callers (``ProtocolAnalyzer``, ``DocumentGenerator``) only talk to
    this surface so swapping providers never touches business logic.
    """

    name: str = "abstract"
    model: str = ""

    def check_health(self) -> bool:  # pragma: no cover - implemented by subclass
        raise NotImplementedError

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
        json_mode: bool = False,
    ) -> str:  # pragma: no cover - implemented by subclass
        raise NotImplementedError

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> dict:
        """Default JSON-gen impl: call generate with ``json_mode`` and parse.

        Subclasses can override when a provider has a native JSON mode that
        needs a different payload shape.
        """
        raw = self.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return _parse_json_robust(raw)


# ── OpenAI ─────────────────────────────────────────────────────────

class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL")
                         or "https://api.openai.com/v1").rstrip("/")
        self.timeout = 120

    def check_health(self) -> bool:
        if not self.api_key:
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=8,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt, system_prompt=None, temperature=0.3,
                 max_tokens=8192, json_mode=False) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OpenAI provider selected but OPENAI_API_KEY is not set."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            return body["choices"][0]["message"]["content"] or ""
        except requests.Timeout:
            raise RuntimeError("OpenAI request timed out")
        except requests.HTTPError as e:
            raise RuntimeError(
                f"OpenAI error: {e.response.status_code} {e.response.text[:300]}"
            )
        except requests.ConnectionError:
            raise RuntimeError("Cannot reach OpenAI API — check your network")


# ── Anthropic ──────────────────────────────────────────────────────

class AnthropicProvider(LLMProvider):
    name = "anthropic"
    # Anthropic requires you to pin an API version.
    api_version = "2023-06-01"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get(
            "ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"
        )
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL")
                         or "https://api.anthropic.com").rstrip("/")
        self.timeout = 120

    def check_health(self) -> bool:
        if not self.api_key:
            return False
        # Anthropic doesn't expose a cheap health endpoint; do a minimal
        # 1-token generation. Cheap enough to ping on app startup.
        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages",
                json={
                    "model": self.model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}],
                },
                headers=self._headers(),
                timeout=8,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def generate(self, prompt, system_prompt=None, temperature=0.3,
                 max_tokens=8192, json_mode=False) -> str:
        if not self.api_key:
            raise RuntimeError(
                "Anthropic provider selected but ANTHROPIC_API_KEY is not set."
            )

        # Claude has no native json_mode like OpenAI — fold the instruction
        # into the system prompt when requested.
        sys_parts = [system_prompt] if system_prompt else []
        if json_mode:
            sys_parts.append(
                "Return only a single valid JSON object. "
                "No prose before or after the JSON."
            )

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_parts:
            payload["system"] = "\n\n".join(sys_parts)

        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            resp.raise_for_status()
            body = resp.json()
            # Anthropic returns list of content blocks; concatenate text.
            parts = []
            for block in body.get("content", []) or []:
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
            return "".join(parts)
        except requests.Timeout:
            raise RuntimeError("Anthropic request timed out")
        except requests.HTTPError as e:
            raise RuntimeError(
                f"Anthropic error: {e.response.status_code} {e.response.text[:300]}"
            )
        except requests.ConnectionError:
            raise RuntimeError("Cannot reach Anthropic API — check your network")

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": self.api_version,
            "Content-Type": "application/json",
        }


# ── JSON parsing helper ────────────────────────────────────────────

def _parse_json_robust(raw: str) -> dict:
    """Parse JSON from a model response, stripping markdown fences and
    repairing truncated outputs. Mirrors ``OllamaService.generate_json``."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass

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
        f"first 300 chars: {raw[:300]!r}"
    )


# ── Factory ────────────────────────────────────────────────────────

CONFIG_PATH = Path.home() / ".smartsop" / "llm.json"


def load_config() -> dict:
    """Read the user-level LLM config file, merged on top of env vars.

    Returns a dict with keys ``provider``, ``openai_api_key``,
    ``anthropic_api_key``, ``openai_model``, ``anthropic_model``.
    """
    cfg: dict = {
        "provider": (os.environ.get("LLM_PROVIDER") or "").strip().lower(),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "openai_model": os.environ.get("OPENAI_MODEL", ""),
        "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
        "anthropic_model": os.environ.get("ANTHROPIC_MODEL", ""),
    }
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            for k, v in data.items():
                if v:
                    cfg[k] = v
    except Exception as e:
        logger.warning("Could not read %s: %s", CONFIG_PATH, e)
    return cfg


def save_config(partial: dict) -> dict:
    """Write/update the LLM config file atomically and return the merged config.

    Only known keys are persisted. Existing values are preserved when the
    caller omits them (partial update semantics).
    """
    allowed = {
        "provider", "openai_api_key", "openai_model",
        "anthropic_api_key", "anthropic_model",
    }
    # Merge with whatever's already on disk
    existing: dict = {}
    try:
        if CONFIG_PATH.exists():
            existing = json.loads(CONFIG_PATH.read_text()) or {}
    except Exception:
        existing = {}

    for k, v in (partial or {}).items():
        if k in allowed:
            existing[k] = v

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, indent=2))
    tmp.replace(CONFIG_PATH)
    # Restrict file permissions — contains API keys.
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    return existing


def build_fallback_provider() -> Optional[LLMProvider]:
    """Construct the configured non-Ollama fallback provider, if any.

    Merges env vars + ``~/.smartsop/llm.json``. Resolution order:
      1. Explicit ``provider`` selection
      2. Presence of Anthropic credentials → Anthropic
      3. Presence of OpenAI credentials → OpenAI
      4. None (Ollama-only mode)
    """
    cfg = load_config()
    provider = (cfg.get("provider") or "").strip().lower()

    if provider == "openai" and cfg.get("openai_api_key"):
        return OpenAIProvider(
            api_key=cfg["openai_api_key"],
            model=cfg.get("openai_model") or None,
        )
    if provider == "anthropic" and cfg.get("anthropic_api_key"):
        return AnthropicProvider(
            api_key=cfg["anthropic_api_key"],
            model=cfg.get("anthropic_model") or None,
        )

    # Auto-detect by available credentials.
    if cfg.get("anthropic_api_key"):
        return AnthropicProvider(
            api_key=cfg["anthropic_api_key"],
            model=cfg.get("anthropic_model") or None,
        )
    if cfg.get("openai_api_key"):
        return OpenAIProvider(
            api_key=cfg["openai_api_key"],
            model=cfg.get("openai_model") or None,
        )
    return None
