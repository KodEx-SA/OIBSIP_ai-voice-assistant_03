"""
api.py — Clare's tool functions
Includes temperature control + memory tools (remember / recall / forget).
"""

import enum
import time
import logging
from livekit.agents import function_tool, RunContext
from memory import ClareMemory

logger = logging.getLogger("clare.api")
logger.setLevel(logging.INFO)


class TemperatureZone(enum.Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"


class AssistantAgentFunction:
    def __init__(self, memory: ClareMemory) -> None:
        super().__init__()
        self.memory = memory

        self._temperature_zones = {
            TemperatureZone.LIVING_ROOM: 25,
            TemperatureZone.BEDROOM: 22,
            TemperatureZone.KITCHEN: 20,
            TemperatureZone.BATHROOM: 30,
            TemperatureZone.OFFICE: 21,
        }

    # ------------------------------------------------------------------ #
    #  Temperature tool                                                  #
    # ------------------------------------------------------------------ #

    @function_tool()
    async def get_temperature(self, context: RunContext, zone: TemperatureZone):
        """Get the current temperature in a specific zone or room.

        Args:
            zone: The specific zone/room to check temperature for
        """
        start = time.monotonic()
        try:
            temp      = self._temperature_zones[zone]
            zone_name = zone.value.replace("_", " ").title()
            message   = f"The temperature in the {zone_name} is {temp}°C."

            logger.info("Temperature check — zone: %s, temp: %s°C", zone.value, temp)

            result = {
                "zone": zone.value,
                "temperature_celsius": temp,
                "message": message,
            }

            await self.memory.log_tool_execution(
                tool_name = "get_temperature",
                arguments = {"zone": zone.value},
                result = result,
                status = "success",
                duration_ms = int((time.monotonic() - start) * 1000),
            )
            return result

        except KeyError:
            error_msg = f"Sorry, I don't have temperature data for {zone.value.replace('_', ' ')}."
            await self.memory.log_tool_execution(
                tool_name = "get_temperature",
                arguments = {"zone": zone.value},
                result = {"error": error_msg},
                status = "error",
                duration_ms = int((time.monotonic() - start) * 1000),
            )
            return {"error": error_msg}

    # ------------------------------------------------------------------ #
    #  Memory tools                                                      #
    # ------------------------------------------------------------------ #

    @function_tool()
    async def remember(self, context: RunContext, key: str, information: str):
        """Store a piece of information in long-term memory so you can recall it in future conversations.

        Args:
            key: A short snake_case identifier for what you are remembering
                 (e.g. "user_name", "preferred_temperature_unit", "favourite_room")
            information: The information to store
        """
        start = time.monotonic()
        await self.memory.save_memory(key, information)
        result = {"status": "remembered", "key": key, "information": information}

        await self.memory.log_tool_execution(
            tool_name = "remember",
            arguments = {"key": key, "information": information},
            result = result,
            status = "success",
            duration_ms= int((time.monotonic() - start) * 1000),
        )
        logger.info("Remembered — key=%s", key)
        return result

    @function_tool()
    async def recall(self, context: RunContext, key: str):
        """Retrieve a specific piece of information from long-term memory.

        Args:
            key: The identifier of the memory to retrieve
        """
        start   = time.monotonic()
        content = await self.memory.get_memory(key)

        if content:
            result = {"key": key, "content": content, "found": True}
        else:
            result = {"key": key, "found": False, "message": f"No memory stored for '{key}'."}

        await self.memory.log_tool_execution(
            tool_name = "recall",
            arguments = {"key": key},
            result = result,
            status = "success",
            duration_ms= int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def forget(self, context: RunContext, key: str):
        """Delete a specific memory permanently.

        Args:
            key: The identifier of the memory to delete
        """
        start   = time.monotonic()
        deleted = await self.memory.delete_memory(key)
        result  = {"key": key, "deleted": deleted}

        await self.memory.log_tool_execution(
            tool_name = "forget",
            arguments = {"key": key},
            result = result,
            status = "success",
            duration_ms= int((time.monotonic() - start) * 1000),
        )
        return result

    @function_tool()
    async def list_memories(self, context: RunContext):
        """List all information stored in long-term memory."""
        start    = time.monotonic()
        memories = await self.memory.get_all_memories()

        result = {
            "count":    len(memories),
            "memories": [{"key": m["key"], "content": m["content"]} for m in memories],
        }

        await self.memory.log_tool_execution(
            tool_name = "list_memories",
            arguments = {},
            result = result,
            status = "success",
            duration_ms= int((time.monotonic() - start) * 1000),
        )
        return result