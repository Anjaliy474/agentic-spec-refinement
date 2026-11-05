"""Model backends.

Every component (orchestrator, critics, baselines) talks to a model through the
``LLM`` interface, so the same pipeline can run on a local Ollama model, any
OpenAI-compatible server (LM Studio, vLLM, llama.cpp server, hosted APIs), or
the scripted ``FakeLLM`` used in tests.

Each call is recorded in ``LLM.usage`` so experiments can report token cost
and latency per component (needed for H2).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class CallRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    tag: str = ""


@dataclass
class Usage:
    calls: list[CallRecord] = field(default_factory=list)

    @property
    def prompt_tokens(self) -> int:
        return sum(c.prompt_tokens for c in self.calls)

    @property
    def completion_tokens(self) -> int:
        return sum(c.completion_tokens for c in self.calls)

    @property
    def seconds(self) -> float:
        return sum(c.seconds for c in self.calls)

    def summary(self) -> dict:
        return {
            "calls": len(self.calls),
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "seconds": round(self.seconds, 3),
        }


class LLM(ABC):
    """A text-in, text-out model."""

    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.usage = Usage()

    @abstractmethod
    def _complete(self, system: str, prompt: str, json_mode: bool) -> tuple[str, int, int]:
        """Return (text, prompt_tokens, completion_tokens)."""

    def complete(self, prompt: str, system: str = "", json_mode: bool = False, tag: str = "") -> str:
        start = time.perf_counter()
        text, p_tok, c_tok = self._complete(system, prompt, json_mode)
        self.usage.calls.append(
            CallRecord(self.model, p_tok, c_tok, time.perf_counter() - start, tag)
        )
        return text

    def complete_json(self, prompt: str, system: str = "", tag: str = "", retries: int = 1):
        """Ask for JSON and parse it, retrying once with the parse error if needed."""
        text = self.complete(prompt, system, json_mode=True, tag=tag)
        for attempt in range(retries + 1):
            try:
                return parse_json(text)
            except ValueError as err:
                if attempt == retries:
                    raise
                text = self.complete(
                    f"{prompt}\n\nYour previous answer was not valid JSON ({err}). "
                    "Reply with valid JSON only.",
                    system,
                    json_mode=True,
                    tag=f"{tag}:retry",
                )
        raise AssertionError("unreachable")


def parse_json(text: str):
    """Parse JSON from model output, tolerating code fences and surrounding prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if starts:
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as err:
                raise ValueError(str(err)) from err
    raise ValueError("no JSON object found in model output")


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 600) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class OllamaLLM(LLM):
    """A model served by a local Ollama instance."""

    def __init__(self, model: str, host: str | None = None, temperature: float = 0.0, seed: int = 0):
        super().__init__(model, temperature)
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        if not self.host.startswith("http"):
            self.host = f"http://{self.host}"
        self.seed = seed

    def _complete(self, system: str, prompt: str, json_mode: bool) -> tuple[str, int, int]:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "seed": self.seed},
        }
        if json_mode:
            body["format"] = "json"
        out = _post(f"{self.host}/api/chat", body)
        return (
            out["message"]["content"],
            out.get("prompt_eval_count", 0),
            out.get("eval_count", 0),
        )


class OpenAICompatLLM(LLM):
    """Any server exposing the OpenAI chat-completions API."""

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
    ):
        super().__init__(model, temperature)
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "not-needed")

    def _complete(self, system: str, prompt: str, json_mode: bool) -> tuple[str, int, int]:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        body = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        out = _post(
            f"{self.base_url}/chat/completions",
            body,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        usage = out.get("usage", {})
        return (
            out["choices"][0]["message"]["content"],
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )


class FakeLLM(LLM):
    """Scripted model for tests and offline demos.

    ``responder`` maps (system, prompt) to a reply string. Token counts are
    approximated by whitespace word counts.
    """

    def __init__(self, responder: Callable[[str, str], str], model: str = "fake"):
        super().__init__(model)
        self.responder = responder

    def _complete(self, system: str, prompt: str, json_mode: bool) -> tuple[str, int, int]:
        text = self.responder(system, prompt)
        return text, len(f"{system} {prompt}".split()), len(text.split())


def make_llm(spec: dict) -> LLM:
    """Build a backend from a config entry such as ``{"backend": "ollama", "model": "qwen2.5:7b"}``."""
    spec = dict(spec)
    backend = spec.pop("backend", "ollama")
    if backend == "ollama":
        return OllamaLLM(**spec)
    if backend == "openai":
        return OpenAICompatLLM(**spec)
    raise ValueError(f"unknown backend: {backend}")
