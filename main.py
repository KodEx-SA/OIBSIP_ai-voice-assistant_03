"""
main.py - Clare voice assistant entrypoint
Pipeline: Deepgram STT -> Groq LLM -> Cartesia TTS -> Silero VAD
All free-tier providers, no OpenAI required.
"""

import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents import Agent, AgentSession, RoomInputOptions
import livekit.plugins.groq as groq  # =============== used for Groq via .with_groq() ===============
import livekit.plugins.deepgram as deepgram
import livekit.plugins.cartesia as cartesia
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
    #  1. Connect to the LiveKit room                                    #
    # ------------------------------------------------------------------ #
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # ------------------------------------------------------------------ #
    #  2. Wait for participant - graceful exit if they leave too early   #
    # ------------------------------------------------------------------ #
    logger.info("Waiting for participant to join room: %s", ctx.room.name)
    try:
        participant = await ctx.wait_for_participant()
        logger.info("Participant joined: %s", participant.identity)
    except RuntimeError as e:
        logger.warning("Room closed before participant joined — %s", e)
        return

    # ------------------------------------------------------------------ #
    #  3. Initialise memory                                              #
    # ------------------------------------------------------------------ #
    memory = ClareMemory()
    await memory.start_session(room_id=ctx.room.name)
    memory_context = await memory.build_memory_context()

    # ------------------------------------------------------------------ #
    #  4. System instructions                                            #
    # ------------------------------------------------------------------ #
    base_instructions = (
        "You are Clare, a voice assistant created by Ashley (KodEx-SA). "
        "Your interface with users is voice only - keep responses short and natural. "
        "Avoid complex punctuation, long sentences, or lists. Speak conversationally. "
        "You can check temperatures in various zones."
        "You have long-term memory: use 'remember' to store facts the user tells you, "
        "'recall' to retrieve them, 'forget' to remove them, and 'list_memories' to see all."
        "Proactively remember useful things like the user's name, preferences, or anything "
        "they'd expect you to know next time."
    )

    instructions = (
        f"{base_instructions}\n\n{memory_context}"
        if memory_context
        else base_instructions
    )

    # ------------------------------------------------------------------ #
    #  5. Tools                                                          #
    # ------------------------------------------------------------------ #
    agent_function = AssistantAgentFunction(memory=memory) # =============== custom agent function with access to memory ===============

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
    #  6. Voice pipeline - all free tier                                 #
    #                                                                    #
    #   STT: Deepgram - nova-3 model, best accuracy, free $200 credit    #
    #   LLM: Groq - llama-3.1-8b-instant, fastest free LLM available     #
    #   TTS: Cartesia - sonic-english, natural voice, free tier          #
    #   VAD: Silero - local, always free                                 #
    # ------------------------------------------------------------------ #
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=cartesia.TTS(
            voice="ac197a78-cec7-4c50-93e5-93bdc1910b11"
        ),  # Neutral, natural voice
        vad=silero.VAD.load(),
    )

    # ------------------------------------------------------------------ #
    #  7. Save conversation to memory                                    #
    # ------------------------------------------------------------------ #
    @session.on("user_input_transcribed")
    def on_user_spoke(event):
        if event.is_final and event.transcript.strip():
            asyncio.ensure_future(memory.save_message("user", event.transcript))

    @session.on("agent_speech_committed")
    def on_agent_spoke(event):
        if hasattr(event, "transcript") and event.transcript.strip():
            asyncio.ensure_future(memory.save_message("assistant", event.transcript))

    # ------------------------------------------------------------------ #
    #  8. Start session                                                  #
    # ------------------------------------------------------------------ #
    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(participant_identity=participant.identity),
    )

    await asyncio.sleep(1)

    user_name = await memory.get_memory("user_name")
    greeting = (
        f"Hi {user_name}, I'm Clare. How may I help you?"
        if user_name
        else "Hi, I'm Clare. How may I help you?"
    )
    try:
        await session.say(greeting, allow_interruptions=True)
    except RuntimeError:
        logger.warning("Session closed before greeting could be sent.")
        return

    # ------------------------------------------------------------------ #
    #  9. Keep alive until room disconnects                              #
    # ------------------------------------------------------------------ #
    disconnect_ev = asyncio.Event()

    def _on_disconnected(*_):
        disconnect_ev.set()

    ctx.room.on("disconnected", _on_disconnected)

    try:
        await disconnect_ev.wait()
    finally:
        await memory.end_session()
        logger.info("Session ended cleanly.")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
