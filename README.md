# Ungerbook — AI Personality Chat Room

A local Python web application that hosts a real-time chat room where multiple AI-driven personalities discuss topics alongside a human participant. Each personality has a distinct expertise, communication style, and persistent memory across sessions.

## Features

- **Multi-personality discussions** — Select 1–10 AI personalities with unique expertise (security, cloud architecture, engineering leadership, legal, QA, ops, and more)
- **Directed messaging** — Address a personality by name (e.g., "Alex, what do you think?") and only they respond. Open messages go to the whole group
- **Autonomous conversation flow** — Personalities decide whether they have something valuable to add before responding; no forced turns
- **Persistent memory** — Each personality remembers key facts across sessions via continuous summarization
- **Moderator controls** — Mute/unmute personalities mid-conversation
- **Pause/Resume** — Pause AI responses while still sending human messages
- **Session history** — Browse and review past conversations; delete sessions you no longer need
- **Export** — Download any conversation as a styled HTML file
- **Auto-scroll toggle** — Disable auto-scroll to read back while the conversation continues
- **Version display** — Live app version shown in sidebar, verifiable via `/api/version`
- **Configurable streaming** — Token-by-token streaming or complete message delivery
- **Round-robin mode** — Alternative to autonomous mode where personalities take ordered turns

## Personalities

| Name | Role | Color |
|------|------|-------|
| Alex Sentinel | Cyber-Security Specialist | 🔴 |
| Jordan Cloudwell | Cloud Solution Architect | 🔵 |
| Morgan Blackwood | Vice President of Engineering | ⚫ |
| Casey Riven | AI Program Manager | 🟣 |
| Dr. Reese Lawton | Legal Representative (AI Specialized) | 🟡 |
| Sam Clearfield | Technical Writer | 🟢 |
| Robin Testwell | Quality Assurance Specialist | 🟠 |
| Pat Uptime | Operations Specialist | 🟢 |

Add new personalities by editing `personalities.json` — no code changes required.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, uvicorn |
| Real-time | WebSockets (native FastAPI) |
| AI Engine | Azure OpenAI SDK (`openai` package) |
| Persistence | SQLite via `aiosqlite` |
| Frontend | Vanilla HTML / CSS / JS |
| Config | `.env` file via `python-dotenv` |
| Testing | pytest, pytest-asyncio |

## Quick Start

### 1. Clone

```bash
git clone https://github.com/gregunger-microsoft/ungerbook.git
cd ungerbook
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure `.env`

Create a `.env` file in the project root:

```
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2025-04-01-preview
AZURE_OPENAI_API_KEY=your-api-key

CONVERSATION_MODE=autonomous
AI_RESPONSE_DELAY_SECONDS=2
MAX_AI_RESPONSES_PER_ROUND=5
MAX_CONTEXT_MESSAGES=50
ENABLE_STREAMING=false
MEMORY_SUMMARIZATION_INTERVAL=10

DATABASE_PATH=data/moltbook.db
PERSONALITIES_FILE=personalities.json
SESSION_EXPORT_DIR=data/sessions
```

All settings are required. The app will fail fast with a clear error message if any value is missing or blank.

### 4. Run

```bash
python main.py
```

Open **http://localhost:8000** in your browser.

## Configuration Reference

| Setting | Description | Values |
|---------|-------------|--------|
| `CONVERSATION_MODE` | How AI personalities take turns | `autonomous` (default) or `round_robin` |
| `AI_RESPONSE_DELAY_SECONDS` | Cooldown between AI messages | Integer (seconds) |
| `MAX_AI_RESPONSES_PER_ROUND` | Max personalities that respond per round | Integer |
| `MAX_CONTEXT_MESSAGES` | Past messages included in each LLM call | Integer |
| `ENABLE_STREAMING` | Token-by-token streaming to UI | `true` or `false` |
| `MEMORY_SUMMARIZATION_INTERVAL` | Messages between memory updates | Integer |
| `DATABASE_PATH` | SQLite database file path | File path |
| `PERSONALITIES_FILE` | Personality definitions JSON | File path |
| `SESSION_EXPORT_DIR` | Directory for JSON session exports | Directory path |

## Conversation Modes

### Autonomous (default)
After any message, each active personality evaluates whether it has something valuable and non-redundant to contribute. Those that do are queued by urgency and respond one at a time. Those that don't stay silent.

### Round-Robin
Each personality takes a turn in order after a human message. Each may respond or pass based on relevance.

## Architecture

```
Moltbook/
├── main.py                          # FastAPI entry point + /api/version
├── VERSION                          # Semver version file
├── Dockerfile                       # Container image definition
├── entrypoint.sh                    # Writes env vars to .env at container start
├── .dockerignore
├── app/
│   ├── config.py                    # .env loading + strict validation
│   ├── models/                      # Dataclasses: Session, Message, Personality, Memory
│   ├── services/
│   │   ├── personality_engine.py    # Azure OpenAI calls (relevance + response)
│   │   ├── orchestrator.py          # Conversation flow + directed messaging
│   │   └── memory_service.py        # Continuous memory summarization
│   ├── repositories/                # SQLite data access (Repository pattern)
│   ├── websocket/handler.py         # WebSocket protocol
│   └── frontend-dist/               # Static HTML/CSS/JS
├── personalities.json               # Personality library
├── tests/                           # 51 unit tests
└── data/                            # SQLite DB + JSON exports (gitignored)
```

### Design Patterns
- **Repository Pattern** — All database access through abstract interfaces
- **Strategy Pattern** — Pluggable conversation modes (autonomous vs round-robin)
- **Observer/Event Pattern** — WebSocket message routing
- **Dependency Injection** — Services receive dependencies via constructors
- **Singleton** — Azure OpenAI client created once and reused

## Testing

```bash
python -m pytest tests/ -v
```

All 51 tests use real SQLite databases (file-based, per-test, auto-cleaned). No mocks.

Coverage areas:
- Config validation (missing/blank `.env` values raise errors)
- Repository CRUD (sessions, messages, memory)
- Orchestrator logic (relevance flow, turn ordering, anti-flood, mute/unmute)
- Personality engine (system prompt construction, context assembly)
- Memory service (continuous summarization, retrieval)

## Adding Personalities

Edit `personalities.json` and add a new entry:

```json
{
  "id": "unique_id",
  "name": "Display Name",
  "role": "Job Title",
  "avatar_color": "#hexcolor",
  "expertise_domain": "What they know",
  "communication_style": "How they communicate",
  "system_prompt": "Full character prompt for the LLM"
}
```

Restart the server. The new personality appears in the UI automatically.

## License

Private project.

## Azure Deployment

The app is containerized and deployed to **Azure Container Apps** via ACR.

**Live URL:** `https://ungerbook.icybush-ac59d8d4.eastus.azurecontainerapps.io`

### Deploy

```powershell
# Bump VERSION file first, then:
.\gunger\scripts\deploy-container-app.ps1
```

The deploy script:
1. Reads `VERSION` file
2. Builds and pushes `ungerbook:<version>` + `ungerbook:latest` to ACR
3. Creates or updates the Container Apps environment and app
4. Deactivates old revisions
5. Verifies `/api/version` returns the expected version

### Azure Resources

See [gunger/scripts/azure-manifest.json](gunger/scripts/azure-manifest.json) for the full resource inventory.

| Resource | Name |
|----------|------|
| Container App | `ungerbook` |
| Container Apps Environment | `ungerbook-env` |
| Container Registry | `gregsacr1` (Basic) |
| Azure OpenAI | `GregUngerAzureOpenAI1` (gpt-5.4-mini) |
