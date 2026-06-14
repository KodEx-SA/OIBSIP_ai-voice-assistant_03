"""
api.py - Clare's tool functions
Phase 1: temperature control + memory tools
Phase 3: web search + page reading + knowledge base
"""

import enum
import time
import logging
from livekit.agents import function_tool, RunContext
from memory import ClareMemory
from web_search import WebSearcher
from knowledge import KnowledgeBase

logger = logging.getLogger("clare.api")
logger.setLevel(logging.INFO)


class TemperatureZone(enum.Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"


class AssistantAgentFunction:
    def __init__(self, memory: ClareMemory, searcher: WebSearcher, knowledge: KnowledgeBase) -> None:
        super().__init__()
        self.memory = memory
        self.searcher = searcher
        self.knowledge = knowledge

        self._temperature_zones = {
            TemperatureZone.LIVING_ROOM: 25,
            TemperatureZone.BEDROOM: 22,
            TemperatureZone.KITCHEN: 20,
            TemperatureZone.BATHROOM: 30,
            TemperatureZone.OFFICE: 21,
        }

    # ================================================================== #
    #  Temperature                                                       #
    # ================================================================== #

    @function_tool()
    async def get_temperature(self, context: RunContext, zone: TemperatureZone):
        """Get the current temperature in a specific zone or room.

        Args:
            zone: The specific zone/room to check temperature for
        """
        start = time.monotonic()
        try:
            temp = self._temperature_zones[zone]
            zone_name = zone.value.replace("_", " ").title()
            message = f"The temperature in the {zone_name} is {temp}°C."
            result = {
                "zone": zone.value,
                "temperature_celsius": temp,
                "message": message,
            }
            status = "success"
        except KeyError:
            error_msg = f"No temperature data for {zone.value.replace('_', ' ')}."
            result = {"error": error_msg}
            status = "error"

        await self.memory.log_tool_execution(
            tool_name="get_temperature",
            arguments={"zone": zone.value},
            result=result,
            status=status,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    # ================================================================== #
    #  Memory tools                                                      #
    # ================================================================== #

    @function_tool()
    async def remember(self, context: RunContext, key: str, information: str):
        """Store a piece of information in long-term memory so you can recall it in future conversations.

        Args:
            key: A short snake_case identifier (e.g. "user_name", "favourite_room")
            information: The information to store
        """
        start = time.monotonic()
        await self.memory.save_memory(key, information)
        result = {"status": "remembered", "key": key, "information": information}
        await self.memory.log_tool_execution(
            tool_name="remember",
            arguments={"key": key, "information": information},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def recall(self, context: RunContext, key: str):
        """Retrieve a specific piece of information from long-term memory.

        Args:
            key: The identifier of the memory to retrieve
        """
        start = time.monotonic()
        content = await self.memory.get_memory(key)
        result = (
            {"key": key, "content": content, "found": True}
            if content
            else {
                "key": key,
                "found": False,
                "message": f"No memory stored for '{key}'.",
            }
        )
        await self.memory.log_tool_execution(
            tool_name="recall",
            arguments={"key": key},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def forget(self, context: RunContext, key: str):
        """Delete a specific memory permanently.

        Args:
            key: The identifier of the memory to delete
        """
        start = time.monotonic()
        deleted = await self.memory.delete_memory(key)
        result = {"key": key, "deleted": deleted}

        await self.memory.log_tool_execution(
            tool_name="forget",
            arguments={"key": key},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def list_memories(self, context: RunContext):
        """List all information stored in long-term memory."""
        start = time.monotonic()
        memories = await self.memory.get_all_memories()
        result = {
            "count": len(memories),
            "memories": [{"key": m["key"], "content": m["content"]} for m in memories],
        }

        await self.memory.log_tool_execution(
            tool_name="list_memories",
            arguments={},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    # ================================================================== #
    #  Web intelligence tools (Phase 3)                                  #
    # ================================================================== #

    @function_tool()
    async def web_search(self, context: RunContext, query: str):
        """Search the web for current information you don't know or that may have changed.
        Use this proactively when asked about news, current events, prices, people, or
        anything you are uncertain about. Returns titles, URLs, and snippets.

        Args:
            query: The search query — be specific for better results
        """
        start = time.monotonic()
        results = await self.searcher.search(query, count=5)

        if not results:
            result = {"query": query, "found": False, "message": "No results found."}
            status = "error"
        else:
            result = {
                "query": query,
                "found": True,
                "count": len(results),
                "results": results,
            }
            status = "success"

        await self.memory.log_tool_execution(
            tool_name="web_search",
            arguments={"query": query},
            result={"query": query, "count": len(results), "status": status},
            status=status,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        logger.info("Web search — query: %s, results: %d", query, len(results))
        return result

    @function_tool()
    async def read_webpage(self, context: RunContext, url: str):
        """Read and extract the text content from a specific webpage URL.
        Use after web_search to get full details from a result.

        Args:
            url: The full URL of the page to read (must start with https://)
        """
        start = time.monotonic()
        content = await self.searcher.read_page(url)
        result = {"url": url, "content": content, "chars": len(content)}

        await self.memory.log_tool_execution(
            tool_name="read_webpage",
            arguments={"url": url},
            result={"url": url, "chars": len(content)},
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def learn_about(self, context: RunContext, topic: str):
        """Search the web for a topic, read the top results, and store what
        you learn in your permanent knowledge base for future recall.
        Use this when asked to learn or research something.

        Args:
            topic: The topic to search, read about, and learn
        """
        start = time.monotonic()

        # Search
        results = await self.searcher.search(topic, count=3)
        if not results:
            return {
                "topic": topic,
                "learned": False,
                "message": "No search results found.",
            }

        # Read and store top results
        chunks_stored = 0
        sources_read = []

        for item in results[:3]:
            url = item.get("url", "")
            snippet = item.get("snippet", "")

            # Always store the snippet — fast and reliable
            if snippet:
                stored = await self.knowledge.store(
                    content=snippet, source=url, topic=topic
                )
                chunks_stored += stored

            # Try to read the full page too
            if url:
                page_content = await self.searcher.read_page(url)
                if page_content and not page_content.startswith("["):
                    stored = await self.knowledge.store(
                        content=page_content, source=url, topic=topic
                    )
                    chunks_stored += stored
                    sources_read.append(url)

        result = {
            "topic": topic,
            "learned": True,
            "sources_read": len(sources_read),
            "chunks_stored": chunks_stored,
            "sources": sources_read,
        }

        await self.memory.log_tool_execution(
            tool_name="learn_about",
            arguments={"topic": topic},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        logger.info(
            "Learned about '%s' — %d chunks from %d sources",
            topic,
            chunks_stored,
            len(sources_read),
        )
        return result

    @function_tool()
    async def recall_knowledge(self, context: RunContext, question: str):
        """Search your learned knowledge base semantically for information
        relevant to a question. Use this before web_search to check if you
        already know something from a previous learning session.

        Args:
            question: The question or topic to search your knowledge base for
        """
        start = time.monotonic()
        results = await self.knowledge.query(question, n_results=5)

        if not results:
            result = {
                "question": question,
                "found": False,
                "message": "Nothing in knowledge base yet.",
            }
        else:
            result = {
                "question": question,
                "found": True,
                "count": len(results),
                "results": [
                    {
                        "content": r["content"][:500],  # truncate for voice context
                        "source": r["source"],
                        "topic": r["topic"],
                        "distance": r["distance"],
                    }
                    for r in results
                ],
            }

        await self.memory.log_tool_execution(
            tool_name="recall_knowledge",
            arguments={"question": question},
            result={
                "question": question,
                "found": result.get("found"),
                "count": result.get("count", 0),
            },
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def list_knowledge_topics(self, context: RunContext):
        """List all topics Clare has learned about and stored in her knowledge base."""
        start = time.monotonic()
        topics = await self.knowledge.list_topics()
        count = await self.knowledge.count()
        result = {"topics": topics, "total_topics": len(topics), "total_chunks": count}

        await self.memory.log_tool_execution(
            tool_name="list_knowledge_topics",
            arguments={},
            result=result,
            status="success",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        return result
