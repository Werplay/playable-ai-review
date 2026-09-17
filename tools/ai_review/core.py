from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
MAX_FILE_BYTES = 1_000_000
MAX_CHUNK_LINES = 120
MAX_CHUNK_CHARS = 4_000
CHUNK_OVERLAP = 12


@dataclass
class ChangedFile:
    path: str
    status: str
    old_path: str | None = None
    patch: str = ""
    base: str = ""
    proposed: str = ""
    binary: bool = False
    generated: bool = False


@dataclass
class Finding:
    severity: str
    category: str
    file: str
    line: int
    evidence: str
    scenario: str
    explanation: str
    recommendation: str
    introduced: bool = True
    source: str = "model"
    classification: str = "needs_human_review"
    confidence: str = "medium"
    rejection_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: str = "model") -> "Finding":
        return cls(
            severity=str(data.get("severity", "medium")).lower(),
            category=str(data.get("category", "correctness")),
            file=str(data.get("file", "")), line=int(data.get("line") or 1),
            evidence=str(data.get("evidence", "")), scenario=str(data.get("scenario", "")),
            explanation=str(data.get("explanation", "")), recommendation=str(data.get("recommendation", "")),
            introduced=bool(data.get("introduced", True)), source=source,
            confidence=str(data.get("confidence", "medium")),
        )

    def dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Usage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    duration_ns: int = 0
    completion_reason: str = "stop"

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.output_tokens


def sha256(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    return hashlib.sha256(data).hexdigest()


def normalized_repo_id(root: Path) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", f"{root.name}-{sha256(str(root.resolve()))[:12]}")


def cache_dir(root: Path) -> Path:
    override = os.environ.get("AI_REVIEW_INDEX_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ai-review"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg).expanduser() / "ai-review" if xdg else Path.home() / ".cache" / "ai-review"


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|authorization)(\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp|github_pat|sk-[A-Za-z0-9])[_A-Za-z0-9-]{16,}\b"),
]


def redact(text: str, limit: int | None = None) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) + m.group(2) if m.lastindex and m.lastindex >= 2 else "") + "[REDACTED]", text)
    return text if limit is None or len(text) <= limit else text[:limit] + "…"


def normalize_evidence(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).replace(" ;", ";")


def evidence_occurs(evidence: str, content: str) -> bool:
    needle = normalize_evidence(evidence)
    return bool(needle) and needle in normalize_evidence(content)


def serialize_vector(vector: Iterable[float]) -> bytes:
    import struct
    values = list(vector)
    return struct.pack(f"<{len(values)}f", *values)


def deserialize_vector(blob: bytes, dimensions: int) -> list[float]:
    import struct
    if len(blob) != dimensions * 4:
        raise ValueError("embedding byte length does not match dimensions")
    return list(struct.unpack(f"<{dimensions}f", blob))


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    denominator = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


def json_objects(text: str) -> Any:
    """Recover JSON from plain, fenced, or mildly truncated model output."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (cleaned.find("["), cleaned.find("{")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("model response contained no JSON")
    candidate = cleaned[start:]
    for end in range(len(candidate), 0, -1):
        fragment = candidate[:end].rstrip(" ,\n\t")
        for suffix in ("", "]", "}", "}]", "]}"):
            try:
                return json.loads(fragment + suffix)
            except json.JSONDecodeError:
                continue
    raise ValueError("model response JSON was incomplete")


def identifiers(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[A-Za-z_$][A-Za-z0-9_$]{2,}", text) if x.lower() not in {"const", "return", "function", "class", "import", "from", "this", "that", "with"}}
