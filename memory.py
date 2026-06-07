"""
memory.py — Clare's cloud memory layer
Handles sessions, conversation history, long-term memories, and tool execution logs.
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any
from supabase import create_client, Client

logger = logging.getLogger("clare.memory")
logger.setLevel(logging.INFO)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClareMemory:
    """
    Cloud-backed memory for Clare.

    Usage:
        memory = ClareMemory()
        await memory.start_session(room_id="room-xyz")
        await memory.save_message("user", "What is the temperature?")
        await memory.save_message("assistant", "It is 22°C in the bedroom.")
        await memory.save_memory("user_name", "Ashley")
        name = await memory.get_memory("user_name")
        await memory.end_session()
    """

    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_KEY must be set in your .env file."
            )

        self.client: Client = create_client(url, key)
        self.session_id: str | None = None
        self.room_id: str | None = None
        logger.info("ClareMemory initialised — Supabase connected.")

    # ------------------------------------------------------------------ #
    #  Session management                                                #
    # ------------------------------------------------------------------ #

    async def start_session(self, room_id: str) -> str:
        """Create a new session row and store its ID internally."""
        self.room_id = room_id
        result = (
            self.client.table("sessions")
            .insert({"room_id": room_id, "started_at": _now()})
            .execute()
        )
        self.session_id = result.data[0]["id"]
        logger.info("Session started — id=%s  room=%s", self.session_id, room_id)
        return self.session_id

    async def end_session(self) -> None:
        """Mark the current session as ended."""
        if not self.session_id:
            return
        self.client.table("sessions").update({"ended_at": _now()}).eq(
            "id", self.session_id
        ).execute()
        logger.info("Session ended — id=%s", self.session_id)

    # ------------------------------------------------------------------ #
    #  Conversation history                                              #
    # ------------------------------------------------------------------ #

    async def save_message(self, role: str, content: str) -> None:
        """Persist a single message to the current session."""
        if not self.session_id:
            logger.warning("save_message called before start_session — skipping.")
            return
        self.client.table("messages").insert(
            {
                "session_id": self.session_id,
                "role": role,
                "content": content,
                "created_at": _now(),
            }
        ).execute()

    async def get_session_history(self, limit: int = 30) -> list[dict]:
        """Return the most recent messages from the current session, oldest first."""
        if not self.session_id:
            return []
        result = (
            self.client.table("messages")
            .select("role, content, created_at")
            .eq("session_id", self.session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data

    async def get_cross_session_history(self, limit: int = 50) -> list[dict]:
        """Return recent messages across ALL sessions — Clare's full conversation memory."""
        result = (
            self.client.table("messages")
            .select("role, content, created_at")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data

    # ------------------------------------------------------------------ #
    #  Long-term memory (key/value facts)                                #
    # ------------------------------------------------------------------ #

    async def save_memory(
        self, key: str, content: str, source: str = "conversation"
    ) -> None:
        """
        Upsert a long-term memory by key.
        If the key already exists it's updated; otherwise it's created.
        """
        existing = self.client.table("memories").select("id").eq("key", key).execute()

        if existing.data:
            self.client.table("memories").update(
                {"content": content, "source": source}
            ).eq("key", key).execute()
            logger.info("Memory updated — key=%s", key)
        else:
            self.client.table("memories").insert(
                {"key": key, "content": content, "source": source}
            ).execute()
            logger.info("Memory created — key=%s", key)

    async def get_memory(self, key: str) -> str | None:
        """Retrieve a specific memory by its key. Returns None if not found."""
        result = (
            self.client.table("memories").select("content").eq("key", key).execute()
        )
        if result.data:
            return result.data[0]["content"]
        return None

    async def delete_memory(self, key: str) -> bool:
        """Delete a memory by key. Returns True if it existed and was removed."""
        existing = self.client.table("memories").select("id").eq("key", key).execute()
        if not existing.data:
            return False
        self.client.table("memories").delete().eq("key", key).execute()
        logger.info("Memory deleted — key=%s", key)
        return True

    async def get_all_memories(self) -> list[dict]:
        """Return all stored long-term memories, newest first."""
        result = (
            self.client.table("memories")
            .select("key, content, source, updated_at")
            .order("updated_at", desc=True)
            .execute()
        )
        return result.data

    async def build_memory_context(self) -> str:
        """
        Build a compact string of all memories to inject into Clare's system prompt.
        Returns empty string if no memories exist.
        """
        memories = await self.get_all_memories()
        if not memories:
            return ""
        lines = ["[Clare's long-term memories]"]
        for m in memories:
            lines.append(f"  {m['key']}: {m['content']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Tool execution logging                                            #
    # ------------------------------------------------------------------ #

    async def log_tool_execution(
        self,
        tool_name: str,
        arguments: dict,
        result: Any,
        status: str = "success",
        duration_ms: int | None = None,
    ) -> None:
        """Log a tool call for the mission control dashboard (Phase 2)."""
        self.client.table("tool_executions").insert(
            {
                "session_id": self.session_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "result": (
                    result if isinstance(result, dict) else {"value": str(result)}
                ),
                "status": status,
                "executed_at": _now(),
                "duration_ms": duration_ms,
            }
        ).execute()
