"""Near-dup embeddings. Prefer MiniLM; hashing fallback keeps Render RAM low."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Sequence

log = logging.getLogger(__name__)

DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+", re.I)

_minilm = None
_minilm_failed = False


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _hash_embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    tokens = _TOKEN.findall((text or "").lower())
    if not tokens:
        return vec
    for tok in tokens:
        h = hashlib.blake2b(tok.encode(), digest_size=4).digest()
        idx = int.from_bytes(h, "little") % DIM
        sign = 1.0 if h[0] % 2 == 0 else -1.0
        vec[idx] += sign
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def minilm_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except Exception:
        return False


def _load_minilm(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_batch(texts: list[str], *, model_name: str, use_minilm: bool) -> list[list[float]]:
    global _minilm_failed
    if use_minilm and not _minilm_failed:
        try:
            model = _load_minilm(model_name)
            vectors = model.encode(
                texts,
                batch_size=min(8, max(1, len(texts))),
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return [row.astype(float).tolist() for row in vectors]
        except Exception as exc:
            _minilm_failed = True
            log.warning("MiniLM unavailable (%s); using hashing embeddings", exc)
    return [_hash_embed(t) for t in texts]


def embed_one(text: str, *, model_name: str, use_minilm: bool) -> list[float]:
    return embed_batch([text], model_name=model_name, use_minilm=use_minilm)[0]
