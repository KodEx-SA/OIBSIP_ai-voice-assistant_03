# Clare - Personal Learning Notes
> Breaking down every piece of the codebase: what it is, why it exists, and how it works.

---

## Table of Contents

1. [The Big Picture](#1-the-big-picture)
2. [main.py - Line by Line](#2-mainpy--line-by-line)
3. [api.py - Line by Line](#3-apipy--line-by-line)
4. [memory.py - Line by Line](#4-memorypy--line-by-line)
5. [Tools and Concepts](#5-tools-and-concepts)
6. [The Database (Supabase)](#6-the-database-supabase)
7. [The Dashboard](#7-the-dashboard)
8. [Key Python Concepts Used](#8-key-python-concepts-used)
9. [The Full Flow - What Happens When You Speak](#9-the-full-flow--what-happens-when-you-speak)

---

## 1. The Big Picture

Clare is made of three layers:

```
┌─────────────────────────────────────────────────┐
│                   ME (user voice)               │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│          LIVEKIT (room infrastructure)          │
│  Handles audio streaming between User and Agent │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│             THE AGENT (main.py)                 │
│                                                 │
│  Deepgram STT -> Groq LLM -> Cartesia TTS       │
│  Silero VAD (always listening for speech)       │
│                                                 │
│  Tools (api.py):                                │
│    get_temperature, remember, recall,           │
│    forget, list_memories                        │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              SUPABASE (memory.py)               │
│   sessions / messages / memories / tool_logs    │
└─────────────────────────────────────────────────┘
```

---

## 2. main.py - Line by Line

### Imports

```python
import asyncio
```
Python's built-in library for writing async code - code that can pause and wait (e.g. for a network response) without freezing the whole program. Almost everything in Clare uses `await` which requires asyncio.

```python
import logging
```
Python's built-in library for printing structured log messages. Better than `print()` because logs have levels (INFO, WARNING, ERROR) and timestamps. 
You see these in the terminal output throughout development.

```python
from dotenv import load_dotenv
```
Reads your `.env` file and loads all the key=value pairs into the environment so `os.getenv("DEEPGRAM_API_KEY")` works. 
Without this your API keys are invisible to Python.

```python
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents import Agent, AgentSession, RoomInputOptions
```
These are the core LiveKit classes:
- `AutoSubscribe` - tells LiveKit what to subscribe to (audio only, or audio+video)
- `JobContext` - the object LiveKit passes to your entrypoint. It contains the room, participant info, etc.
- `WorkerOptions` - configuration for the worker process (which function to call when a job arrives)
- `cli` - the command-line runner. `cli.run_app(...)` starts the worker when you run `python3 main.py start`
- `Agent` - defines Clare's personality (instructions) and what tools she can use
- `AgentSession` - the running voice pipeline (STT + LLM + TTS + VAD wired together)
- `RoomInputOptions` - options for how the session connects to the room (which participant to listen to)

```python
import livekit.plugins.groq as groq
import livekit.plugins.deepgram as deepgram
import livekit.plugins.cartesia as cartesia
import livekit.plugins.silero as silero
```
The four providers that power Clare's voice. Each is a LiveKit plugin - a package that wraps the provider's API in a format LiveKit understands.

```python
from memory import ClareMemory
from api import AssistantAgentFunction
```
Your own files. Python imports work like this: `from filename import ClassName`. No `.py` extension needed.

---

### The entrypoint function

```python
async def entrypoint(ctx: JobContext):
```
This is the function LiveKit calls every time someone connects to a room. The `async` keyword means this function can use `await` inside it. 
`ctx: JobContext` means the parameter is called `ctx` and its type is `JobContext` - this is just documentation, Python doesn't enforce it.

```python
await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
```
Connects Clare to the LiveKit room. `AUDIO_ONLY` means Clare subscribes to audio tracks only - she doesn't need video. 
The `await` means: pause here until the connection is established before moving on.

```python
participant = await ctx.wait_for_participant()
```
Waits until a real human joins the room. Without this, Clare would try to start talking to an empty room with no audio track to publish to. 
This was the original voice bug.

```python
except RuntimeError as e:
    logger.warning("Room closed before participant joined - %s", e)
    return
```
If the user connects and immediately disconnects before Clare finishes initialising, this catches the error and exits cleanly instead of crashing.

```python
memory = ClareMemory()
await memory.start_session(room_id=ctx.room.name)
memory_context = await memory.build_memory_context()
```
Creates the memory object, starts a session in Supabase, and loads any previously stored memories. 
`ctx.room.name` is the unique ID LiveKit assigns to the room (e.g. `console-abc123`).

```python
base_instructions = (
    "You are Clare, a voice assistant..."
)
instructions = (
    f"{base_instructions}\n\n{memory_context}"
    if memory_context
    else base_instructions
)
```
Clare's personality and behaviour rules. If there are stored memories, they get appended to the instructions so Clare knows them before the conversation even starts. The `f"..."` is an f-string - the `{variable}` parts get replaced with the variable's value.

```python
agent = Agent(
    instructions=instructions,
    tools=[
        agent_function.get_temperature,
        agent_function.remember,
        ...
    ],
)
```
Creates the agent with her instructions and a list of tools she can call. The LLM reads the docstrings on each tool to understand when and how to use them.

```python
session = AgentSession(
    stt=deepgram.STT(model="nova-3"),
    llm=groq.LLM(model="llama-3.3-70b-versatile"),
    tts=cartesia.TTS(voice="ac197a78-..."),
    vad=silero.VAD.load(),
)
```
Wires the four providers together into a single pipeline. This is the voice engine. Nothing has started yet - this just configures it.

```python
@session.on("user_input_transcribed")
def on_user_spoke(event):
    if event.is_final and event.transcript.strip():
        asyncio.ensure_future(memory.save_message("user", event.transcript))
```
An event listener. Whenever Deepgram finishes transcribing what you said, this function runs and saves your words to Supabase. 
`event.is_final` means the transcription is complete (not a partial mid-sentence guess). 
`event.transcript.strip()` removes whitespace and checks the string isn't empty.

`asyncio.ensure_future(...)` is how you call an async function from inside a regular (non-async) function. It schedules the coroutine to run without blocking.

```python
await session.start(
    room=ctx.room,
    agent=agent,
    room_input_options=RoomInputOptions(participant_identity=participant.identity),
)
```
Starts the voice pipeline. From this point Clare is live — she's listening, thinking, and speaking.

```python
disconnect_ev = asyncio.Event()

def _on_disconnected(*_):
    disconnect_ev.set()

ctx.room.on("disconnected", _on_disconnected)

try:
    await disconnect_ev.wait()
finally:
    await memory.end_session()
```
Keeps Clare running until the room disconnects. `asyncio.Event()` is a flag that starts as False. 
`disconnect_ev.wait()` pauses execution until the flag is set. 
When the room disconnects, `_on_disconnected` sets the flag, `wait()` unblocks, the `finally` block runs cleanup, and the entrypoint returns. 
This replaced the broken `ctx.room.wait_for_disconnect()` call.

---

## 3. api.py - Line by Line

### Imports

```python
import enum
```
Python's enum module. Lets you define a fixed set of named values. Used for `TemperatureZone` so Clare can only check valid rooms.

```python
import time
```
For measuring how long things take. `time.monotonic()` returns a high-precision clock value that only goes forward (unlike `time.time()` which can go backward during clock adjustments).

```python
from livekit.agents import function_tool, RunContext
```
- `function_tool` - a decorator that registers a method as a tool the LLM can call
- `RunContext` - LiveKit passes this to every tool call; contains session info

---

### TemperatureZone

```python
class TemperatureZone(enum.Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    ...
```
An enum is a controlled list. Instead of accepting any string (which could be a typo), the LLM can only pass one of these specific values. LiveKit/Groq automatically maps "bedroom" -> `TemperatureZone.BEDROOM` before your function runs. If the user says "garage" it fails before reaching your code.

---

### AssistantAgentFunction

```python
class AssistantAgentFunction:
    def __init__(self, memory: ClareMemory) -> None:
        super().__init__()
        self.memory = memory
```
A plain Python class that groups all tools together. `__init__` is the constructor - it runs when you do `AssistantAgentFunction(memory=memory)`. `self.memory = memory` stores the memory object so every tool method can use it via `self.memory`.

`super().__init__()` calls the parent class constructor. Since there's no parent class beyond Python's base `object`, this is harmless but technically correct.

---

### @function_tool() decorator

```python
@function_tool()
async def get_temperature(self, context: RunContext, zone: TemperatureZone):
    """Get the current temperature in a specific zone or room.

    Args:
        zone: The specific zone/room to check temperature for
    """
```
The `@function_tool()` decorator does three things:
1. Registers this method as a tool the LLM can call
2. Reads the **docstring** to understand what the tool does
3. Reads the **type hints** (`zone: TemperatureZone`) to know what parameters to pass

The docstring is not just for humans - the LLM reads it to decide when to use this tool and what to pass. 
If you remove or break the docstring, the LLM won't know how to use the tool correctly.

---

### Tool execution pattern

Every tool follows the same pattern:

```python
start = time.monotonic() # 1. Start timer

# 2. Do the actual work
result = { ... }

await self.memory.log_tool_execution( # 3. Log to Supabase
    tool_name="...",
    arguments={...},
    result=result,
    status="success",
    duration_ms=int((time.monotonic() - start) * 1000),
)

return result # 4. Return result to the LLM
```

`time.monotonic()` returns seconds as a float. Subtracting start from end gives elapsed seconds. 
Multiplying by 1000 converts to milliseconds. `int(...)` rounds it to a whole number.

---

## 4. memory.py — Line by Line

### Imports

```python
from supabase import create_client, Client
```
The Supabase Python SDK. `create_client(url, key)` returns a `Client` object that lets you run database queries. 
`Client` is imported only for the type hint `self.client: Client`.

```python
from datetime import datetime, timezone
```
For generating timestamps. `datetime.now(timezone.utc).isoformat()` produces a UTC timestamp string like `2026-06-08T10:12:22.660981+00:00` - the format Supabase expects.

---

### ClareMemory class

```python
def __init__(self):
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_KEY must be set...")

    self.client: Client = create_client(url, key)
    self.session_id: str | None = None
```
`os.getenv("KEY")` reads from the environment (populated by `load_dotenv()`). The guard clause `if not url or not key` raises an error immediately with a clear message rather than crashing later with a confusing error. `str | None` means the variable is either a string or None - a Python 3.10+ type hint.

---

### Supabase query pattern

All database operations follow this pattern:

```python
result = (
    self.client.table("sessions")  # which table
    .insert({...})                 # what operation
    .execute()                     # actually run it
)
```

For reads:
```python
result = (
    self.client.table("memories")
    .select("key, content")             # which columns
    .eq("key", key)                     # WHERE key = key
    .order("updated_at", desc=True)     # ORDER BY updated_at DESC
    .limit(50)                          # LIMIT 50
    .execute()
)
data = result.data     # list of dicts
```

This is called a **query builder** pattern. Each method returns the same object so you can chain calls. 
`.execute()` is what actually sends the query to Supabase.

---

### build_memory_context

```python
async def build_memory_context(self) -> str:
    memories = await self.get_all_memories()
    if not memories:
        return ""
    lines = ["[Clare's long-term memories]"]
    for m in memories:
        lines.append(f"  {m['key']}: {m['content']}")
    return "\n".join(lines)
```
Turns the list of memories into a string that gets injected into Clare's system prompt. For example:

```
[Clare's long-term memories]
  user_name: Ashley
  favourite_zone: bedroom
```

This is how Clare "knows" things before you've said a word - the memories are baked into her instructions at session start.

---

## 5. Tools and Concepts

### What is LiveKit?

LiveKit is a real-time audio/video infrastructure platform. 
It handles the hard parts of streaming audio between you and Clare - connection management, packet loss, codec negotiation. 
You don't write any of that. You just connect to a room and LiveKit handles delivery.

### What is Deepgram?

A speech recognition API. You send it audio, it returns text. 
The `nova-3` model is their most accurate general-purpose model. 
It streams results in real time - you don't have to wait until you finish speaking to get a transcript.

### What is Groq?

An AI inference provider that runs open-source LLMs (like Meta's LLaMA) at very high speed. 
`llama-3.3-70b-versatile` is a 70-billion parameter model - comparable in quality to GPT-4 but free on Groq's tier. 
The speed comes from their custom hardware (LPUs instead of GPUs).

### What is Cartesia?

A text-to-speech API. You send it text, it returns audio. 
The voices are pre-trained neural voice models. Jennifer (`ac197a78`) is one of their natural-sounding English voices. Each voice has its own UUID.

### What is Silero VAD?

Voice Activity Detection - a local (runs on your machine, no API) model that listens to the audio stream and tells LiveKit "the user is speaking now" / "the user has stopped speaking". Without it, Clare wouldn't know when to start processing your words or when you've finished your sentence.

### What is Supabase?

A cloud database platform built on PostgreSQL. It provides a REST API for your database (so Python can query it without writing SQL directly), real-time subscriptions (so the dashboard can react to new rows instantly), and row-level security (RLS) for access control.

---

## 6. The Database (Supabase)

Four tables:

**sessions** - one row per LiveKit room connection
```
id (UUID) | room_id (text) | started_at | ended_at | metadata
```

**messages** - every utterance, linked to a session
```
id | session_id | role (user/assistant/system) | content | created_at
```

**memories** - long-term key/value facts, not tied to any session
```
id | key (unique) | content | source | created_at | updated_at
```

**tool_executions** - every tool call Clare makes
```
id | session_id | tool_name | arguments (JSON) | result (JSON) | status | executed_at | duration_ms
```

### Why UUID instead of integer IDs?

UUIDs (`7b4e3500-eb53-4a4e-8375-f798308aa7d7`) are globally unique - no two rows in any table in any database will ever have the same UUID. 
This makes it safe to merge data, share IDs across systems, and prevents ID enumeration attacks (someone guessing `?id=1`, `?id=2` etc.).

### What is RLS?

Row Level Security - a PostgreSQL feature that lets you write rules controlling who can read/write each row. 
Supabase enables it by default. Since Clare uses the `anon` key (public), we added policies allowing the anon role full access to our specific tables.

---

## 7. The Dashboard

Built with Next.js 15 and TypeScript. It connects to the same Supabase project as Clare and subscribes to real-time changes.

**Key concept — Supabase Realtime:**
```typescript
const channel = supabase
  .channel('sessions-watch')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'sessions' }, () => {
    // this runs every time a row is inserted/updated/deleted in sessions
    refetchData()
  })
  .subscribe()
```
Instead of polling (checking every few seconds), Supabase pushes a notification to the browser the moment the database changes. 
This is why the dashboard updates instantly when Clare logs a tool call.

**`'use client'`** at the top of components means that component runs in the browser (can use state, effects, event listeners). 
Without it, Next.js tries to render it on the server where there's no `window`, no browser APIs, and no real-time subscriptions.

---

## 8. Key Python Concepts Used

### async / await

```python
async def my_function():
    result = await some_other_async_function()
    return result
```
`async` marks a function as a coroutine - it can be paused. `await` pauses the function at that line until the awaited thing finishes, then continues. 
While paused, Python can run other things. 
This is how Clare can listen for your voice, handle a Supabase query, and manage a LiveKit connection all at the same time without threads.

### Decorators

```python
@function_tool()
async def get_temperature(self, ...):
    ...
```
A decorator is a function that wraps another function. `@function_tool()` is equivalent to:
```python
get_temperature = function_tool()(get_temperature)
```
It modifies the function - in this case registering it with LiveKit as a callable tool - without you having to change the function itself.

### f-strings

```python
name = "Ashley"
message = f"Hello {name}, welcome back."
# -> "Hello Ashley, welcome back."
```
A way to embed variables directly in strings. The `f` prefix enables it. Any `{expression}` inside gets evaluated and inserted.

### Type hints

```python
def start_session(self, room_id: str) -> str:
```
`: str` means room_id should be a string. `-> str` means the function returns a string. 
Python doesn't enforce these at runtime - they're documentation for you and your tools (like VS Code's intellisense).

### try / except / finally

```python
try:
    result = risky_operation()
except RuntimeError as e:
    handle_the_error(e)
finally:
    always_runs_this()
```
`try` - attempt this. `except` - if a specific error happens, handle it here instead of crashing. `finally` - always run this, whether or not an error occurred. Used in Clare's disconnect handler to ensure `memory.end_session()` always runs even if something goes wrong.

---

## 9. The Full Flow - What Happens When You Speak

1. **You speak** into your mic in the LiveKit console
2. **LiveKit** streams the audio to Clare's worker process
3. **Silero VAD** detects you are speaking and signals to start capturing
4. **Silero VAD** detects you stopped speaking and signals end of utterance
5. **Deepgram STT** receives the audio chunk and returns text (e.g. "What's the temperature in the bedroom?")
6. **LiveKit agents** fires `user_input_transcribed` event → `memory.save_message("user", ...)` runs
7. **Groq LLM** receives the transcript plus Clare's instructions plus conversation history
8. Groq decides to call the `get_temperature` tool with `zone=TemperatureZone.BEDROOM`
9. **api.py `get_temperature`** runs — looks up 22°C, logs to Supabase, returns result
10. **Groq LLM** receives the tool result and generates a response: "The bedroom is 22 degrees."
11. **Cartesia TTS** converts the text to audio using Jennifer's voice
12. **LiveKit** streams the audio back to you
13. **You hear Clare speak**
14. **LiveKit agents** fires `agent_speech_committed` event -> `memory.save_message("assistant", ...)` runs
15. Both messages are now in Supabase and visible in the dashboard in real time
