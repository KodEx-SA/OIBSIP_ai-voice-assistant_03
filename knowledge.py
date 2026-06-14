"""
knowledge.py - Clare's long-term knowledge base
Uses ChromaDB (local vector store) with sentence-transformers embeddings.
Allows Clare to store what she learns from the web and recall it semantically.
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from functools import partial

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger("clare.knowledge")
logger.setLevel(logging.INFO)

PERSIST_DIR    = os.getenv("KNOWLEDGE_STORE_DIR", "./knowledge_store")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # ~90MB, downloads once on first run
COLLECTION_NAME = "clare_knowledge"


class KnowledgeBase:
    """
    Vector knowledge store for Clare.

    Stores chunks of learned text with metadata (source URL, topic, timestamp).
    Supports semantic search — finds relevant content by meaning, not just keywords.

    Usage:
        kb = KnowledgeBase()
        await kb.initialise()
        await kb.store("Python is a programming language...", source="https://...", topic="python")
        results = await kb.query("what is python used for")
    """

    def __init__(self):
        self._client     = None
        self._collection = None
        self._embed_fn   = None

    async def initialise(self) -> None:
        """Set up the Chroma client and collection. Call once at startup."""
        loop = asyncio.get_event_loop()

        # Chroma and sentence-transformers are synchronous — run in thread pool
        await loop.run_in_executor(None, self._setup)
        logger.info(
            "KnowledgeBase initialised — store: %s, documents: %d",
            PERSIST_DIR,
            self._collection.count(),
        )

    def _setup(self):
        """Synchronous setup — runs in thread pool."""
        os.makedirs(PERSIST_DIR, exist_ok=True)

        self._embed_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )

        self._client = chromadb.PersistentClient(path=PERSIST_DIR)

        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------ #
    #  Store                                                               #
    # ------------------------------------------------------------------ #

    async def store(
        self,
        content:  str,
        source:   str,
        topic:    str,
        chunk_size: int = 500,
    ) -> int:
        """
        Store content in the knowledge base.
        Long content is chunked so it fits within embedding limits.

        Returns the number of chunks stored.
        """
        if not content.strip():
            return 0

        chunks = self._chunk_text(content, chunk_size)
        if not chunks:
            return 0

        now      = datetime.now(timezone.utc).isoformat()
        ids      = [f"{topic}_{i}_{now}" for i in range(len(chunks))]
        metas    = [
            {
                "source":    source,
                "topic":     topic,
                "chunk_idx": i,
                "stored_at": now,
            }
            for i in range(len(chunks))
        ]

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self._collection.add, documents=chunks, ids=ids, metadatas=metas),
        )

        logger.info("Stored %d chunks — topic: %s, source: %s", len(chunks), topic, source)
        return len(chunks)

    # ------------------------------------------------------------------ #
    #  Query                                                               #
    # ------------------------------------------------------------------ #

    async def query(self, question: str, n_results: int = 5) -> list[dict]:
        """
        Semantic search: find content most relevant to the question.

        Returns a list of dicts with keys: content, source, topic, distance
        """
        loop    = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            partial(
                self._collection.query,
                query_texts=[question],
                n_results=min(n_results, max(self._collection.count(), 1)),
            ),
        )

        output = []
        docs       = results.get("documents", [[]])[0]
        metas      = results.get("metadatas", [[]])[0]
        distances  = results.get("distances",  [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            output.append({
                "content":  doc,
                "source":   meta.get("source", ""),
                "topic":    meta.get("topic", ""),
                "distance": round(dist, 4),
            })

        logger.info("Knowledge query — question: %s, results: %d", question, len(output))
        return output

    # ------------------------------------------------------------------ #
    #  Utilities                                                           #
    # ------------------------------------------------------------------ #

    async def list_topics(self) -> list[str]:
        """Return all unique topics stored in the knowledge base."""
        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(self._collection.get, include=["metadatas"]),
        )
        topics = {m.get("topic", "") for m in result.get("metadatas", [])}
        return sorted(t for t in topics if t)

    async def count(self) -> int:
        """Return total number of stored chunks."""
        return self._collection.count()

    def _chunk_text(self, text: str, chunk_size: int) -> list[str]:
        """Split text into overlapping chunks by word count."""
        words    = text.split()
        overlap  = chunk_size // 5   # 20% overlap between chunks
        chunks   = []
        i        = 0

        while i < len(words):
            chunk = " ".join(words[i : i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
            i += chunk_size - overlap

        return chunks
