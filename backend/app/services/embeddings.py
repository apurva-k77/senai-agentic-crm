"""Lightweight embeddings for RAG (no GPU required)."""
import hashlib
import math
import re

from app.core.config import settings


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def embed_text(text: str, dims: int | None = None) -> list[float]:
    dims = dims or settings.vector_dims
    vec = [0.0] * dims
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % dims
        sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
        vec[idx] += sign * (1.0 + math.log1p(tokens.count(tok)))
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
