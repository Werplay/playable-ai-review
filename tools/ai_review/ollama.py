from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .core import Usage, json_objects

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_EMBED_MODEL = "qwen3-embedding:0.6b"


class OllamaError(RuntimeError):
    pass


@dataclass
class OllamaClient:
    base_url: str = ""
    model: str = ""
    embedding_model: str = ""
    timeout: int = 300

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = self.model or os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
        self.embedding_model = self.embedding_model or os.environ.get("OLLAMA_EMBEDDING_MODEL", DEFAULT_EMBED_MODEL)

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OllamaError(f"Ollama request to {path} failed: {exc}") from exc

    def verify_models(self) -> None:
        tags = self._request("/api/tags")
        names = {m.get("name") for m in tags.get("models", [])} | {m.get("model") for m in tags.get("models", [])}
        missing = [m for m in (self.model, self.embedding_model) if m not in names and m.split(":")[0] not in names]
        if missing:
            commands = "\n".join(f"  ollama pull {m}" for m in missing)
            raise OllamaError(f"Required local model(s) missing. Run:\n{commands}")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._request("/api/embed", {"model": self.embedding_model, "input": texts, "truncate": True})
        vectors = result.get("embeddings") or []
        if len(vectors) != len(texts) or not all(isinstance(v, list) and v for v in vectors):
            raise OllamaError("Ollama returned an invalid embedding batch")
        dimension = len(vectors[0])
        if any(len(v) != dimension for v in vectors):
            raise OllamaError("Ollama returned inconsistent embedding dimensions")
        return vectors

    def generate_json(self, prompt: str, num_predict: int = 4096) -> tuple[Any, Usage]:
        usage = Usage()
        last_error: Exception | None = None
        for limit in (num_predict, num_predict * 2):
            response = self._request("/api/generate", {
                "model": self.model, "prompt": prompt, "stream": False, "format": "json",
                "options": {"temperature": 0.1, "num_predict": limit},
            })
            usage = Usage(int(response.get("prompt_eval_count", 0)), int(response.get("eval_count", 0)), int(response.get("total_duration", 0)), "length" if not response.get("done", True) else "stop")
            try:
                return json_objects(str(response.get("response", ""))), usage
            except ValueError as exc:
                last_error = exc
        raise OllamaError(f"Ollama returned malformed JSON after retry: {last_error}")
