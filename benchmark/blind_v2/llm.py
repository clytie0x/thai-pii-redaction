"""Free or local prompt-only redaction.

Platform credentials are refused. This module never reads ``TOKENMIND_API_KEY``,
``APP_TOKENMIND_API_KEY``, or ``AIFORTHAI_API_KEY``. A provider response that
reports a non-zero cost aborts the baseline instead of continuing on a paid
model.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .score import dedupe_predictions
from .types import REDACTION_TYPE_SET, REDACTION_TYPES

_BLOCKED_CHOICES = ("tokenmind", "aiforthai", "pathumma")
_PREFERRED_LOCAL = ("gemma", "typhoon", "llama", "qwen")
_REDACTION_PROMPT = (
    "Find personal data in the document. Reply with a JSON array only. "
    'Each item is {"type": one of %s, "text": an exact substring}. '
    "No explanation.\nDocument:\n"
)


class LLMUnavailable(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class LLMProbe:
    available: bool
    reason: str
    kind: str = ""
    model: str = ""
    cost_usd: float | None = None


def probe_llm() -> LLMProbe:
    forced = os.environ.get("AIGUARD_BLIND_LLM", "").lower()
    if any(token in forced for token in _BLOCKED_CHOICES):
        return LLMProbe(
            False,
            "refusing the platform provider; this benchmark uses free or local models only",
        )
    names = _ollama_models()
    if names:
        return LLMProbe(True, "", "ollama", _choose_local(names), 0.0)
    llama = _llama_cpp()
    if llama is not None:
        binary, model = llama
        return LLMProbe(True, "", "llama_cpp", f"{Path(binary).name}:{Path(model).name}", 0.0)
    if os.environ.get("OPENROUTER_API_KEY"):
        return LLMProbe(True, "", "openrouter", "openrouter/free", 0.0)
    return LLMProbe(
        False,
        "no local Ollama model, llama.cpp model, or OpenRouter free-tier key is available",
    )


def complete(prompt: str, probe: LLMProbe | None = None) -> str:
    selected = probe or probe_llm()
    if not selected.available:
        raise LLMUnavailable(selected.reason)
    if selected.kind == "ollama":
        return _ollama_complete(selected.model, prompt)
    if selected.kind == "llama_cpp":
        return _llama_complete(prompt)
    if selected.kind == "openrouter":
        return _openrouter_complete(prompt)
    raise LLMUnavailable("no free or local model is selected")


def redact_prompt(document: str) -> str:
    names = ", ".join(REDACTION_TYPES)
    return _REDACTION_PROMPT % names + document


def parse_redaction(document: str, response: str) -> list[tuple[int, int, str]]:
    start = response.find("[")
    end = response.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        payload = json.loads(response[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    found: list[tuple[int, int, str]] = []
    cursor = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        entity_type = item.get("type")
        surface = item.get("text")
        if entity_type not in REDACTION_TYPE_SET or not isinstance(surface, str) or not surface:
            continue
        index = document.find(surface, cursor)
        if index < 0:
            index = document.find(surface)
        if index < 0:
            continue
        found.append((index, index + len(surface), str(entity_type)))
        cursor = index + len(surface)
    return dedupe_predictions(found)


class LLMRedactor:
    name = "llm"
    cost_usd = 0.0

    def __init__(self) -> None:
        self._probe = LLMProbe(False, "not prepared")

    def prepare(self) -> str | None:
        self._probe = probe_llm()
        if not self._probe.available:
            return self._probe.reason
        self.cost_usd = 0.0
        return None

    def predict(self, text: str) -> list[tuple[int, int, str]]:
        response = complete(redact_prompt(text), self._probe)
        return parse_redaction(text, response)


def _choose_local(names: list[str]) -> str:
    folded = [(name, name.lower()) for name in names]
    for needle in _PREFERRED_LOCAL:
        for name, lower in folded:
            if needle in lower:
                return name
    return names[0]


def _ollama_models() -> list[str]:
    try:
        import httpx
    except ImportError:
        return []
    try:
        response = httpx.get("http://127.0.0.1:11434/api/tags", timeout=0.5)
    except Exception:
        return []
    if response.status_code != 200:
        return []
    try:
        payload = response.json()
    except Exception:
        return []
    names = []
    for row in payload.get("models") or []:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            names.append(row["name"])
    return names


def _ollama_complete(model: str, prompt: str) -> str:
    import httpx

    response = httpx.post(
        "http://127.0.0.1:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=180,
    )
    if response.status_code != 200:
        raise LLMUnavailable(f"ollama status {response.status_code}")
    body = response.json()
    text = body.get("response")
    if not isinstance(text, str):
        raise LLMUnavailable("ollama returned no text")
    return text


def _llama_cpp() -> tuple[str, str] | None:
    binary = shutil.which("llama-cli") or shutil.which("llama-completion")
    model = os.environ.get("AIGUARD_BLIND_LLM_MODEL", "")
    if binary and model and Path(model).is_file():
        return binary, model
    return None


def _llama_complete(prompt: str) -> str:
    located = _llama_cpp()
    if located is None:
        raise LLMUnavailable("llama.cpp model is not available")
    binary, model = located
    try:
        completed = subprocess.run(
            [binary, "-m", model, "-p", prompt, "-n", "128", "--temp", "0", "-ngl", "0"],
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LLMUnavailable(f"llama.cpp failed ({type(exc).__name__})") from None
    if completed.returncode != 0:
        raise LLMUnavailable("llama.cpp returned a non-zero status")
    return completed.stdout


def _openrouter_complete(prompt: str) -> str:
    import httpx

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise LLMUnavailable("OpenRouter free-tier key is not available")
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "openrouter/free",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=180,
    )
    if response.status_code != 200:
        raise LLMUnavailable(f"openrouter status {response.status_code}")
    body = response.json()
    usage = body.get("usage") if isinstance(body, dict) else None
    cost = usage.get("cost") if isinstance(usage, dict) else None
    if isinstance(cost, (int, float)) and cost > 0:
        raise LLMUnavailable("openrouter reported a non-zero cost; paid calls are refused")
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMUnavailable(f"openrouter returned no text ({type(exc).__name__})") from None
    if not isinstance(text, str):
        raise LLMUnavailable("openrouter returned no text")
    return text
