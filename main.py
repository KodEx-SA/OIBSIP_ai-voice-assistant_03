"""
main.py - Clare voice assistant entrypoint
Phase 3: Web intelligence added (Brave + SerpAPI + Chroma knowledge base)
"""

import asyncio
import logging
from dotenv import load_dotenv
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents import Agent, AgentSession, RoomInputOptions
import livekit.plugins.deepgram as deepgram
import livekit.plugins.cartesia as cartesia
import livekit.plugins.silero as silero
import livekit.plugins.groq as groq

from memory import ClareMemory
from web_search import WebSearcher
from knowledge import KnowledgeBase
from api import AssistantAgentFunction

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("clare.main")


async def entrypoint(ctx: JobContext):
    # ------------------------------------------------------------------ #
    #  1. Connect to LiveKit room                                        #
    # ------------------------------------------------------------------ #
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # ------------------------------------------------------------------ #
    #  2. Wait for participant                                           #
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
    #  4. Initialise web intelligence (Phase 3)                          #
    # ------------------------------------------------------------------ #
    searcher = WebSearcher()
    knowledge = KnowledgeBase()
    await knowledge.initialise()

    # ------------------------------------------------------------------ #
    #  5. System instructions                                            #
    # ------------------------------------------------------------------ #
    base_instructions = (
        "You are Clare, a voice assistant created by Ashley (known as KodEx-SA across github). "
        "He is a software developer with a passion for AI and building useful tools. "
        "He was born in South Africa in the year of 2000"
        "Your interface with users is voice only - keep responses short and natural. "
        "Avoid complex punctuation, long sentences, or lists. Speak conversationally. "
        "You have access to the web and a personal knowledge base. "
        "When asked about current events, news, prices, people, or anything you are "
        "uncertain about - use web_search immediately. Don't say you can't access "
        "the internet. You can, and should. "
        "Before searching the web, always check recall_knowledge first - you may "
        "already have learned about it. "
        "When asked to learn or research a topic, use learn_about to search, read, "
        "and store the knowledge permanently. "
        "You also have long-term memory: use remember to store facts, recall to "
        "retrieve them, forget to remove them, and list_memories to see all. "
        "You can check temperatures in various zones. "
        "Proactively remember useful things like the user's name and preferences."
    )

    instructions = (
        f"{base_instructions}\n\n{memory_context}"
        if memory_context
        else base_instructions
    )

    # ------------------------------------------------------------------ #
    #  6. Wire up tools                                                  #
    # ------------------------------------------------------------------ #
    agent_function = AssistantAgentFunction(
        memory=memory,
        searcher=searcher,
        knowledge=knowledge,
    )

    agent = Agent(
        instructions=instructions,
        tools=[
            # Temperature
            agent_function.get_temperature,
            # Memory
            agent_function.remember,
            agent_function.recall,
            agent_function.forget,
            agent_function.list_memories,
            # Web intelligence (Phase 3)
            agent_function.web_search,
            agent_function.read_webpage,
            agent_function.learn_about,
            agent_function.recall_knowledge,
            agent_function.list_knowledge_topics,
        ],
    )

    # ------------------------------------------------------------------ #
    #  7. Voice pipeline                                                 #
    # ------------------------------------------------------------------ #
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        # llm=groq.LLM(model="llama-3.3-70b-versatile"),
        # llm=groq.LLM(model="llama3-groq-70b-8192-tool-use-preview"),
        llm=groq.LLM(model="llama-3.1-8b-instant"),
        tts=cartesia.TTS(voice="ac197a78-cec7-4c50-93e5-93bdc1910b11"),
        vad=silero.VAD.load(),
    )

    # ------------------------------------------------------------------ #
    #  8. Save conversation to memory                                    #
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
    #  9. Start session                                                  #
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
        else "Hi Sir, I'm Clare. How may I help you?"
    )

    try:
        await session.say(greeting, allow_interruptions=True)
    except RuntimeError:
        logger.warning("Session closed before greeting could be sent.")
        return

    # ------------------------------------------------------------------ #
    #  10. Keep alive until room disconnects                             #
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
