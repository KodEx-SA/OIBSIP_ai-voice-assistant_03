# Clare - AI Voice Assistant

A real-time AI voice assistant built with LiveKit Agents. Clare listens, thinks, speaks, and remembers - powered entirely by free-tier providers.

## Live Stack

| Layer | Provider | Model | Purpose |
|---|---|---|---|
| STT | Deepgram | nova-3 | Converts your voice to text |
| LLM | Groq | llama-3.3-70b-versatile | Processes and generates responses |
| TTS | Cartesia | Jennifer (ac197a78) | Converts responses back to speech |
| VAD | Silero | - | Detects when you are speaking |
| Memory | Supabase | PostgreSQL | Stores sessions, messages, memories |
| Dashboard | Next.js 15 | - | Real-time mission control UI |

## Project Structure

```
OIBSIP_ai-voice-assistant_03/
├── main.py              # Agent entrypoint - voice pipeline wiring
├── api.py               # Clare's tools - temperature, memory operations
├── memory.py            # Supabase cloud memory layer
├── requirements.txt     # Python dependencies
├── schema/              # Supabase SQL schema
├── list_voices.py       # Utility: list available Cartesia voices
├── dashboard/           # Mission Control - Next.js real-time dashboard
│   └── src/
│       ├── app/         # Next.js app router
│       ├── components/  # SessionsPanel, ConversationPanel, ToolLogPanel, MemoriesPanel
│       └── lib/         # Supabase client + TypeScript types
├── ai/                  # Python virtual environment
└── .env                 # API keys (never commit this)
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- Accounts and API keys for:
  - [LiveKit Cloud](https://livekit.io) - room infrastructure
  - [Deepgram](https://deepgram.com) - STT (free $200 credit)
  - [Groq](https://console.groq.com) - LLM (free tier)
  - [Cartesia](https://cartesia.ai) - TTS (free tier)
  - [Supabase](https://supabase.com) - memory database (free tier)

## Setup

### 1. Clone and activate virtual environment

```bash
git clone https://github.com/KodEx-SA/ai-voice-assistant
cd OIBSIP_ai-voice-assistant_03
source ai/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Supabase

Create a project at [supabase.com](https://supabase.com), then run the contents of `schema/schema.sql` in the SQL Editor. Disable RLS on all four tables or add permissive policies for the anon role.

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# AI providers
DEEPGRAM_API_KEY=your-deepgram-key
GROQ_API_KEY=your-groq-key
CARTESIA_API_KEY=your-cartesia-key

# Memory
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key
```

### 5. Start Clare

```bash
python3 main.py start
```

Then open your [LiveKit console](https://cloud.livekit.io) and connect to the room.

### 6. Start the dashboard (optional)

```bash
cd dashboard
cp .env.local.example .env.local   # fill in your Supabase keys
npm install
npm run dev                         # runs on localhost:3001
```

## Features

### Voice Pipeline

Clare processes voice in real time through four stages:

```
You speak -> Deepgram (STT) -> Groq (LLM) -> Cartesia (TTS) -> Clare speaks
                ↑ also running continuously
            Silero VAD (detects speech)
```

### Cloud Memory

Every session is stored in Supabase. Clare remembers:

- **Session history** - every exchange within a conversation
- **Long-term memories** - facts stored across sessions (your name, preferences, etc.)
- **Tool executions** - every tool call with arguments, results, and timing

Clare proactively stores useful information and recalls it in future sessions.

### Tools Clare Can Use

| Tool | What it does |
|---|---|
| `get_temperature` | Returns the temperature for a named zone |
| `remember` | Stores a key/value fact in long-term memory |
| `recall` | Retrieves a stored fact by key |
| `forget` | Deletes a stored fact permanently |
| `list_memories` | Returns all stored facts |

### Mission Control Dashboard

A real-time Next.js dashboard at `localhost:3001` showing:

- Live and historical sessions with duration
- Full conversation transcripts per session
- Tool execution log with arguments, results, and timing
- Long-term memory manager with inline delete

All panels update in real time via Supabase postgres_changes subscriptions.

## Changing Clare's Voice

List voices available on your Cartesia account:

```bash
python3 list_voices.py
```

Then update `main.py`:

```python
tts=cartesia.TTS(voice="your-voice-id-here"),
```

## Architecture Notes

- `main.py` wires the pipeline together and manages the session lifecycle
- `api.py` defines every tool Clare can call, each decorated with `@function_tool()`
- `memory.py` is a pure data layer — it only reads and writes to Supabase
- The dashboard is completely separate from the agent and only reads from Supabase

## Roadmap

- [x] Phase 1 — Cloud memory (Supabase)
- [x] Phase 2 — Mission Control dashboard
- [ ] Phase 3 — Web intelligence (search + browser)
- [ ] Phase 4 — Skill system (dynamic tool loading)
- [ ] Phase 5 — MCP/API integration
- [ ] Phase 6 — Auto-learning pipeline

## Built by

Ashley Koketso Motsie — [KodEx-SA](https://github.com/KodEx-SA)