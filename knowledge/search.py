"""Local hybrid search over markdown knowledge. No paid embedding API."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]{2,}")
_CORPUS = Path(__file__).resolve().parent / "corpus"


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def _corpus_stamp() -> tuple:
    if not _CORPUS.is_dir():
        return ()
    return tuple((p.name, int(p.stat().st_mtime)) for p in sorted(_CORPUS.glob("*.md")))


@lru_cache(maxsize=8)
def _documents(stamp: tuple) -> list[dict[str, Any]]:
    del stamp
    docs: list[dict[str, Any]] = []
    if not _CORPUS.is_dir():
        return docs
    for path in sorted(_CORPUS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        chunks = _chunk(text, path.stem)
        docs.extend(chunks)
    return docs


def _chunk(text: str, source: str) -> list[dict[str, Any]]:
    parts = re.split(r"\n##\s+", text)
    out: list[dict[str, Any]] = []
    for i, part in enumerate(parts):
        body = part.strip()
        if len(body) < 40:
            continue
        title = body.splitlines()[0].lstrip("# ").strip()
        out.append(
            {
                "id": f"{source}:{i}",
                "source": source,
                "title": title[:120],
                "text": body,
                "tokens": _tokenize(body),
            }
        )
    return out


def _tfidf_vector(tokens: list[str], df: dict[str, int], n_docs: int) -> dict[str, float]:
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec: dict[str, float] = {}
    length = max(len(tokens), 1)
    for t, c in tf.items():
        idf = math.log((n_docs + 1) / (1 + df.get(t, 0))) + 1.0
        vec[t] = (c / length) * idf
    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    num = sum(a[k] * b[k] for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return num / (na * nb)


def search_knowledge(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    q = (query or "").strip()
    docs = _documents(_corpus_stamp())
    if not q or not docs:
        return []
    df: dict[str, int] = {}
    for doc in docs:
        for t in set(doc["tokens"]):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    qvec = _tfidf_vector(_tokenize(q), df, n)
    scored: list[tuple[float, dict[str, Any]]] = []
    for doc in docs:
        dvec = _tfidf_vector(doc["tokens"], df, n)
        lexical = sum(1 for t in _tokenize(q) if t in doc["tokens"])
        score = 0.75 * _cosine(qvec, dvec) + 0.25 * (lexical / max(len(_tokenize(q)), 1))
        if score <= 0:
            continue
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, doc in scored[: max(1, min(int(limit), 8))]:
        hits.append(
            {
                "id": doc["id"],
                "source": doc["source"],
                "title": doc["title"],
                "score": round(float(score), 4),
                "excerpt": doc["text"][:700],
            }
        )
    return hits
