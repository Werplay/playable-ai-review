from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .core import (CHUNK_OVERLAP, MAX_CHUNK_CHARS, MAX_CHUNK_LINES, MAX_FILE_BYTES,
                   SCHEMA_VERSION, cosine, deserialize_vector, identifiers,
                   serialize_vector, sha256)

EXCLUDED_PARTS = {".git", "node_modules", "vendor", "dist", "build", "coverage", ".cache", "__pycache__", ".venv", "venv"}
EXCLUDED_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp3", ".mp4", ".zip", ".gz", ".pdf", ".woff", ".woff2", ".lock", ".min.js", ".min.css"}
SECRET_NAMES = {".env", ".env.local", ".npmrc", ".pypirc", "credentials", "id_rsa", "id_ed25519"}


@dataclass
class IndexStats:
    files: int = 0
    chunks: int = 0
    embedded: int = 0
    reused: int = 0
    deleted: int = 0
    dimensions: int = 0


def language(path: str) -> str:
    return {".py":"python", ".ts":"typescript", ".tsx":"tsx", ".js":"javascript", ".jsx":"jsx", ".go":"go", ".rs":"rust", ".java":"java", ".md":"markdown"}.get(Path(path).suffix.lower(), "text")


def eligible(path: str, root: Path) -> bool:
    p = Path(path)
    low = p.name.lower()
    if any(part in EXCLUDED_PARTS for part in p.parts) or low in SECRET_NAMES or low.startswith(".env"):
        return False
    if any(low.endswith(s) for s in EXCLUDED_SUFFIXES):
        return False
    try:
        raw = (root / p).read_bytes()
    except (OSError, UnicodeError):
        return False
    return len(raw) <= MAX_FILE_BYTES and b"\0" not in raw


def chunk_text(path: str, text: str) -> list[tuple[int, int, str, str]]:
    lines = text.splitlines()
    chunks, start = [], 0
    while start < len(lines):
        end = min(start + MAX_CHUNK_LINES, len(lines))
        while end > start + 1 and len("\n".join(lines[start:end])) > MAX_CHUNK_CHARS:
            end -= 1
        # Prefer ending just before a symbol declaration near the boundary.
        for candidate in range(end - 1, max(start + 20, end - 25), -1):
            if re.match(r"^\s*(?:export\s+)?(?:async\s+)?(?:def|class|function|interface|type|const\s+\w+\s*=\s*(?:async\s*)?\()\b", lines[candidate]):
                end = candidate
                break
        body = "\n".join(lines[start:end])
        digest = sha256(body)
        chunks.append((start + 1, end, body, digest))
        if end >= len(lines): break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


