"""Retrieval: a bi-encoder over a Chroma index, and a cross-encoder to rerank.

Models are pinned by revision and loaded as safetensors only, never pickle
(THREAT-MODEL.md, LLM03); Chroma's telemetry is off (LLM02).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from .corpus import ROOT, Passage

EMBED = ("BAAI/bge-small-en-v1.5", "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a")
RERANK = ("cross-encoder/ms-marco-MiniLM-L-6-v2", "233902d25c440f23af6f7d6e94d2946bac0bee0a")
# A larger reranker, measured against RERANK (evaluate.py); Apache-2.0.
RERANK_BGE = ("BAAI/bge-reranker-v2-m3", "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
# bge is trained to read a query with this in front of it, and a passage
# without.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
INDEX = ROOT / "data" / "index"


@cache
def embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED[0], revision=EMBED[1], model_kwargs={"use_safetensors": True})


@cache
def reranker(model: tuple[str, str] = RERANK):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model[0], revision=model[1], max_length=512, model_kwargs={"use_safetensors": True})


def _collection(pin: str):
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=str(INDEX), settings=Settings(anonymized_telemetry=False))
    # The default search breadth (10) can miss neighbors when 20 are asked
    # for; at this corpus's size a wide search costs nothing.
    return client.get_or_create_collection(
        f"mobium-{pin[:7]}-bge-small",
        metadata={"hnsw:space": "cosine", "hnsw:construction_ef": 200, "hnsw:search_ef": 100},
    )


class Index:
    def __init__(self, passages: list[Passage], pin: str):
        self.by_id = {p.id: p for p in passages}
        self.col = _collection(pin)
        if self.col.count() != len(passages):
            ids = [p.id for p in passages]
            vecs = embedder().encode([p.text for p in passages], normalize_embeddings=True, batch_size=32)
            existing = self.col.get()["ids"]
            if existing:
                self.col.delete(ids=existing)
            for i in range(0, len(ids), 500):
                self.col.add(ids=ids[i:i + 500], embeddings=vecs[i:i + 500].tolist())

    def search(self, question: str, k: int) -> list[tuple[str, float]]:
        """The k nearest passages and their cosine similarity."""
        q = embedder().encode([QUERY_PREFIX + question], normalize_embeddings=True)[0]
        res = self.col.query(query_embeddings=[q.tolist()], n_results=k)
        return [(pid, 1 - d) for pid, d in zip(res["ids"][0], res["distances"][0])]

    def scores(self, question: str, candidates: list[str], model: tuple[str, str] = RERANK,
               with_path: bool = True) -> dict[str, float]:
        """The reranker's score for each candidate, read with the passage's
        file in front of its text: a section's heading does not say it is
        the README's or the roadmap's, and with the file named MRR rose by
        0.023 (95% interval +0.005 to +0.045) at 7b590a4. `with_path` False
        is the reranker as it was, for comparison."""
        text = (lambda c: f"{self.by_id[c].path}\n{self.by_id[c].text}") if with_path else (lambda c: self.by_id[c].text)
        return dict(zip(candidates, (float(s) for s in reranker(model).predict([(question, text(c)) for c in candidates]))))

    def rerank(self, question: str, candidates: list[str], k: int, model: tuple[str, str] = RERANK,
               with_path: bool = True) -> list[tuple[str, float]]:
        scores = self.scores(question, candidates, model, with_path)
        return sorted(scores.items(), key=lambda x: -x[1])[:k]


def path() -> Path:
    return INDEX
