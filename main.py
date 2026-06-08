"""
main.py - Clare voice assistant entrypoint
Fixes:
  - wait_for_participant() added (was the cause of no voice I/O)
  - Memory integrated: sessions, conversation history, long-term facts
"""

import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents import Agent, AgentSession, RoomInputOptions
import livekit.plugins.openai as openai
import livekit.plugins.silero as silero

from memory import ClareMemory
from api import AssistantAgentFunction

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clare.main")


async def entrypoint(ctx: JobContext):
    # ------------------------------------------------------------------ #
    #  1. Connect to the LiveKit room                                      #
    # ------------------------------------------------------------------ #
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # ------------------------------------------------------------------ #
    #  2. Wait for a user to actually join — THIS was the voice bug fix    #
    #     Without this, Clare has no audio track to read from or write to  #
    # ------------------------------------------------------------------ #
    logger.info("Waiting for participant to join room: %s", ctx.room.name)
    participant = await ctx.wait_for_participant()
    logger.info("Participant joined: %s", participant.identity)

    # ------------------------------------------------------------------ #
    #  3. Initialise memory and start a session                            #
    # ------------------------------------------------------------------ #
    memory = ClareMemory()
    await memory.start_session(room_id=ctx.room.name)

    # Load any stored long-term memories to inject into Clare's prompt
    memory_context = await memory.build_memory_context()

    # ------------------------------------------------------------------ #
    #  4. Build Clare's system instructions (with memory context injected) #
    # ------------------------------------------------------------------ #
    base_instructions = (
        "You are Clare, a voice assistant created by Ashley (KodEx-SA). "
        "Your interface with users is voice only — keep responses short and natural. "
        "Avoid complex punctuation, long sentences, or lists. Speak conversationally. "
        "You can check temperatures in various zones. "
        "You have long-term memory: use 'remember' to store facts the user tells you, "
        "'recall' to retrieve them, 'forget' to remove them, and 'list_memories' to see all. "
        "Proactively remember useful things like the user's name, preferences, or anything "
        "they'd expect you to know next time."
    )

    instructions = (
        f"{base_instructions}\n\n{memory_context}"
        if memory_context
        else base_instructions
    )

    # ------------------------------------------------------------------ #
    #  5. Wire up tools and agent                                          #
    # ------------------------------------------------------------------ #
    agent_function = AssistantAgentFunction(memory=memory)

    agent = Agent(
        instructions=instructions,
        tools=[
            agent_function.get_temperature,
            agent_function.remember,
            agent_function.recall,
            agent_function.forget,
            agent_function.list_memories,
        ],
    )

    # ------------------------------------------------------------------ #
    #  6. Build the voice pipeline                                         #
    # ------------------------------------------------------------------ #
    session = AgentSession(
        stt=openai.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(),
        vad=silero.VAD.load(),
    )

    # ------------------------------------------------------------------ #
    #  7. Hook into session events to save conversation to memory          #
    # ------------------------------------------------------------------ #
    @session.on("user_input_transcribed")
    def on_user_spoke(event):
        """Save every user utterance to the session history."""
        if event.is_final and event.transcript.strip():
            asyncio.ensure_future(
                memory.save_message("user", event.transcript)
            )

    @session.on("agent_speech_committed")
    def on_agent_spoke(event):
        """Save every Clare response to the session history."""
        if hasattr(event, "transcript") and event.transcript.strip():
            asyncio.ensure_future(
                memory.save_message("assistant", event.transcript)
            )

    # ------------------------------------------------------------------ #
    #  8. Start the session (pass participant so audio tracks are linked)  #
    # ------------------------------------------------------------------ #
    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(participant_identity=participant.identity),
    )

    # Give the audio pipeline a moment to initialise
    await asyncio.sleep(1)

    # Clare's greeting - checks memory for a known name
    user_name = await memory.get_memory("user_name")
    greeting  = f"Hi {user_name}, I'm Clare. How may I help you?" if user_name else "Hi, I'm Clare. How may I help you?"
    await session.say(greeting, allow_interruptions=True)

    # ------------------------------------------------------------------ #
    #  9. Keep alive and clean up when the room closes                    #
    # ------------------------------------------------------------------ #
    try:
        await ctx.room.wait_for_disconnect()
    finally:
        await memory.end_session()
        logger.info("Session ended cleanly.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))