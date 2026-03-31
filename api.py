import enum
from livekit.agents import function_tool, RunContext
import logging

logger = logging.getLogger("temperature-control")
logger.setLevel(logging.INFO)


class TemperatureZone(enum.Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    OFFICE = "office"


class AssistantAgentFunction:
    def __init__(self) -> None:
        super().__init__()

        self._temperature_zones = {
            TemperatureZone.LIVING_ROOM: 25,
            TemperatureZone.BEDROOM: 22,
            TemperatureZone.KITCHEN: 20,
            TemperatureZone.BATHROOM: 30,
            TemperatureZone.OFFICE: 21,
        }

    @function_tool()
    async def get_temperature(self, context: RunContext, zone: TemperatureZone):
        """Get the current temperature in a specific zone or room.

        Args:
            zone: The specific zone/room to check temperature for

        Returns:
            A dictionary containing temperature information
        """
        try:
            temp = self._temperature_zones[zone]
            zone_name = zone.value.replace('_', ' ').title()
            message = f"The temperature in the {zone_name} is {temp}°C."

            logger.info("Temperature check - zone: %s, temp: %s°C", zone.value, temp)

            return {
                "zone": zone.value,
                "temperature_celsius": temp,
                "message": message,
            }

        except KeyError:
            error_msg = f"Sorry, I don't have temperature data for {zone.value.replace('_', ' ')}."
            return {"error": error_msg}