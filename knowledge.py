"""
knowledge.py - Clare's knowledge base
Uses Supabase PostgreSQL full-text search instead of a local vector store.
No local models, no heavy dependencies, no RAM overhead.
"""

import os
import logging
from datetime import datetime, timezone
from supabase import create_client, Client

logger = logging.getLogger("clare.knowledge")
logger.setLevel(logging.INFO)

MAX_CHUNK_WORDS = 300
CHUNK_OVERLAP = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeBase:
    """
    Cloud knowledge store for Clare using Supabase full-text search.
    No local ML models - everything runs in PostgreSQL.
    """

    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set.")
        self.client: Client = create_client(url, key)

    async def initialise(self) -> None:
        result = (
            self.client.table("knowledge")
            .select("id", count="exact", head=True)
            .execute()
        )
        count = result.count or 0
        logger.info(
            "KnowledgeBase initialised - Supabase full-text search, %d documents stored",
            count,
        )

    async def store(self, content: str, source: str, topic: str) -> int:
        if not content.strip():
            return 0
        chunks = self._chunk_text(content)
        if not chunks:
            return 0
        rows = [
            {
                "topic": topic,
                "content": chunk,
                "source": source,
                "chunk_idx": i,
                "stored_at": _now(),
            }
            for i, chunk in enumerate(chunks)
        ]
        self.client.table("knowledge").insert(rows).execute()
        logger.info(
            "Stored %d chunks - topic: %s, source: %s", len(chunks), topic, source
        )
        return len(chunks)

    async def query(self, question: str, n_results: int = 5) -> list[dict]:
        words = [w.strip("?.,!") for w in question.split() if len(w) > 2]
        keyword = max(words, key=len) if words else ""
        if not keyword:
            return []
        result = (
            self.client.table("knowledge")
            .select("content, source, topic")
            .ilike("content", f"%{keyword}%")
            .limit(n_results)
            .execute()
        )
        rows = result.data or []
        logger.info("Knowledge query - question: %s, results: %d", question, len(rows))
        return [
            {
                "content": r.get("content", ""),
                "source": r.get("source", ""),
                "topic": r.get("topic", ""),
            }
            for r in rows
        ]

    async def list_topics(self) -> list[str]:
        result = self.client.table("knowledge").select("topic").execute()
        topics = {r["topic"] for r in (result.data or [])}
        return sorted(topics)

    async def count(self) -> int:
        result = (
            self.client.table("knowledge")
            .select("id", count="exact", head=True)
            .execute()
        )
        return result.count or 0

    def _chunk_text(self, text: str) -> list[str]:
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i : i + MAX_CHUNK_WORDS])
            if chunk.strip():
                chunks.append(chunk)
            i += MAX_CHUNK_WORDS - CHUNK_OVERLAP
        return chunks