class RepositoryIndex:
    def __init__(self, root: Path, db_path: Path, embedder):
        self.root, self.db_path, self.embedder = root, db_path, embedder
        db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self, rebuild: bool = False) -> None:
        if rebuild and self.db_path.exists(): self.db_path.unlink()
        with self.connect() as con:
            con.executescript("""
              CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS repositories(id INTEGER PRIMARY KEY CHECK(id=1), root TEXT, head TEXT, indexed_at INTEGER);
              CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, content_hash TEXT, size INTEGER, mtime INTEGER, indexed_at INTEGER);
              CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, path TEXT, start_line INTEGER, end_line INTEGER, language TEXT, content_hash TEXT, text TEXT NOT NULL, embedding BLOB, embedding_model TEXT, dimensions INTEGER, indexed_at INTEGER);
              CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
              CREATE INDEX IF NOT EXISTS chunks_hash ON chunks(content_hash);
            """)
            old = con.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if old and int(old[0]) != SCHEMA_VERSION:
                raise RuntimeError(f"index schema {old[0]} is incompatible with {SCHEMA_VERSION}; use --rebuild-index")
            con.execute("INSERT OR REPLACE INTO metadata VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))

    def tracked(self) -> list[str]:
        raw = subprocess.run(["git", "ls-files", "-z"], cwd=self.root, check=True, stdout=subprocess.PIPE).stdout
        return [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p]

    def update(self, rebuild: bool = False, batch_size: int = 16) -> IndexStats:
        self.initialize(rebuild)
        stats, now = IndexStats(), int(time.time())
        paths = [p for p in self.tracked() if eligible(p, self.root)]
        with self.connect() as con:
            prior = {r["path"]: r["content_hash"] for r in con.execute("SELECT path,content_hash FROM files")}
            cached = {}
            for row in con.execute("SELECT content_hash,embedding,embedding_model,dimensions FROM chunks WHERE embedding IS NOT NULL"):
                cached[row["content_hash"]] = (row["embedding"], row["embedding_model"], row["dimensions"])
            current = set(paths)
            for stale in set(prior) - current:
                con.execute("DELETE FROM chunks WHERE path=?", (stale,)); con.execute("DELETE FROM files WHERE path=?", (stale,)); stats.deleted += 1
            pending: list[tuple[str,int,int,str,str,str]] = []
            for path in paths:
                raw = (self.root / path).read_bytes(); file_hash = sha256(raw)
                if prior.get(path) == file_hash:
                    stats.reused += con.execute("SELECT count(*) FROM chunks WHERE path=?", (path,)).fetchone()[0]
                    continue
                con.execute("DELETE FROM chunks WHERE path=?", (path,))
                text = raw.decode("utf-8", "replace")
                for start, end, body, digest in chunk_text(path, text): pending.append((path,start,end,language(path),body,digest))
                con.execute("INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)", (path,file_hash,len(raw),int((self.root/path).stat().st_mtime),now))
            owner = getattr(self.embedder, "__self__", None)
            model = getattr(owner, "embedding_model", getattr(self.embedder, "model", "local"))
            missing = []
            for item in pending:
                old = cached.get(item[5])
                if old and old[1] == model:
                    con.execute("INSERT INTO chunks(path,start_line,end_line,language,content_hash,text,embedding,embedding_model,dimensions,indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (*item[:4],item[5],item[4],old[0],old[1],old[2],now))
                    stats.reused += 1
                    if not stats.dimensions: stats.dimensions = old[2]
                else:
                    missing.append(item)
            for offset in range(0, len(missing), batch_size):
                batch = missing[offset:offset+batch_size]
                vectors = self.embedder([x[4] for x in batch])
                for item, vector in zip(batch, vectors):
                    if not stats.dimensions: stats.dimensions = len(vector)
                    if len(vector) != stats.dimensions: raise RuntimeError("embedding dimensions changed during indexing")
                    con.execute("INSERT INTO chunks(path,start_line,end_line,language,content_hash,text,embedding,embedding_model,dimensions,indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (*item[:4],item[5],item[4],serialize_vector(vector),model,len(vector),now))
                    stats.embedded += 1
            head = subprocess.run(["git","rev-parse","HEAD"], cwd=self.root, text=True, capture_output=True).stdout.strip()
            con.execute("INSERT OR REPLACE INTO repositories VALUES(1,?,?,?)", (str(self.root),head,now))
            stats.files = con.execute("SELECT count(*) FROM files").fetchone()[0]
            stats.chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
            if not stats.dimensions:
                row = con.execute("SELECT dimensions FROM chunks LIMIT 1").fetchone(); stats.dimensions = row[0] if row else 0
        return stats

    def retrieve(self, query: str, vector: list[float], paths: set[str], limit: int = 6) -> list[dict]:
        qids = identifiers(query); scored = []
        with self.connect() as con:
            for row in con.execute("SELECT * FROM chunks WHERE embedding IS NOT NULL"):
                emb = deserialize_vector(row["embedding"], row["dimensions"])
                lexical = len(qids & identifiers(row["text"])) / max(1, len(qids))
                affinity = .12 if any(Path(row["path"]).parent == Path(p).parent for p in paths) else 0
                test_affinity = .12 if (("test" in row["path"].lower()) != any("test" in p.lower() for p in paths)) else 0
                score = .68*cosine(vector,emb) + .2*lexical + affinity + test_affinity
                scored.append((score, dict(row)))
        return [r for _, r in sorted(scored, key=lambda x:x[0], reverse=True)[:limit]]
